import pandas as pd

from app import _csv_bytes, _merge_status_updates


def test_csv_export_neutralises_spreadsheet_formulas():
    data = pd.DataFrame(
        {
            "Student ID": ["internal-id"],
            "Name": ["=HYPERLINK(\"https://example.com\")"],
            "Gender": ["Female"],
            "Grade": ["Grade 9"],
            "Math": [90],
            "Science": [91],
            "English": [92],
            "Total": [273],
            "Status": ["Active"],
        }
    )

    exported = _csv_bytes(data).decode("utf-8")

    assert "'=HYPERLINK" in exported
    assert "internal-id" not in exported


def test_status_change_on_one_roster_page_keeps_hidden_student_statuses():
    statuses = {"student-a": "Debarred", "student-b": "Active"}

    updated = _merge_status_updates(statuses, {"student-b": "Debarred"})

    assert updated == {"student-a": "Debarred", "student-b": "Debarred"}


def test_reactivating_a_student_removes_their_session_override():
    updated = _merge_status_updates({"student-a": "Debarred"}, {"student-a": "Active"})

    assert updated == {}
