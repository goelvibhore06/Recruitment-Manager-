# StudentSelect: Data Pipeline & Shortlisting UI

A production-minded Streamlit web interface designed to upload raw student datasets, automatically clean the data, and dynamically filter candidates for administrative shortlisting.

## 🚀 Core Features

* **Data Upload & Auto-Cleaning:** Upload raw CSV files into an automated pipeline that instantly handles duplicates, typos, missing values, and validates/recalculates the Total score column.
* **Interactive Status Management:** Toggle students as "Active" or "Debarred" in real-time. Debarred students are instantly excluded from the live shortlist and minimum score queries without needing to re-upload the dataset.
* **Dynamic Filtering & Export:** Set a minimum total score requirement to generate a live shortlist. The app displays summary statistics (matched count, average scores) and allows you to export the final filtered list as a clean CSV.
* **Privacy & Safety:** Processing happens entirely in application memory. Exported CSVs neutralize text beginning with spreadsheet formula characters for secure downloads.

## 🧹 Dataset Schema & Cleaning Logic

The app expects a CSV with the following columns: **Name, Gender, Grade, Math, Science, English, Total**. 

The auto-cleaning pipeline applies the following logic:

* **Mixed casing & whitespace:** Standardized (e.g., "ROHAN" becomes "Rohan").
* **Gender & Grade variants:** Maps variants to standard formatting (e.g., M to "Male", 11 to "Grade 11").
* **Missing or Invalid Scores:** Replaced with the valid-file median for that subject (or 0 if no valid values exist).
* **Total Column:** Always recalculated precisely as *Math + Science + English*.
* **Exact Duplicates:** Removes repeated records after standardizing demographic fields and scores.

*(Note: An audit panel in the UI exposes exactly what changed during cleaning so the process remains transparent.)*

## 💻 Running the App Locally

**Prerequisites:** Python 3.10 or newer installed on your machine.

1. **Open your terminal** and clone/navigate to this project folder.
2. **Create and activate a virtual environment:**

   **For macOS / Linux:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
