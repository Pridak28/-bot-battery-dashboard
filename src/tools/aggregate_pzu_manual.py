from __future__ import annotations
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas as pd


def _read_any(path: Path) -> Optional[pd.DataFrame]:
    try:
        if path.suffix.lower() in (".xlsx", ".xls"):
            return pd.read_excel(path)
        
        # Special handling for OPCOM Romanian CSV format
        if path.suffix.lower() == ".csv":
            # Try to read OPCOM format with special parsing
            try:
                df = _parse_opcom_csv(path)
                if df is not None and not df.empty:
                    return df
            except Exception:
                pass
        
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
        
        # Try reading as binary and checking content
        with open(path, 'rb') as f:
            content = f.read(1000)  # Read first 1000 bytes
            print(f"File {path.name} first 100 bytes: {content[:100]}")
            
        return None
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return None


def _parse_opcom_csv(path: Path) -> Optional[pd.DataFrame]:
    """Parse OPCOM Romanian CSV format with hourly prices"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Extract date from first line: "PIP si volum tranzactionat pentru ziua de livrare: 29/9/2023"
        date_str = None
        if lines and "ziua de livrare:" in lines[0]:
            date_part = lines[0].split("ziua de livrare:")[1].strip().strip('"')
            # Convert from DD/M/YYYY to YYYY-MM-DD
            try:
                day, month, year = date_part.split('/')
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except:
                pass
        
        if not date_str:
            return None
        
        # Find the hourly data section starting with "Zona de tranzactionare"
        hourly_data = []
        in_hourly_section = False
        
        for line in lines:
            line = line.strip().strip('"')
            if "Zona de tranzactionare" in line:
                in_hourly_section = True
                continue
            
            if in_hourly_section and line:
                parts = [p.strip().strip('"') for p in line.split('","')]
                if len(parts) >= 3 and parts[0] == "Romania":
                    try:
                        hour = int(parts[1])  # Interval (1-24)
                        price = float(parts[2].replace(',', '.'))  # Price in Lei/MWh
                        if 1 <= hour <= 24:
                            hourly_data.append({
                                'date': date_str,
                                'hour': hour - 1,  # Convert to 0-23
                                'price': price
                            })
                    except (ValueError, IndexError):
                        continue
        
        if hourly_data:
            df = pd.DataFrame(hourly_data)
            print(f"Parsed OPCOM CSV {path.name}: {len(df)} hourly prices for {date_str}")
            return df
        
        return None
    except Exception as e:
        print(f"Error parsing OPCOM CSV {path}: {e}")
        return None


def _detect_columns(df: pd.DataFrame) -> Tuple[str, str, str]:
    cols = {c.lower().strip(): c for c in df.columns}
    # Possible column names in English/Romanian
    date_candidates = ["date", "data", "delivery_date", "trading day", "zi"]
    hour_candidates = ["hour", "ora", "interval", "he", "hour index"]
    price_candidates = [
        "price", "pret", "preț", "pzu price", "pzu_price", "price eur/mwh", "price ron/mwh",
    ]

    def pick(cands):
        for k in cands:
            if k in cols:
                return cols[k]
        # fallback: try any column that looks numeric for price or time-like for hour
        return None

    dcol = pick(date_candidates)
    hcol = pick(hour_candidates)
    pcol = pick(price_candidates)
    if dcol is None:
        # try to guess if there's a datetime column that includes date and hour; leave hour None
        for c in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[c]):
                dcol = c
                break
    if pcol is None:
        # choose the last numeric column as price
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if num_cols:
            pcol = num_cols[-1]
    if dcol is None or pcol is None:
        raise ValueError("Could not detect essential columns (date/price)")
    return dcol, hcol, pcol


def _normalize(df: pd.DataFrame, dcol: str, hcol: Optional[str], pcol: str) -> pd.DataFrame:
    out = pd.DataFrame()
    if pd.api.types.is_datetime64_any_dtype(df[dcol]):
        dt = pd.to_datetime(df[dcol])
        out["date"] = dt.dt.date.astype(str)
        if hcol is None:
            out["hour"] = dt.dt.hour
        else:
            out["hour"] = _parse_hour(df[hcol])
    else:
        out["date"] = pd.to_datetime(df[dcol], errors="coerce").dt.date.astype(str)
        if hcol is None:
            # if there's also a time column in dataset, try to find it
            time_col = None
            for c in df.columns:
                lc = str(c).lower()
                if lc in ("time", "ora", "hour", "interval") and c != dcol:
                    time_col = c
                    break
            out["hour"] = _parse_hour(df[time_col]) if time_col else 0
        else:
            out["hour"] = _parse_hour(df[hcol])

    out["price"] = pd.to_numeric(df[pcol], errors="coerce")
    out = out.dropna(subset=["date", "hour", "price"])  # type: ignore
    out["hour"] = out["hour"].astype(int)
    out = out[(out["hour"] >= 0) & (out["hour"] <= 23)]
    return out


def _parse_hour(series: pd.Series) -> pd.Series:
    # Accept integers (0..23), strings like "HH" or "HH:MM", or interval labels like "[01-02)"
    def to_hour(v) -> Optional[int]:
        if pd.isna(v):
            return None
        try:
            iv = int(v)
            return iv
        except Exception:
            s = str(v).strip()
            if ":" in s:
                try:
                    hh = int(s.split(":", 1)[0])
                    return hh
                except Exception:
                    return None
            # interval labels like 01-02 or [01-02)
            digits = "".join(ch for ch in s if ch.isdigit())
            if len(digits) >= 2:
                try:
                    return int(digits[:2])
                except Exception:
                    return None
            return None
    return series.map(to_hour)


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
                dcol, hcol, pcol = _detect_columns(df)
                norm = _normalize(df, dcol, hcol, pcol)
                if cutoff is not None:
                    norm = norm[pd.to_datetime(norm["date"]) >= cutoff.date()]
                frames.append(norm)
            except Exception:
                continue
    if not frames:
        return pd.DataFrame(columns=["date", "hour", "price", "currency"])
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.sort_values(["date", "hour"]).drop_duplicates(["date", "hour"], keep="last")
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
    # Add more mappings as needed
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
    ap = argparse.ArgumentParser(description="Aggregate manually downloaded OPCOM PZU files into a unified CSV")
    ap.add_argument("--inputs", nargs="+", required=True, help="One or more directories containing CSV/XLSX files")
    ap.add_argument("--years", type=int, choices=[1, 2, 3], default=None, help="Restrict to last N years")
    ap.add_argument("--since", type=str, default=None, help="Restrict to dates >= YYYY-MM-DD")
    ap.add_argument("--output", type=str, default="data/pzu_history.csv")
    ap.add_argument("--currency-in", type=str, default="RON", help="Input currency (RON/EUR)")
    ap.add_argument("--target-currency", type=str, default="EUR", help="Output currency")
    ap.add_argument("--fx-rate", type=float, default=None, help="If converting RON->EUR, provide RON per 1 EUR (e.g., 4.97)")
    ap.add_argument("--split-years", action="store_true", help="Also write *_1y, *_2y, *_3y files")
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
