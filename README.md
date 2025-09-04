
# Page Indexation Merger

A lightweight Streamlit app to merge **page indexation** spreadsheets.

## What it does

- Accepts multiple Excel files (`.xlsx`).
- From each file, pulls the **Date**, **Not indexed**, and **Indexed** columns.
- Uses the **file name** to label columns with the site name, e.g.:
  - `NBCBayArea.com … .xlsx` → `NBC Bay Area not indexed` and `NBC Bay Area indexed`
- Merges everything on **Date** with an outer-join and sorts by Date.
- Exports a single CSV.

## How to run (locally)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Expected spreadsheet format

- Must contain a Date column (any capitalization). If multiple date-like columns exist, the first is used.
- Must contain columns named some variation of **"Not indexed"** and **"Indexed"** (case-insensitive, spaces/underscores ignored).
  - Examples recognized: `Not indexed`, `NOT INDEXED`, `not_indexed`, `Indexed`, `indexed`.

If any of the required columns are missing in a file, that file is skipped with a warning in the UI.
