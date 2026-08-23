<div align="center">

<h1>🎓 Recruitment Manager</h1>

<p><strong>Turn messy student data into a clean, ready-to-act-on shortlist.</strong></p>

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/Tests-pytest-0A9EDC?style=flat-square&logo=pytest&logoColor=white" alt="Tested with pytest" />
  <img src="https://img.shields.io/badge/License-MIT-black?style=flat-square" alt="MIT License" />
</p>

<p>
  <a href="https://goelvibhore06-recruitment-manager--app-fdln7b.streamlit.app/"><strong>🚀 Launch Live App</strong></a>
  &nbsp;·&nbsp;
  <a href="#-demo">🎥 Watch Demo</a>
  &nbsp;·&nbsp;
  <a href="#-dataset-schema">📋 Dataset Schema</a>
</p>

</div>

<br/>

## Overview

**Recruitment Manager** is a production-minded Streamlit application that turns messy, inconsistent student datasets into a reliable shortlisting workflow. Upload a raw CSV, and the app automatically repairs common data-quality issues, then lets administrators filter, manage, and export candidates through a clean interactive interface — all without touching a spreadsheet formula.

## ✨ Features

**Automated data cleaning**
Raw CSVs are run through a validation and repair pipeline that resolves duplicates, inconsistent casing, and missing or invalid values, and recalculates score totals — instantly, on upload.

**Live status management**
Mark students as *Active* or *Debarred* on the fly. Debarred candidates are immediately excluded from shortlists and score queries, with no re-upload required.

**Dynamic shortlisting**
Set a minimum score threshold to generate a live, filtered shortlist. Summary statistics — matched count, average scores — update in real time, and the final list exports as a clean CSV.

**Privacy by design**
All processing happens in application memory. Exported files are sanitized against formula-injection characters for safe, secure downloads.

## 🎥 Demo

*Add a short (≤90s) walkthrough here covering: uploading data, reviewing the cleaned table, applying a minimum score filter, and exporting the shortlist.*

> 📺 **[Watch the demo](#)**

## 📋 Dataset Schema

Recruitment Manager expects a CSV with the following columns:

| Column | Description |
|---|---|
| `Name` | Student full name |
| `Gender` | Standardized on cleaning (e.g. `M` → `Male`) |
| `Grade` | Standardized on cleaning (e.g. `11` → `Grade 11`) |
| `Math` | Numeric score |
| `Science` | Numeric score |
| `English` | Numeric score |
| `Total` | Always recalculated as `Math + Science + English` |

### Cleaning logic

- **Casing & whitespace** — Normalized across all text fields (`ROHAN` → `Rohan`).
- **Gender & Grade variants** — Mapped to a standard format.
- **Missing or invalid scores** — Replaced with the subject's valid-file median (or `0` if no valid values exist).
- **Totals** — Always recomputed from source scores, never trusted from the raw file.
- **Duplicates** — Exact matches removed after standardization.

An in-app audit panel exposes exactly what was changed during cleaning, so the process stays transparent and reviewable.

## 🚀 Quickstart

**Prerequisites:** Python 3.10+

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd recruitment-manager

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\Activate.ps1         # Windows

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Launch the app
python -m streamlit run app.py
```

Open the local address printed in your terminal (usually `http://localhost:8501`). Upload your own CSV, or click **Load example data** in the sidebar to explore the app immediately.

## 🧪 Testing

```bash
pytest -q
```

Covers normalization, total recalculation, invalid-score repair, and schema validation.

## ☁️ Deployment

Fully compatible with [Streamlit Community Cloud](https://share.streamlit.io):

1. Push this repository to GitHub.
2. Link it at [share.streamlit.io](https://share.streamlit.io).
3. Set the main file path to `app.py`.

## ⚠️ Disclaimer

Recruitment Manager is built as an administrative aid for shortlisting candidates. It is strongly recommended to retain a human review process for all final admissions decisions.

---

<div align="center">

Built with Streamlit

</div>
