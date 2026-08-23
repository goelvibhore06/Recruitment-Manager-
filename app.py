from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Mapping

import pandas as pd
import streamlit as st

from cleaning import CleaningReport, apply_statuses, clean_student_data, shortlist


st.set_page_config(
    page_title="StudentSelect | Admissions workspace",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

SUBJECTS = ("Math", "Science", "English")
FILTER_SUFFIXES = ("search", "grade", "gender", "status")
PAGE_SIZES = (50, 100, 250)
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _grade_sort_key(grade: object) -> int | float:
    """Return a numeric key for normalised grade labels, with unknown values last."""
    grade_number = str(grade).removeprefix("Grade ")
    return int(grade_number) if grade_number.isdecimal() else float("inf")


def _sort_by_grade(data: pd.DataFrame) -> pd.DataFrame:
    """Order student records by grade number, then name."""
    return (
        data.assign(_grade_order=data["Grade"].map(_grade_sort_key))
        .sort_values(["_grade_order", "Name"], kind="stable")
        .drop(columns="_grade_order")
        .reset_index(drop=True)
    )


def _init_state() -> None:
    defaults = {
        "cleaned_data": None,
        "report": None,
        "statuses": {},
        "loaded_signature": None,
        "pending_data": None,
        "pending_filename": None,
        "pending_signature": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _csv_bytes(data: pd.DataFrame, *, include_rank: bool = False) -> bytes:
    columns_to_drop = ["Student ID"]
    if not include_rank:
        columns_to_drop.append("Rank")
    export = data.drop(columns=columns_to_drop, errors="ignore").copy()
    # CSV files are commonly opened in spreadsheet apps, which can interpret
    # leading formula characters in user-supplied text as executable formulas.
    for column in export.select_dtypes(include="object"):
        export[column] = export[column].map(_escape_csv_formula)
    return export.to_csv(index=False).encode("utf-8")


def _escape_csv_formula(value: object) -> object:
    """Render text safely when the CSV is opened in a spreadsheet application."""
    if isinstance(value, str) and value.lstrip().startswith(CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _read_csv(file: BytesIO | object) -> pd.DataFrame:
    try:
        return pd.read_csv(file, dtype=str, keep_default_na=True)
    except UnicodeDecodeError:
        file.seek(0)
        return pd.read_csv(file, dtype=str, encoding="latin-1", keep_default_na=True)


def _load_data(raw: pd.DataFrame, signature: str) -> None:
    cleaned, report = clean_student_data(raw)
    st.session_state.cleaned_data = cleaned
    st.session_state.report = report
    st.session_state.statuses = {}
    st.session_state.loaded_signature = signature
    st.session_state.pending_data = None
    st.session_state.pending_filename = None
    st.session_state.pending_signature = None


def _stage_data(raw: pd.DataFrame, filename: str, signature: str) -> None:
    """Hold an uploaded file for explicit user approval before cleaning."""
    st.session_state.cleaned_data = None
    st.session_state.report = None
    st.session_state.statuses = {}
    st.session_state.loaded_signature = None
    st.session_state.pending_data = raw
    st.session_state.pending_filename = filename
    st.session_state.pending_signature = signature


def _show_report(data: pd.DataFrame, report: CleaningReport) -> None:
    with st.expander("Cleaning results", expanded=True):
        st.caption("Every uploaded file is processed in memory. Student data is not retained after this browser session.")
        audit = pd.DataFrame(
            {
                "Check": [
                    "Rows received", "Rows ready for review", "Blank rows removed", "Duplicate records removed",
                    "Missing scores filled", "Invalid scores repaired", "Labels standardised", "Totals recalculated",
                ],
                "Result": [
                    report.source_rows, report.output_rows, report.blank_rows_removed, report.duplicate_rows_removed,
                    report.missing_scores_imputed, report.invalid_scores_repaired, report.normalised_values,
                    report.totals_recalculated,
                ],
            }
        )
        st.dataframe(audit, hide_index=True, width="stretch")
        st.info(
            "Missing scores are filled with the valid-file median for that subject. Non-numeric and out-of-range "
            "scores are repaired the same way. Names, gender labels, and grades are standardised; totals are then "
            "recalculated from Math, Science, and English."
        )
        st.download_button(
            "Download cleaned dataset",
            data=_csv_bytes(data),
            file_name="cleaned_student_dataset.csv",
            mime="text/csv",
            type="primary",
            width="stretch",
        )


def _filter_roster(data: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    """Render shared roster controls and return the matching records."""
    search_col, grade_col, gender_col, status_col = st.columns((2.1, 1.25, 1.25, 1.1))
    search = search_col.text_input("Search students", placeholder="Name or grade", key=f"{key_prefix}_search")
    grades = grade_col.multiselect(
        "Grade", sorted(data["Grade"].unique(), key=_grade_sort_key), key=f"{key_prefix}_grade"
    )
    genders = gender_col.multiselect("Gender", sorted(data["Gender"].unique()), key=f"{key_prefix}_gender")
    statuses = status_col.multiselect("Eligibility", ["Active", "Debarred"], key=f"{key_prefix}_status")

    filtered = data.copy()
    if search:
        query = search.casefold().strip()
        filtered = filtered.loc[
            filtered["Name"].str.casefold().str.contains(query, na=False)
            | filtered["Grade"].str.casefold().str.contains(query, na=False)
        ]
    if grades:
        filtered = filtered.loc[filtered["Grade"].isin(grades)]
    if genders:
        filtered = filtered.loc[filtered["Gender"].isin(genders)]
    if statuses:
        filtered = filtered.loc[filtered["Status"].isin(statuses)]
    return filtered


def _clear_roster_filters(key_prefix: str) -> None:
    """Reset the controls that only affect one roster table."""
    for suffix in FILTER_SUFFIXES:
        st.session_state.pop(f"{key_prefix}_{suffix}", None)


def _roster_filters_are_active(key_prefix: str) -> bool:
    """Return whether any search or roster selection currently narrows a table."""
    return any(st.session_state.get(f"{key_prefix}_{suffix}") for suffix in FILTER_SUFFIXES)


def _merge_status_updates(statuses: Mapping[str, str], updates: Mapping[str, str]) -> dict[str, str]:
    """Keep only debarred decisions while preserving students outside the current page.

    Active is the default, so omitting it keeps session state compact even when
    an administrator reviews a large, paginated roster.
    """
    merged = {student_id: status for student_id, status in statuses.items() if status == "Debarred"}
    for student_id, status in updates.items():
        if status == "Debarred":
            merged[student_id] = status
        else:
            merged.pop(student_id, None)
    return merged


def _paginate(data: pd.DataFrame, key_prefix: str) -> tuple[pd.DataFrame, int, int]:
    """Render compact paging controls and return the visible subset and range."""
    if data.empty:
        return data, 0, 0

    page_size_col, page_col = st.columns((1, 1))
    page_size = page_size_col.selectbox(
        "Rows per page", PAGE_SIZES, index=1, key=f"{key_prefix}_page_size"
    )
    page_count = max(1, (len(data) + page_size - 1) // page_size)
    page_key = f"{key_prefix}_page"
    if st.session_state.get(page_key, 1) > page_count:
        st.session_state[page_key] = page_count
    page = page_col.number_input("Page", min_value=1, max_value=page_count, value=1, step=1, key=page_key)
    start = (int(page) - 1) * page_size
    end = min(start + page_size, len(data))
    return data.iloc[start:end], start + 1, end


def _status_editor_key(data: pd.DataFrame) -> str:
    """Give each filtered roster its own editor state.

    Streamlit stores data-editor changes by row position. A stable key for a
    different filtered result could otherwise apply an old row edit to the
    student now occupying that position.
    """
    roster_identity = "\x1f".join(data["Student ID"].astype(str))
    return f"student_status_editor_{hashlib.sha1(roster_identity.encode('utf-8')).hexdigest()[:12]}"


def _status_editor(data: pd.DataFrame) -> None:
    editor_data = data[["Student ID", "Name", "Gender", "Grade", "Math", "Science", "English", "Total"]].copy()
    editor_data["Active"] = data["Status"].eq("Active")
    edited = st.data_editor(
        editor_data,
        key=_status_editor_key(data),
        hide_index=True,
        width="stretch",
        height=500,
        disabled=["Student ID", "Name", "Gender", "Grade", "Math", "Science", "English", "Total"],
        column_config={
            "Student ID": None,
            "Active": st.column_config.CheckboxColumn(
                "Active",
                help="Uncheck to debar a student from shortlists immediately.",
                default=True,
            ),
            "Total": st.column_config.NumberColumn(format="%.0f / 300"),
        },
    )
    # Only the filtered rows are present in this editor. Merge their changes so
    # previously debarred students outside the current filter keep their status.
    updates = {
        student_id: "Active" if active else "Debarred"
        for student_id, active in zip(edited["Student ID"], edited["Active"])
    }
    st.session_state.statuses = _merge_status_updates(st.session_state.statuses, updates)


def _show_overview(data: pd.DataFrame) -> None:
    active = data.loc[data["Status"] == "Active"]
    st.markdown("#### Cohort at a glance")
    total_col, active_col, avg_col, top_col = st.columns(4)
    total_col.metric("Students", f"{len(data):,}")
    active_col.metric("Eligible", f"{len(active):,}", f"{len(data) - len(active):,} debarred")
    avg_col.metric("Average score", f"{data['Total'].mean():.0f} / 300")
    top_col.metric("Top score", f"{data['Total'].max():.0f} / 300")

    left, right = st.columns((1.05, 0.95), gap="large")
    with left:
        st.markdown("#### Subject performance")
        subject_averages = data[list(SUBJECTS)].mean().round(1)
        st.bar_chart(subject_averages, color="#4F46E5", horizontal=True)
        st.caption("Average score out of 100 across the cleaned cohort.")
    with right:
        st.markdown("#### Grade distribution")
        by_grade = data.groupby("Grade", sort=False).size().reindex(
            sorted(data["Grade"].unique(), key=_grade_sort_key)
        ).rename("Students")
        st.bar_chart(by_grade, color="#14B8A6")
        st.caption("Use the Roster tab to focus on a particular group.")

    st.markdown("#### Leading candidates")
    leaders = data.sort_values(["Total", "Name"], ascending=[False, True]).head(5).copy()
    leaders.insert(0, "Rank", range(1, len(leaders) + 1))
    st.dataframe(
        leaders[["Rank", "Name", "Grade", "Math", "Science", "English", "Total", "Status"]],
        hide_index=True,
        width="stretch",
        column_config={"Total": st.column_config.NumberColumn(format="%.0f / 300")},
    )


def _show_shortlist(data: pd.DataFrame) -> None:
    st.markdown("#### Build a shortlist")
    st.caption("Set transparent rules, then export an ordered list for human review.")

    controls, summary = st.columns((1.2, 1), gap="large")
    with controls:
        minimum_total = st.slider("Minimum total score", min_value=0, max_value=300, value=180, step=5)
        subject_floor = st.slider("Minimum score in every subject", min_value=0, max_value=100, value=0, step=5)
        selected_grades = st.multiselect(
            "Limit to grades", sorted(data["Grade"].unique(), key=_grade_sort_key), placeholder="All grades"
        )
        maximum_candidates = st.number_input(
            "Maximum candidates", min_value=1, max_value=max(1, len(data)), value=min(25, len(data)), step=1,
        )

    candidates = shortlist(data, minimum_total)
    candidates = candidates.loc[(candidates[list(SUBJECTS)] >= subject_floor).all(axis=1)]
    if selected_grades:
        candidates = candidates.loc[candidates["Grade"].isin(selected_grades)]
    candidates = candidates.sort_values(["Total", "Name"], ascending=[False, True], kind="stable").copy()
    candidates.insert(0, "Rank", range(1, len(candidates) + 1))
    displayed = candidates.head(int(maximum_candidates))

    with summary:
        st.markdown("<div class='shortlist-summary'>", unsafe_allow_html=True)
        st.metric("Candidates matched", f"{len(candidates):,}")
        st.metric("Shown in shortlist", f"{len(displayed):,}")
        st.metric("Cut-off score", "—" if displayed.empty else f"{displayed['Total'].iloc[-1]:.0f} / 300")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### Ranked candidates")
    if displayed.empty:
        st.info("No active students match these criteria. Try lowering a threshold or widening the grade scope.")
    else:
        st.dataframe(
            displayed[["Rank", "Name", "Gender", "Grade", "Math", "Science", "English", "Total", "Status"]],
            hide_index=True,
            width="stretch",
            height=440,
            column_config={
                "Rank": st.column_config.NumberColumn(format="#%d"),
                "Total": st.column_config.NumberColumn(format="%.0f / 300"),
            },
        )
    st.download_button(
        "Download ranked shortlist",
        data=_csv_bytes(displayed, include_rank=True),
        file_name="student_shortlist.csv",
        mime="text/csv",
        type="primary",
        disabled=displayed.empty,
    )
    st.caption("The export includes the current eligibility status and rank, but never the internal Student ID.")


def _sidebar() -> object:
    with st.sidebar:
        st.markdown("<div class='sidebar-brand'>🎓 <span>StudentSelect</span></div>", unsafe_allow_html=True)
        st.caption("Admissions review workspace")
        st.markdown("<div class='sidebar-section-label'>DATA SOURCE</div>", unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Upload student CSV", type=["csv"], help="Maximum file size: 20 MB. Select Clean dataset after upload."
        )
        if st.button("Use sample data", width="stretch"):
            sample = Path(__file__).parent / "data" / "sample_students.csv"
            _load_data(pd.read_csv(sample, dtype=str), "example")
            st.rerun()
        return uploaded


def _styles() -> None:
    st.markdown(
        """<style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
        :root { --ink: #172033; --muted: #68738A; --line: #E8ECF4; --indigo: #4F46E5; }
        .stApp { background: #F6F7FB; font-family: 'DM Sans', sans-serif; }
        .block-container { max-width: 1440px; padding: 1.6rem 2.4rem 3rem; }
        [data-testid='stHeader'] { background: rgba(246,247,251,.88); }
        [data-testid='stSidebar'] { background: #101828; }
        [data-testid='stSidebar'] * { color: #E9EDF6; }
        [data-testid='stSidebar'] [data-testid='stFileUploaderDropzone'] { background: #1B2740; border: 1px dashed #53627D; }
        [data-testid='stSidebar'] [data-testid='stFileUploaderDropzone'] button { color: #172033; }
        [data-testid='stSidebar'] .stButton button { background: #F0C674; color: #172033; border: 0; font-weight: 700; }
        .sidebar-brand { font-family: 'Playfair Display', serif; font-size: 1.55rem; font-weight: 700; margin: .55rem 0 .15rem; }
        .sidebar-section-label { color: #98A6BF !important; font-size: .68rem; letter-spacing: .12em; font-weight: 700; margin: 1.15rem 0 .5rem; }
        .hero { border: 1px solid #E6E9F2; border-radius: 22px; padding: 2rem 2.25rem; margin-bottom: 1.25rem; background: radial-gradient(circle at 95% 0%, #E5E3FF 0, transparent 30%), #FFF; }
        .eyebrow { color: var(--indigo); font-size: .75rem; letter-spacing: .12em; font-weight: 700; margin-bottom: .35rem; }
        .hero h1 { color: var(--ink); font-family: 'Playfair Display', serif; font-size: clamp(2rem, 3vw, 3rem); margin: 0 0 .4rem; letter-spacing: -.03em; }
        .hero p { color: var(--muted); font-size: 1.05rem; margin: 0; max-width: 660px; }
        [data-testid='stMetric'] { background: #FFF; border: 1px solid var(--line); border-radius: 15px; padding: 1rem 1.1rem; box-shadow: 0 2px 5px rgba(16,24,40,.02); }
        [data-testid='stMetricLabel'] { color: var(--muted); font-size: .82rem; font-weight: 600; }
        [data-testid='stMetricValue'] { color: var(--ink); font-family: 'Playfair Display', serif; }
        .shortlist-summary [data-testid='stMetric'] { box-shadow: none; border-radius: 13px; margin-bottom: .35rem; }
        .stTabs [data-baseweb='tab-list'] { gap: .5rem; border-bottom: 1px solid var(--line); }
        .stTabs [data-baseweb='tab'] { border-radius: 9px 9px 0 0; padding: .72rem 1rem; color: var(--muted); font-weight: 600; }
        .stTabs [aria-selected='true'] { color: var(--indigo); background: #F0EFFF; }
        .stButton > button[kind='primary'] { background: var(--indigo); border-color: var(--indigo); font-weight: 700; }
        .stDownloadButton > button { border-radius: 9px; font-weight: 700; }
        [data-testid='stDataFrame'] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
        .stAlert { border-radius: 12px; }
        </style>""",
        unsafe_allow_html=True,
    )


def main() -> None:
    _init_state()
    _styles()
    uploaded = _sidebar()

    if uploaded is not None:
        file_digest = hashlib.sha256(uploaded.getvalue()).hexdigest()
        signature = f"{uploaded.name}:{uploaded.size}:{file_digest}"
        known_signatures = {st.session_state.loaded_signature, st.session_state.pending_signature}
        if signature not in known_signatures:
            try:
                _stage_data(_read_csv(uploaded), uploaded.name, signature)
            except (ValueError, pd.errors.ParserError) as error:
                st.error(f"We could not process this file: {error}")
                return

    st.markdown(
        """<section class='hero'><div class='eyebrow'>ADMISSIONS WORKSPACE</div>
        <h1>Review every student with confidence.</h1>
        <p>Clean source data, manage eligibility, explore the cohort, and create a transparent shortlist without leaving one focused workspace.</p></section>""",
        unsafe_allow_html=True,
    )

    if st.session_state.pending_data is not None:
        st.markdown("#### Dataset ready to clean")
        st.caption(
            f"**{st.session_state.pending_filename}** contains {len(st.session_state.pending_data):,} rows. "
            "Review its cleaning results before starting your admissions review."
        )
        if st.button("Clean dataset", type="primary", icon="✨"):
            try:
                _load_data(st.session_state.pending_data, st.session_state.pending_signature)
                st.toast("Dataset cleaned. See the cleaning results below.", icon="✅")
                st.rerun()
            except ValueError as error:
                st.error(f"We could not clean this file: {error}")
        return

    if st.session_state.cleaned_data is None:
        st.info("Upload a student CSV to get started, or use the sample data to explore the workspace.")
        st.markdown("#### Your review flow")
        first, second, third = st.columns(3)
        first.markdown("**1. Clean**  \nChoose when to clean your uploaded data, then review every correction.")
        second.markdown("**2. Review**  \nSearch the roster and update eligibility as decisions are made.")
        third.markdown("**3. Shortlist**  \nApply fair, visible criteria and export a ranked list for review.")
        return

    data = _sort_by_grade(apply_statuses(st.session_state.cleaned_data, st.session_state.statuses))
    _show_overview(data)
    _show_report(data, st.session_state.report)

    overview_tab, roster_tab, shortlist_tab = st.tabs(["Overview", "Roster & eligibility", "Shortlist builder"])
    with overview_tab:
        heading, reset = st.columns((4, 1))
        heading.markdown("#### Quick cohort filter")
        reset.button(
            "Clear overview filters",
            key="clear_overview_filters",
            on_click=_clear_roster_filters,
            args=("overview",),
            disabled=not _roster_filters_are_active("overview"),
            width="stretch",
        )
        overview_data = _filter_roster(data, "overview")
        st.caption(f"Showing {len(overview_data):,} of {len(data):,} students.")
        if _roster_filters_are_active("overview"):
            st.info(
                "These filters only narrow the Overview table. Clear them to compare every shortlisted student."
            )
        overview_page, first_row, last_row = _paginate(overview_data, "overview")
        if first_row:
            st.caption(f"Displaying rows {first_row:,}–{last_row:,}.")
        st.dataframe(
            overview_page.drop(columns=["Student ID"]), hide_index=True, width="stretch", height=360,
            column_config={"Total": st.column_config.NumberColumn(format="%.0f / 300")},
        )

    with roster_tab:
        heading, reset = st.columns((4, 1))
        heading.markdown("#### Review the roster")
        reset.button(
            "Clear roster filters",
            key="clear_roster_filters",
            on_click=_clear_roster_filters,
            args=("roster",),
            disabled=not _roster_filters_are_active("roster"),
            width="stretch",
        )
        st.caption("Use the Active checkbox to include a student in shortlists; uncheck it to debar them immediately.")
        roster_data = _filter_roster(data, "roster")
        st.caption(f"Showing {len(roster_data):,} of {len(data):,} students.")
        roster_page, first_row, last_row = _paginate(roster_data, "roster")
        if first_row:
            st.caption(f"Editing rows {first_row:,}–{last_row:,}. Use search and filters to locate any student.")
        _status_editor(roster_page)
        st.download_button(
            "Download filtered roster", data=_csv_bytes(roster_data), file_name="student_roster.csv", mime="text/csv",
            disabled=roster_data.empty,
        )

    current_data = _sort_by_grade(apply_statuses(st.session_state.cleaned_data, st.session_state.statuses))
    with shortlist_tab:
        _show_shortlist(current_data)


if __name__ == "__main__":
    main()
