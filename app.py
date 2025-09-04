
import io, re, hashlib, os
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Merge Page Indexation Spreadsheets", layout="wide")
st.title("Merge Page Indexation Spreadsheets")
st.caption("Upload .xlsx files. We'll extract **Date**, **Not indexed**, and **Indexed** from each, label columns by file name, and merge by Date. No data is invented—just a merge.")

def normalize_col(s: str) -> str:
    return re.sub(r'[\s_]+', '', s or '').strip().casefold()

def find_date_column(df: pd.DataFrame) -> str | None:
    # Prefer explicit "date" name
    for c in df.columns:
        if normalize_col(str(c)) in {"date"}:
            return c
    # Next: first datetime-like column
    for c in df.columns:
        ser = pd.to_datetime(df[c], errors="coerce", infer_datetime_format=True)
        if ser.notna().sum() >= max(3, int(0.2 * len(ser))):
            return c
    # Fallback: first column
    return df.columns[0] if len(df.columns) else None

ACRONYMS = ["NBC","CNBC","MSNBC","TODAY","SYFY","USA","E!","BRAVO","TELEMUNDO","PEACOCK","OXYGEN","UNIVERSAL"]

def prettify_site(raw: str) -> str:
    name = Path(raw).name
    name = re.sub(r'\.[A-Za-z0-9]{2,4}$', '', name)  # drop extension
    # Keep part that looks like a domain if present
    m = re.search(r'([A-Za-z0-9-]+\.)+[A-Za-z]{2,}', name)
    if m:
        core = m.group(0)
        core = re.sub(r'^www\.', '', core)
        core = core.split('.')[0]  # second-level only
    else:
        core = name

    core = core.replace('_',' ').replace('-',' ')
    # Insert spaces between camel/PascalCase transitions and digits
    core = re.sub(r'(?<=[A-Za-z])(?=[0-9])', ' ', core)
    core = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', core)

    # Title-case, then restore acronyms
    pretty = core.strip().title()
    for ac in ACRONYMS:
        pretty = re.sub(rf'\b{ac.title()}\b', ac, pretty)
    return pretty.strip()

def extract_columns(xls_bytes: bytes, filename: str) -> pd.DataFrame | None:
    # Read first sheet by default; allow engine to infer
    try:
        df = pd.read_excel(io.BytesIO(xls_bytes), engine="openpyxl")
    except Exception as e:
        st.error(f"{filename}: failed to read Excel ({e})")
        return None

    if df.empty:
        st.warning(f"{filename}: empty sheet; skipping.")
        return None

    date_col = find_date_column(df)
    if date_col is None:
        st.warning(f"{filename}: no date column found; skipping.")
        return None

    # Find 'Not indexed' and 'Indexed' (case-insensitive; spaces/underscores ignored)
    norm_map = {c: normalize_col(str(c)) for c in df.columns}
    inv = {v: k for k, v in norm_map.items()}
    want_not = None
    want_yes = None
    for c, n in norm_map.items():
        if n == "notindexed":
            want_not = c
        if n == "indexed":
            want_yes = c

    if want_not is None or want_yes is None:
        # Try partials like "Pages not indexed", "Total indexed"
        for c in df.columns:
            n = normalize_col(str(c))
            if want_not is None and ("notindexed" in n or (("not" in n) and ("indexed" in n))):
                want_not = c
            if want_yes is None and ("indexed" == n or n.endswith("indexed")):
                want_yes = c

    if want_not is None or want_yes is None:
        st.warning(f"{filename}: missing required columns (need 'Not indexed' and 'Indexed'); skipping.")
        return None

    out = df[[date_col, want_not, want_yes]].copy()
    out.rename(columns={date_col: "Date", want_not: "Not indexed", want_yes: "Indexed"}, inplace=True)

    # Normalize Date to datetime (keep original values if parse fails)
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", infer_datetime_format=True)
    return out

uploaded = st.file_uploader("Upload one or more .xlsx files", type=["xlsx"], accept_multiple_files=True)

if uploaded:
    site_tables = []
    messages = []
    for uf in uploaded:
        data = uf.read()
        site = prettify_site(uf.name)
        df = extract_columns(data, uf.name)
        if df is None:
            continue
        # Rename value columns with site prefix
        df = df.copy()
        df.rename(columns={
            "Not indexed": f"{site} not indexed",
            "Indexed": f"{site} indexed"
        }, inplace=True)
        site_tables.append(df)

    if not site_tables:
        st.stop()

    # Merge on Date (outer), sort by Date
    merged = site_tables[0]
    for nxt in site_tables[1:]:
        merged = pd.merge(merged, nxt, on="Date", how="outer")

    # Sort by Date if parsable
    try:
        merged = merged.sort_values(by="Date")
    except Exception:
        pass

    st.subheader("Preview")
    st.dataframe(merged.head(100), use_container_width=True)

    csv_bytes = merged.to_csv(index=False)
    st.download_button(
        label="Download merged CSV",
        data=csv_bytes,
        file_name="merged_page_indexation.csv",
        mime="text/csv"
    )
else:
    st.info("Upload your Excel files to begin. We'll only merge the columns you provide; nothing is fabricated.")
