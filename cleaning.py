"""Deterministic CSV cleaning utilities for the Student Selection Dashboard."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd


REQUIRED_COLUMNS = ("Name", "Gender", "Grade", "Math", "Science", "English", "Total")
SUBJECTS = ("Math", "Science", "English")
ACTIVE_STATUS = "Active"
DEBARRED_STATUS = "Debarred"
VALID_STATUSES = frozenset((ACTIVE_STATUS, DEBARRED_STATUS))

_COLUMN_ALIASES = {
    "name": "Name", "student name": "Name", "full name": "Name",
    "gender": "Gender", "sex": "Gender",
    "grade": "Grade", "class": "Grade", "class grade": "Grade", "standard": "Grade",
    "math": "Math", "maths": "Math", "mathematics": "Math",
    "science": "Science", "sci": "Science",
    "english": "English", "eng": "English",
    "total": "Total", "total score": "Total", "total marks": "Total",
}

_GENDER_MAP = {
    "m": "Male", "male": "Male", "boy": "Male", "1": "Male",
    "f": "Female", "female": "Female", "girl": "Female", "0": "Female",
    "non binary": "Non-binary", "nonbinary": "Non-binary", "nb": "Non-binary",
    "other": "Other", "prefer not to say": "Unspecified", "": "Unspecified",
}
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
          "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}


@dataclass(frozen=True)
class CleaningReport:
    """An audit-friendly summary of transformations applied to a file."""

    source_rows: int
    output_rows: int
    blank_rows_removed: int
    duplicate_rows_removed: int
    invalid_scores_repaired: int
    missing_scores_imputed: int
    totals_recalculated: int
    normalised_values: int


def _clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    # Common spreadsheet exports can preserve quote characters around a name.
    text = re.sub(r"^[\"']+|[\"']+$", "", text).strip()
    return re.sub(r"\s+", " ", text)


def _column_key(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean_text(value).casefold())


def canonicalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Map forgiving header variants to the schema and reject ambiguous inputs."""
    renamed: dict[str, str] = {}
    used: set[str] = set()
    for column in frame.columns:
        target = _COLUMN_ALIASES.get(_column_key(column))
        if target:
            if target in used:
                raise ValueError(f"More than one column maps to '{target}'. Keep only one.")
            renamed[column] = target
            used.add(target)
    result = frame.rename(columns=renamed)
    missing = [name for name in REQUIRED_COLUMNS if name not in result.columns]
    if missing:
        raise ValueError("Missing required column(s): " + ", ".join(missing))
    return result.loc[:, REQUIRED_COLUMNS].copy()


