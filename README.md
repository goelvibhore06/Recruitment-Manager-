# StudentSelect

A production-minded Streamlit dashboard for cleaning raw student-score CSV files, reviewing the cleaned data, managing a student's active/debarred status in real time, and exporting an eligible shortlist.

## Features

- **Upload and validate** CSV files with helpful errors and flexible header aliases (`Maths`, `Class`, and `Total Marks` work too).
- **Clean automatically**: normalises names, gender labels, and grade formats; parses values like `28 marks`; removes blank rows and duplicate student identities; repairs invalid/missing subject scores; and always recalculates the total out of 300.
- **Audit trail** showing exactly what changed during cleaning.
- **Live eligibility management**: setting a student to `Debarred` instantly excludes them from the shortlist without uploading again.
- **Live total-score filtering**, summary metrics, and a clean CSV export.
- **Responsive large-cohort review**: Overview and Roster tables are paginated, while downloads retain all filtered records.
- **Safer exports**: text beginning with spreadsheet formula characters is neutralised in downloaded CSV files.
- **Private by design**: processing happens in application memory; this project has no database or third-party data service.

## Run it in VS Code

1. Install [Python 3.10+](https://www.python.org/downloads/) and open this project folder in VS Code. On macOS, download the current **macOS 64-bit universal2 installer**, complete the installation, then quit and reopen VS Code.
2. In VS Code, press `Cmd+Shift+P`, choose **Python: Select Interpreter**, and select the installed Python 3.10+ interpreter. Confirm it with:

   ```bash
   python3 --version
   ```

   It must print Python 3.10 or newer. The macOS command is normally `python3`, not `python`.
3. Open the integrated terminal and create a virtual environment:

   ```bash
   python3 -m venv .venv
   ```

4. Activate it:

   ```bash
   # macOS / Linux
   source .venv/bin/activate

   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   ```

5. Install dependencies and launch:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   python -m streamlit run app.py
   ```

6. Open the local address printed in the terminal (normally `http://localhost:8501`). Upload your CSV, or select **Load example data** from the sidebar.

## Expected CSV

The input must contain these fields (case and a few common aliases are accepted):

```csv
Name,Gender,Grade,Math,Science,English,Total
Navya,male,11,47,63,74,184
```

`Total` is required for input compatibility but is deliberately recalculated from the three subject marks. Each subject must ultimately be between 0 and 100.

## Cleaning decisions

| Situation | Handling |
| --- | --- |
| Mixed casing, quotes, whitespace | Cleaned and standardised (`ROHAN` becomes `Rohan`) |
| Gender variants | Maps `M`, `male`, `1` to Male and `F`, `female`, `0` to Female; unfamiliar values become Unspecified |
| Grade variants | Converts `11`, `Grade 11`, `Class XI` to `Grade 11` |
| `28 marks` / spaces / commas | Parsed to a numeric score |
| Missing, text, negative, or >100 score | Replaced with the valid-file median for that subject (or 0 if no valid values exist) |
| Incorrect/missing Total | Recalculated from Math + Science + English |
| Exact duplicate record | Removes repeated records after standardising the name, demographic fields, and subject scores. Rows with different scores are preserved. |

The audit panel exposes the counts so this workflow remains reviewable rather than silently changing data.

## Tests

```bash
pytest -q
```

The test suite covers normalisation, total recalculation, invalid-score repair, duplicate removal, active/debarred shortlist exclusion, export safety, and schema validation.

## Deploy on Streamlit Community Cloud

1. Create a new GitHub repository and push this folder to its `main` branch.
2. Visit [share.streamlit.io](https://share.streamlit.io/), sign in with GitHub, and choose **Create app**.
3. Select the repository and branch, then set the main file path to `app.py`.
4. Click **Deploy**. Streamlit installs `requirements.txt` automatically.
5. Add the resulting public URL here after deployment:

   `Live app: https://<your-app-name>.streamlit.app`

No secrets are required. The included `.streamlit/config.toml` sets the visual theme and keeps uploads capped at 20 MB.

## 90-second demo checklist

Record this once the deployed URL is live, then add the link below to this README:

1. Open the app and upload the supplied CSV.
2. Expand **Cleaning audit trail** and point out repaired values, totals, and duplicates.
3. In **Cleaned data & eligibility**, debar one student.
4. Open **Live shortlist**, set a minimum score, and show the count updating.
5. Download the CSV and open it briefly.

`Demo video: add your Loom, YouTube, or screen recording URL here`

## Project structure

```text
app.py                 Streamlit user interface and session state
cleaning.py            Tested, reusable cleaning and shortlist domain logic
tests/test_cleaning.py Unit tests for the pipeline
data/sample_students.csv Safe built-in demo data
.streamlit/config.toml Streamlit configuration for local and cloud use
```

## Important note

This app supports administrative shortlisting, not automated admissions decisions. Use the cleaned data and eligibility setting as a review tool, and retain an appropriate human decision process.
