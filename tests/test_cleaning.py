import pandas as pd
import pytest

from cleaning import apply_statuses, clean_student_data, shortlist


def source(rows):
    return pd.DataFrame(rows, columns=["Name", "Gender", "Grade", "Math", "Science", "English", "Total"])


def test_normalises_values_and_recalculates_total():
    cleaned, report = clean_student_data(source([["  rOhAn' ", "f", "class III", "20 marks", "30", "40", "5"]]))
    row = cleaned.iloc[0]
    assert (row["Name"], row["Gender"], row["Grade"]) == ("Rohan", "Female", "Grade 3")
    assert (row["Math"], row["Science"], row["English"], row["Total"]) == (20.0, 30.0, 40.0, 90.0)
    assert report.totals_recalculated == 1


def test_invalid_and_missing_scores_use_subject_median():
    cleaned, report = clean_student_data(source([
        ["A", "M", "1", "10", "20", "30", "60"],
        ["B", "F", "1", "bad", "150", "", "0"],
        ["C", "F", "1", "30", "40", "50", "120"],
    ]))
    row = cleaned.loc[cleaned["Name"] == "B"].iloc[0]
    assert (row["Math"], row["Science"], row["English"]) == (20.0, 30.0, 40.0)
    assert row["Total"] == 90.0
    assert report.invalid_scores_repaired == 2
    assert report.missing_scores_imputed == 1


def test_rejects_numbers_embedded_in_invalid_score_text():
    cleaned, report = clean_student_data(source([
        ["A", "M", "1", "42", "20", "30", "92"],
        ["B", "F", "1", "score 99", "20", "30", "149"],
    ]))

    assert cleaned.loc[cleaned["Name"] == "B", "Math"].iloc[0] == 42.0
    assert report.invalid_scores_repaired == 1


def test_deduplicates_normalised_identity():
    cleaned, report = clean_student_data(source([
        ["Aditi", "F", "Grade 5", "10", "20", "30", "60"],
        [" aditi ", "female", "5", "10", "20", "30", "60"],
    ]))
    assert len(cleaned) == 1
    assert report.duplicate_rows_removed == 1


def test_sorts_grades_numerically_with_unspecified_last():
    cleaned, _ = clean_student_data(source([
        ["Ten", "M", "10", "10", "20", "30", "60"],
        ["Two", "F", "2", "10", "20", "30", "60"],
        ["One", "F", "1", "10", "20", "30", "60"],
        ["Unknown", "F", "", "10", "20", "30", "60"],
    ]))
    assert list(cleaned["Grade"]) == ["Grade 1", "Grade 2", "Grade 10", "Unspecified"]


def test_shortlist_excludes_debarred():
    cleaned, _ = clean_student_data(source([
        ["A", "M", "1", "100", "100", "100", "300"],
        ["B", "F", "1", "100", "90", "90", "280"],
    ]))
    cleaned.loc[cleaned["Name"] == "A", "Status"] = "Debarred"
    assert list(shortlist(cleaned, 250)["Name"]) == ["B"]


def test_apply_statuses_defaults_unedited_students_to_active():
    cleaned, _ = clean_student_data(source([
        ["A", "M", "1", "100", "100", "100", "300"],
        ["B", "F", "1", "100", "90", "90", "280"],
    ]))
    first_student_id = cleaned.iloc[0]["Student ID"]

    updated = apply_statuses(cleaned, {first_student_id: "Debarred"})

    assert list(updated["Status"]) == ["Debarred", "Active"]


def test_reactivated_student_returns_to_the_live_threshold_shortlist():
    cleaned, _ = clean_student_data(source([
        ["A", "M", "1", "100", "100", "100", "300"],
        ["B", "F", "1", "100", "90", "90", "280"],
    ]))
    student_id = cleaned.loc[cleaned["Name"] == "A", "Student ID"].iloc[0]

    debarred = apply_statuses(cleaned, {student_id: "Debarred"})
    reactivated = apply_statuses(debarred, {student_id: "Active"})

    assert shortlist(debarred, 290).empty
    assert list(shortlist(reactivated, 290)["Name"]) == ["A"]


def test_rejects_unknown_student_status():
    cleaned, _ = clean_student_data(source([["A", "M", "1", "100", "100", "100", "300"]]))

    with pytest.raises(ValueError, match="Unknown student status"):
        apply_statuses(cleaned, {cleaned.iloc[0]["Student ID"]: "Pending"})


def test_rejects_missing_required_schema():
    with pytest.raises(ValueError, match="Missing required"):
        clean_student_data(pd.DataFrame({"Student": ["A"]}))
