
# merge_pages_cli.py
import argparse, io, re
from pathlib import Path
import pandas as pd

def normalize_col(s: str) -> str:
    import re
    return re.sub(r'[\s_]+', '', s or '').strip().casefold()

def find_date_column(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if normalize_col(str(c)) in {"date"}:
            return c
    for c in df.columns:
        ser = pd.to_datetime(df[c], errors="coerce", infer_datetime_format=True)
        if ser.notna().sum() >= max(3, int(0.2 * len(ser))):
            return c
    return df.columns[0] if len(df.columns) else None

ACRONYMS = ["NBC","CNBC","MSNBC","TODAY","SYFY","USA","E!","BRAVO","TELEMUNDO","PEACOCK","OXYGEN","UNIVERSAL"]

def prettify_site(raw: str) -> str:
    import re
    name = Path(raw).name
    name = re.sub(r'\.[A-Za-z0-9]{2,4}$', '', name)
    m = re.search(r'([A-Za-z0-9-]+\.)+[A-Za-z]{2,}', name)
    if m:
        core = m.group(0)
        core = re.sub(r'^www\.', '', core)
        core = core.split('.')[0]
    else:
        core = name
    core = core.replace('_',' ').replace('-',' ')
    core = re.sub(r'(?<=[A-Za-z])(?=[0-9])', ' ', core)
    core = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', core)
    pretty = core.strip().title()
    for ac in ACRONYMS:
        pretty = re.sub(rf'\b{ac.title()}\b', ac, pretty)
    return pretty.strip()

def extract_columns(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as e:
        print(f"{path.name}: failed to read Excel ({e})")
        return None
    if df.empty:
        print(f"{path.name}: empty sheet; skipping.")
        return None
    date_col = find_date_column(df)
    if date_col is None:
        print(f"{path.name}: no date column; skipping.")
        return None
    norm_map = {c: normalize_col(str(c)) for c in df.columns}
    want_not = None
    want_yes = None
    for c, n in norm_map.items():
        if n == "notindexed": want_not = c
        if n == "indexed": want_yes = c
    if want_not is None or want_yes is None:
        for c in df.columns:
            n = normalize_col(str(c))
            if want_not is None and ("notindexed" in n or (("not" in n) and ("indexed" in n))):
                want_not = c
            if want_yes is None and ("indexed" == n or n.endswith("indexed")):
                want_yes = c
    if want_not is None or want_yes is None:
        print(f"{path.name}: missing columns; skipping.")
        return None
    out = df[[date_col, want_not, want_yes]].copy()
    out.rename(columns={date_col:"Date", want_not:"Not indexed", want_yes:"Indexed"}, inplace=True)
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", infer_datetime_format=True)
    site = prettify_site(path.name)
    out.rename(columns={"Not indexed": f"{site} not indexed", "Indexed": f"{site} indexed"}, inplace=True)
    return out

def main():
    ap = argparse.ArgumentParser(description="Merge page indexation spreadsheets")
    ap.add_argument("files", nargs="+", help="Input .xlsx files")
    ap.add_argument("-o","--output", default="merged_page_indexation.csv", help="Output CSV path")
    args = ap.parse_args()

    merged = None
    for f in args.files:
        df = extract_columns(Path(f))
        if df is None: continue
        merged = df if merged is None else pd.merge(merged, df, on="Date", how="outer")
    if merged is None:
        print("No valid files provided.")
        return
    try:
        merged = merged.sort_values(by="Date")
    except Exception:
        pass
    merged.to_csv(args.output, index=False)
    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
