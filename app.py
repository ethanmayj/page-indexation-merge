import io
import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Merge Page Indexation Spreadsheets", layout="wide")
st.title("Merge Page Indexation Spreadsheets")
st.caption(
    "Upload .xlsx files. We'll extract **Date**, **Not indexed**, and **Indexed** "
    "from each, label columns by file name, and merge by Date. No data is invented—just a merge."
)


def normalize_col(s: str) -> str:
    return re.sub(r"[\s_]+", "", str(s or "")).strip().casefold()


def to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def find_date_column(df: pd.DataFrame) -> str | None:
    # Prefer an explicitly named Date column
    for c in df.columns:
        if normalize_col(str(c)) == "date":
            return c

    # Otherwise find the first column that looks meaningfully date-like
    for c in df.columns:
        try:
            ser = to_series(df[c])
            parsed = pd.to_datetime(ser, errors="coerce")
            if parsed.notna().sum() >= max(3, int(0.2 * len(ser))):
                return c
        except Exception:
            continue

    # Fallback to first column if present
    return df.columns[0] if len(df.columns) else None


ACRONYMS = [
    "NBC",
    "CNBC",
    "MSNBC",
    "TODAY",
    "SYFY",
    "USA",
    "E!",
    "BRAVO",
    "TELEMUNDO",
    "PEACOCK",
    "OXYGEN",
    "UNIVERSAL",
]


def prettify_site(raw: str) -> str:
    name = Path(raw).name
    name = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", name)

    m = re.search(r"([A-Za-z0-9-]+\.)+[A-Za-z]{2,}", name)
    if m:
        core = m.group(0)
        core = re.sub(r"^www\.", "", core)
        core = core.split(".")[0]
    else:
        core = name

    core = core.replace("_", " ").replace("-", " ")
    core = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", core)
    core = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", core)

    pretty = core.strip().title()
    for ac in ACRONYMS:
        pretty = re.sub(rf"\b{re.escape(ac.title())}\b", ac, pretty)
    return pretty.strip()


def extract_columns(xls_bytes: bytes, filename: str) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(io.BytesIO(xls_bytes), engine="openpyxl")
    except Exception as e:
        st.error(f"{filename}: failed to read Excel ({e})")
        return None

    if df.empty:
        st.warning(f"{filename}: empty sheet; skipping.")
        return None

    # Clean header names
    df.columns = [str(c).strip() for c in df.columns]

    # Drop exact duplicate headers, keep first
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()].copy()

    date_col = find_date_column(df)
    if date_col is None:
        st.warning(f"{filename}: no date column found; skipping.")
        return None

    # Find Not indexed / Indexed columns
    norm_map = {c: normalize_col(str(c)) for c in df.columns}
    want_not = None
    want_yes = None

    for c, n in norm_map.items():
        if n == "notindexed":
            want_not = c
        elif n == "indexed":
            want_yes = c

    if want_not is None or want_yes is None:
        for c, n in norm_map.items():
            if want_not is None and ("notindexed" in n or ("not" in n and "indexed" in n)):
                want_not = c
            if want_yes is None and (n == "indexed" or (n.endswith("indexed") and "not" not in n)):
                want_yes = c

    if want_not is None or want_yes is None:
        st.warning(
            f"{filename}: missing required columns (need 'Not indexed' and 'Indexed'); skipping."
        )
        return None

    # Build output safely as 1D Series objects
    out = pd.DataFrame(
        {
            "Date": to_series(df[date_col]),
            "Not indexed": to_series(df[want_not]),
            "Indexed": to_series(df[want_yes]),
        }
    )

    # Normalize Date
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")

    # Drop rows with bad/missing dates
    out = out.dropna(subset=["Date"]).copy()

    return out


uploaded = st.file_uploader(
    "Upload one or more .xlsx files",
    type=["xlsx"],
    accept_multiple_files=True,
)

if uploaded:
    site_tables = []

    for uf in uploaded:
        data = uf.read()
        site = prettify_site(uf.name)
        df = extract_columns(data, uf.name)

        if df is None:
            continue

        df = df.copy()
        df.rename(
            columns={
                "Not indexed": f"{site} not indexed",
                "Indexed": f"{site} indexed",
            },
            inplace=True,
        )
        site_tables.append(df)

    if not site_tables:
        st.stop()

    merged = site_tables[0]
    for nxt in site_tables[1:]:
        merged = pd.merge(merged, nxt, on="Date", how="outer")

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
        mime="text/csv",
    )
else:
    st.info(
        "Upload your Excel files to begin. We'll only merge the columns you provide; nothing is fabricated."
    )