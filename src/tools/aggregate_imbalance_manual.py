from __future__ import annotations
import argparse
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import List, Optional, Tuple
import pandas as pd


def _read_any(path: Path) -> Optional[pd.DataFrame]:
    try:
        if path.suffix.lower() in (".xlsx", ".xls"):
            # For complex Excel files, try reading with different skip rows
            for skiprows in [0, 1, 2, 3, 4]:
                try:
                    df = pd.read_excel(path, skiprows=skiprows)
                    if not df.empty and len(df.columns) > 3:
                        print(f"Successfully read {path.name} with skiprows={skiprows}")
                        return df
                except Exception:
                    continue
            return pd.read_excel(path)
        
        # Try multiple encodings and separators for CSV files  
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'windows-1252']
        separators = [',', ';', '\t']
        
        for encoding in encodings:
            for sep in separators:
                try:
                    df = pd.read_csv(path, encoding=encoding, sep=sep)
                    if not df.empty and len(df.columns) > 1:
                        print(f"Successfully read {path.name} with encoding={encoding}, sep='{sep}'")
                        return df
                except Exception:
                    continue
        return None
    except Exception:
        return None


def _detect_columns(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    cols = {str(c).lower().strip(): c for c in df.columns}
    
    # Special handling for export-8.xlsx format with complex headers
    if any("time interval" in str(c).lower() for c in df.columns):
        print("Detected export-8.xlsx format - applying special parsing")
        # Look for time interval column and price columns
        time_col = None
        price_col = None
        freq_col = None
        
        for c in df.columns:
            col_str = str(c).lower()
            if "time interval" in col_str:
                time_col = c
            elif "estimated price" in col_str and ("negative" in col_str or "positive" in col_str):
                price_col = c
            elif any(word in col_str for word in ["frequency", "frecv", "hz"]):
                freq_col = c
        
        # If we found the special format, try to extract from the unnamed columns
        if time_col and not price_col:
            # Look in the first few rows for column headers
            for i in range(min(5, len(df))):
                row = df.iloc[i]
                for j, val in enumerate(row):
                    if isinstance(val, str) and "estimated price" in val.lower():
                        if j < len(df.columns):
                            price_col = df.columns[j]
                            break
        
        return time_col, None, price_col, freq_col
    
    # Original logic for other formats
    date_candidates = ["date", "data", "day", "zi", "delivery date", "datetime", "timestamp"]
    time_candidates = ["time", "ora", "interval", "minute", "timp", "hour"]
    slot_candidates = ["slot", "index", "slot index", "interval index", "quarter"]
    price_candidates = [
        "price", "pret", "preț", "imbalance price", "estimated imbalance price", "pip", "price ron/mwh", "price eur/mwh",
    ]
    freq_candidates = ["frequency", "frecventa", "frecvență", "hz"]

    def pick(cands):
        for k in cands:
            if k in cols:
                return cols[k]
        return None

    dcol = pick(date_candidates)
    tcol = pick(time_candidates)
    scol = pick(slot_candidates)
    pcol = pick(price_candidates)
    fcol = pick(freq_candidates)

    # if datetime column only
    if dcol and pd.api.types.is_datetime64_any_dtype(df[dcol]):
        tcol = tcol or None
    if pcol is None:
        # pick last numeric
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if num_cols:
            pcol = num_cols[-1]
    if (dcol is None and scol is None) or pcol is None:
        raise ValueError("Could not detect essential columns (date/slot and price)")
    return dcol, tcol, pcol, fcol if fcol in df.columns else fcol


def _to_slot_from_time(t: time) -> int:
    return t.hour * 4 + (t.minute // 15)


def _parse_time_to_slot(series: pd.Series) -> pd.Series:
    def parse(v) -> Optional[int]:
        if pd.isna(v):
            return None
        try:
            # if it's already numeric slot
            iv = int(v)
            return iv
        except Exception:
            s = str(v).strip()
            # formats like HH:MM[:SS]
            try:
                parts = s.split(":")
                hh = int(parts[0])
                mm = int(parts[1]) if len(parts) > 1 else 0
                return hh * 4 + (mm // 15)
            except Exception:
                # interval labels like 00:00-00:15 or [00:00-00:15)
                digits = [int(x) for x in "".join(ch if ch.isdigit() else " " for ch in s).split()]
                if len(digits) >= 2:
                    hh, mm = digits[0], digits[1]
                    return hh * 4 + (mm // 15)
                return None
    return series.map(parse)


def _normalize(df: pd.DataFrame, dcol: Optional[str], tcol: Optional[str], pcol: str, fcol: Optional[str]) -> pd.DataFrame:
    out = pd.DataFrame()
    
    # Special handling for export-8.xlsx format
    if any("time interval" in str(c).lower() for c in df.columns):
        print("Processing export-8.xlsx format...")
        # The data starts from row 4 (index 4), first column has time intervals
        # Skip the header rows and get the actual data
        data_rows = []
        
        for i, row in df.iterrows():
            if i < 4:  # Skip header rows
                continue
            
            time_val = row.iloc[0]  # First column has time intervals
            if pd.isna(time_val) or not isinstance(time_val, str):
                continue
                
            # Parse time interval like "1. 6. 2024 0:00 - 1. 6. 2024 0:15"
            if " - " in str(time_val):
                try:
                    start_time = str(time_val).split(" - ")[0].strip()
                    # Extract date and time: "1. 6. 2024 0:00"
                    parts = start_time.split()
                    if len(parts) >= 4:
                        day, month, year = parts[0].rstrip('.'), parts[1].rstrip('.'), parts[2]
                        time_part = parts[3]  # "0:00"
                        
                        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        hh, mm = time_part.split(':')
                        slot = int(hh) * 4 + (int(mm) // 15)
                        
                        # Get price from column 3 (Unnamed: 3) - negative imbalance price
                        price_val = row.iloc[3] if len(row) > 3 else None
                        if pd.notna(price_val) and isinstance(price_val, (int, float)):
                            data_rows.append({
                                'date': date_str,
                                'slot': slot,
                                'price': float(price_val),
                                'frequency': pd.NA
                            })
                except Exception as e:
                    continue
        
        if data_rows:
            result_df = pd.DataFrame(data_rows)
            result_df["slot"] = result_df["slot"].astype(int)
            result_df = result_df[(result_df["slot"] >= 0) & (result_df["slot"] <= 95)]
            print(f"Parsed {len(result_df)} rows from export-8.xlsx")
            return result_df
    
    # Original logic for other formats
    if dcol and pd.api.types.is_datetime64_any_dtype(df[dcol]):
        dt = pd.to_datetime(df[dcol])
        out["date"] = dt.dt.date.astype(str)
        out["slot"] = dt.dt.hour * 4 + (dt.dt.minute // 15)
    else:
        if dcol:
            out["date"] = pd.to_datetime(df[dcol], errors="coerce").dt.date.astype(str)
        else:
            # if no date, try infer from any datetime-like column
            for c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    dt = pd.to_datetime(df[c])
                    out["date"] = dt.dt.date.astype(str)
                    out["slot"] = dt.dt.hour * 4 + (dt.dt.minute // 15)
                    break
        if "slot" not in out.columns:
            if tcol and tcol in df.columns:
                out["slot"] = _parse_time_to_slot(df[tcol])
            else:
                # if dataset already has a slot/index column
                for c in df.columns:
                    lc = str(c).lower()
                    if lc in ("slot", "index", "slot index", "interval index", "quarter"):
                        out["slot"] = pd.to_numeric(df[c], errors="coerce")
                        break
    out["price"] = pd.to_numeric(df[pcol], errors="coerce")
    if fcol and fcol in df.columns:
        out["frequency"] = pd.to_numeric(df[fcol], errors="coerce")
    else:
        out["frequency"] = pd.NA

    out = out.dropna(subset=["date", "slot", "price"])  # type: ignore
    out["slot"] = out["slot"].astype(int)
    out = out[(out["slot"] >= 0) & (out["slot"] <= 95)]
    return out


def aggregate(inputs: List[Path], cutoff: Optional[datetime]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for folder in inputs:
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in (".csv", ".xlsx", ".xls"):
                continue
            df = _read_any(path)
            if df is None or df.empty:
                continue
            try:
                dcol, tcol, pcol, fcol = _detect_columns(df)
                norm = _normalize(df, dcol, tcol, pcol, fcol)
                if cutoff is not None:
                    norm = norm[pd.to_datetime(norm["date"]) >= cutoff.date()]
                frames.append(norm)
            except Exception:
                continue
    if not frames:
        return pd.DataFrame(columns=["date", "slot", "price", "frequency", "currency"])
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.sort_values(["date", "slot"]).drop_duplicates(["date", "slot"], keep="last")
    return all_df


def maybe_convert_currency(df: pd.DataFrame, currency_in: str, target_currency: str, fx_rate: Optional[float]) -> pd.DataFrame:
    df = df.copy()
    if currency_in.upper() == target_currency.upper():
        df["currency"] = target_currency.upper()
        return df
    if currency_in.upper() == "RON" and target_currency.upper() == "EUR":
        if fx_rate is None:
            raise SystemExit("RON->EUR conversion requested but --fx-rate not provided.")
        df["price"] = df["price"].astype(float) / float(fx_rate)
        df["currency"] = target_currency.upper()
        return df
    raise SystemExit(f"Unsupported currency conversion {currency_in}->{target_currency}")


def write_outputs(df: pd.DataFrame, output: Path, split_years: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    if split_years:
        today = datetime.today().date()
        for years in (1, 2, 3):
            cutoff = today - timedelta(days=365 * years)
            sub = df[pd.to_datetime(df["date"]).dt.date >= cutoff]
            out = output.with_name(output.stem + f"_{years}y" + output.suffix)
            sub.to_csv(out, index=False)


def main():
    ap = argparse.ArgumentParser(description="Aggregate manually downloaded Transelectrica estimated imbalance price files into unified 15-min data")
    ap.add_argument("--inputs", nargs="+", required=True, help="Directories with CSV/XLSX files")
    ap.add_argument("--years", type=int, choices=[1, 2, 3], default=None)
    ap.add_argument("--since", type=str, default=None)
    ap.add_argument("--output", type=str, default="data/imbalance_history.csv")
    ap.add_argument("--currency-in", type=str, default="RON")
    ap.add_argument("--target-currency", type=str, default="EUR")
    ap.add_argument("--fx-rate", type=float, default=None)
    ap.add_argument("--split-years", action="store_true")
    args = ap.parse_args()

    cutoff: Optional[datetime] = None
    if args.years is not None:
        cutoff = datetime.today() - timedelta(days=365 * int(args.years))
    if args.since:
        cutoff = max(cutoff, datetime.fromisoformat(args.since)) if cutoff else datetime.fromisoformat(args.since)

    folders = [Path(p) for p in args.inputs]
    df = aggregate(folders, cutoff)
    df = maybe_convert_currency(df, args.currency_in, args.target_currency, args.fx_rate)
    write_outputs(df, Path(args.output), args.split_years)
    print(f"Wrote {len(df)} rows to {args.output}")


if __name__ == "__main__":
    main()