def _normalise_name(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return "Unknown student"
    # title() handles inconsistent casing while preserving hyphens and apostrophes well enough.
    return text.title()


def _normalise_gender(value: Any) -> str:
    text = _clean_text(value).casefold().replace("-", " ")
    return _GENDER_MAP.get(text, "Unspecified")


def _normalise_grade(value: Any) -> str:
    text = _clean_text(value).casefold()
    text = re.sub(r"^(grade|class|standard)\s*", "", text).strip(" .")
    number = _ROMAN.get(text)
    if number is None:
        match = re.search(r"\d{1,2}", text)
        number = int(match.group()) if match else None
    if number is None or not 1 <= number <= 12:
        return "Unspecified"
    return f"Grade {number}"


def grade_sort_key(grade: object) -> int | float:
    """Return a numeric sort key for a normalised grade label."""
    match = re.fullmatch(r"Grade (\d+)", str(grade))
    return int(match.group(1)) if match else float("inf")


def _parse_score(value: Any) -> float | None:
    _, score = _score_issue(value)
    return score


def _score_issue(value: Any) -> tuple[str, float | None]:
    """Classify a score value before it is repaired."""
    text = _clean_text(value).casefold().replace(",", "")
    if not text or text in {"na", "n/a", "none", "null", "-"}:
        return "missing", None
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(?:\s+marks?)?", text)
    if not match:
        return "invalid", None
    score = float(match.group(1))
    return ("valid", score) if 0 <= score <= 100 else ("invalid", None)


def _parse_total(value: Any) -> float | None:
    """Parse an optional supplied total. Totals have a 0-300, not 0-100, range."""
    text = _clean_text(value).casefold().replace(",", "")
    if not text or text in {"na", "n/a", "none", "null", "-"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    total = float(match.group())
    return total if 0 <= total <= 300 else None


def _student_id(row: pd.Series) -> str:
    stable = "|".join(str(row[column]) for column in ("Name", "Gender", "Grade", *SUBJECTS))
    return hashlib.sha1(stable.encode("utf-8")).hexdigest()[:12]


def clean_student_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Clean a student file and return display-ready records plus a transformation report.

    Scores outside 0-100 and empty/non-numeric scores become missing values. Missing
    subject scores are filled with that subject's valid-file median (or 0 when an
    entire subject column is invalid). Total is always calculated from cleaned scores.
    Duplicate cleaned records retain the first record deterministically.
    """
    source_rows = len(raw)
    data = canonicalise_columns(raw)
    data = data.dropna(how="all")
    blank_rows_removed = source_rows - len(data)

    original = data.copy(deep=True)
    data["Name"] = data["Name"].map(_normalise_name)
    data["Gender"] = data["Gender"].map(_normalise_gender)
    data["Grade"] = data["Grade"].map(_normalise_grade)
    normalised_values = sum(
        int((original[column].map(_clean_text) != data[column]).sum())
        for column in ("Name", "Gender", "Grade")
    )

    score_issues = pd.DataFrame({subject: data[subject].map(_score_issue) for subject in SUBJECTS})
    parsed = pd.DataFrame({subject: score_issues[subject].map(lambda result: result[1]) for subject in SUBJECTS})
    missing_scores_imputed = int(sum(
        (score_issues[subject].map(lambda result: result[0]) == "missing").sum() for subject in SUBJECTS
    ))
    invalid_scores_repaired = int(sum(
        (score_issues[subject].map(lambda result: result[0]) == "invalid").sum() for subject in SUBJECTS
    ))
    for subject in SUBJECTS:
        median = parsed[subject].median(skipna=True)
        parsed[subject] = parsed[subject].fillna(0 if pd.isna(median) else round(float(median), 2))
    data[list(SUBJECTS)] = parsed

    supplied_total = data["Total"].map(_parse_total)
    computed_total = data[list(SUBJECTS)].sum(axis=1).round(2)
    totals_recalculated = int((supplied_total.isna() | (supplied_total != computed_total)).sum())
    data["Total"] = computed_total

    # Use full cleaned records for de-duplication. A name/grade/gender alone is not
    # enough evidence: a source may legitimately contain different assessment rows
    # for two students sharing these attributes. This is deliberately conservative.
    before_dedup = len(data)
    data = data.drop_duplicates(subset=["Name", "Gender", "Grade", *SUBJECTS], keep="first")
    duplicate_rows_removed = before_dedup - len(data)

    data["Student ID"] = data.apply(_student_id, axis=1)
    data["Status"] = ACTIVE_STATUS
    data = data[["Student ID", "Name", "Gender", "Grade", *SUBJECTS, "Total", "Status"]]
    data[list(SUBJECTS) + ["Total"]] = data[list(SUBJECTS) + ["Total"]].round(2)
    data = (
        data.assign(_grade_order=data["Grade"].map(grade_sort_key))
        .sort_values(["_grade_order", "Name"], kind="stable")
        .drop(columns="_grade_order")
        .reset_index(drop=True)
    )

    report = CleaningReport(
        source_rows=source_rows, output_rows=len(data), blank_rows_removed=blank_rows_removed,
        duplicate_rows_removed=duplicate_rows_removed, invalid_scores_repaired=invalid_scores_repaired,
        missing_scores_imputed=missing_scores_imputed, totals_recalculated=totals_recalculated,
        normalised_values=normalised_values,
    )
    return data, report


def apply_statuses(data: pd.DataFrame, statuses: Mapping[str, str]) -> pd.DataFrame:
    """Apply session-only student status selections by stable student ID."""
    invalid_statuses = set(statuses.values()).difference(VALID_STATUSES)
    if invalid_statuses:
        raise ValueError("Unknown student status: " + ", ".join(sorted(invalid_statuses)))
    result = data.copy()
    result["Status"] = result["Student ID"].map(statuses).fillna(ACTIVE_STATUS)
    return result


def shortlist(data: pd.DataFrame, minimum_total: float) -> pd.DataFrame:
    """Return only active students who meet the inclusive total threshold."""
    return data.loc[(data["Status"] == ACTIVE_STATUS) & (data["Total"] >= minimum_total)].copy()
