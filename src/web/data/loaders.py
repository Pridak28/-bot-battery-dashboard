from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st
import yaml

from ...tools.aggregate_imbalance_manual import (
    _detect_columns as _imb_detect_columns,
    _normalize as _imb_normalize,
    _read_any as _imb_read_any,
)
from ..config import project_root


def load_config(path: str) -> dict:
    """Read a YAML configuration file."""
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


@st.cache_data(show_spinner=False)
def load_balancing_day_series(bm_csv: Optional[str], target_date_iso: str) -> Optional[pd.Series]:
    """Return balancing market prices for a specific day."""
    if not bm_csv or not Path(bm_csv).exists():
        return None
    try:
        df = pd.read_csv(bm_csv)
    except Exception:
        return None

    required_cols = {"date", "slot", "price"}
    if not required_cols.issubset(df.columns):
        return None

    sub = df[df["date"] == target_date_iso].sort_values("slot")
    if sub.empty:
        return None

    return pd.Series(sub["price"].to_list())


def _guess_currency_column(df: pd.DataFrame) -> Optional[str]:
    """Return upper-case currency code detected in raw dataframe, if any."""
    currency_like = [
        "currency",
        "moneda",
        "cur",
        "u.m.",
        "unit",
        "currency unit",
        "currency code",
    ]
    cols = {str(c).strip().lower(): c for c in df.columns}
    for key in currency_like:
        if key in cols:
            series = df[cols[key]].astype(str).str.strip()
            non_empty = series[series.str.len() > 0]
            if non_empty.empty:
                continue
            top = non_empty.str.upper().value_counts().idxmax()
            if isinstance(top, str) and len(top) <= 6:
                return top
    return None


@st.cache_data(show_spinner=False)
def load_transelectrica_imbalance_from_excel(
    path_or_dir: str,
    fx_ron_per_eur: float = 5.0,
    declared_currency: Optional[str] = None,
) -> pd.DataFrame:
    """Load Transelectrica imbalance data (Excel or CSV). CSV files with DAMAS columns are returned as-is."""
    path_obj = Path(path_or_dir)
    frames: List[pd.DataFrame] = []

    # Handle CSV files (typically contains DAMAS activation data + full columns)
    if path_obj.is_file() and path_obj.suffix.lower() == '.csv':
        try:
            df = pd.read_csv(path_obj)
            # Check if it's already in the correct format with required columns
            required_cols = {'date', 'slot', 'price_eur_mwh'}
            if required_cols.issubset(df.columns):
                # CSV already formatted with full DAMAS columns - return as-is
                # This preserves afrr_up_activated_mwh, mfrr_down_price_eur, etc.
                return df
            # If CSV doesn't have required columns, fall through to Excel logic
        except Exception:
            pass  # Fall through to try Excel logic

    if path_obj.is_dir():
        for item in path_obj.rglob("*.xls*"):
            try:
                df = _imb_read_any(item)
                if df is None or df.empty:
                    continue
                dcol, tcol, pcol, fcol = _imb_detect_columns(df)
                norm = _imb_normalize(df, dcol, tcol, pcol, fcol)
                detected = _guess_currency_column(df)
                if detected:
                    norm["source_currency"] = detected.upper()
                frames.append(norm)
            except Exception:
                continue
    elif path_obj.is_file():
        df = _imb_read_any(path_obj)
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "slot", "price_eur_mwh"])
        dcol, tcol, pcol, fcol = _imb_detect_columns(df)
        norm = _imb_normalize(df, dcol, tcol, pcol, fcol)
        detected = _guess_currency_column(df)
        if detected:
            norm["source_currency"] = detected.upper()
        frames.append(norm)
    else:
        return pd.DataFrame(columns=["date", "slot", "price_eur_mwh"])

    if not frames:
        return pd.DataFrame(columns=["date", "slot", "price_eur_mwh"])

    non_empty_frames = [frame for frame in frames if not frame.empty]
    if not non_empty_frames:
        return pd.DataFrame(columns=["date", "slot", "price_eur_mwh"])

    out = pd.concat(non_empty_frames, ignore_index=True)
    out = out.sort_values(["date", "slot"]).drop_duplicates(["date", "slot"], keep="last")

    declared = (declared_currency or "").upper().strip()
    if declared not in {"RON", "EUR", ""}:
        declared = ""

    if "source_currency" in out.columns:
        src_cur = out["source_currency"].fillna("").astype(str).str.upper()
    else:
        src_cur = pd.Series([declared or ""] * len(out))

    try:
        fx = float(fx_ron_per_eur)
        if fx == 0:
            fx = 5.0
    except Exception:
        fx = 5.0

    price_numeric = pd.to_numeric(out["price"], errors="coerce")
    ron_aliases = {"RON", "LEI", "RON/MWH", "LEI/MWH"}
    eur_aliases = {"EUR", "EUR/MWH"}

    is_ron = src_cur.isin(ron_aliases)
    is_eur = src_cur.isin(eur_aliases)

    if not is_eur.any() and not is_ron.any():
        if declared == "EUR":
            is_eur = pd.Series([True] * len(out))
        elif declared == "RON":
            is_ron = pd.Series([True] * len(out))

    price_eur = price_numeric.copy()
    if is_ron.any():
        # Reset index to ensure alignment
        is_ron_aligned = is_ron.reindex(price_eur.index, fill_value=False)
        price_eur.loc[is_ron_aligned] = price_numeric.loc[is_ron_aligned] / fx

    original_currency = src_cur.where(
        src_cur != "",
        declared or ("RON" if is_ron.any() and not is_eur.any() else "EUR"),
    )
    out["source_currency"] = original_currency
    out["price_currency"] = "EUR"
    out["price_eur_mwh"] = price_eur
    return out[["date", "slot", "price_eur_mwh", "source_currency", "price_currency"]]


@st.cache_data(show_spinner=False)
def build_hedge_price_curve(
    pzu_csv: Optional[str],
    *,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
    fx_ron_per_eur: float = 5.0,
) -> pd.DataFrame:
    """Return a 15-minute hedge price curve derived from PZU data."""
    empty = pd.DataFrame(columns=["date", "slot", "hedge_price_eur_mwh"])
    if not pzu_csv or not Path(pzu_csv).exists():
        return empty

    try:
        df = pd.read_csv(pzu_csv)
    except Exception:
        return empty

    if "date" not in df.columns or ("hour" not in df.columns and "slot" not in df.columns):
        return empty
    if "price" not in df.columns:
        return empty

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["date", "price"])
    if df.empty:
        return empty

    if start_date is not None:
        try:
            df = df[df["date"] >= pd.Timestamp(start_date)]
        except Exception:
            pass
    if end_date is not None:
        try:
            df = df[df["date"] <= pd.Timestamp(end_date)]
        except Exception:
            pass
    if df.empty:
        return empty

    price_eur = df["price"].copy()
    if "currency" in df.columns:
        currency = df["currency"].astype(str).str.strip().str.upper()
        ron_mask = currency.isin(["RON", "LEI", "RON/MWH", "LEI/MWH"])
        try:
            fx = float(fx_ron_per_eur)
            if fx == 0:
                fx = 5.0
        except Exception:
            fx = 5.0
        price_eur = price_eur.where(~ron_mask, price_eur / fx)
    df["hedge_price_eur_mwh"] = price_eur

    if "slot" in df.columns:
        df["slot"] = pd.to_numeric(df["slot"], errors="coerce")
        df = df.dropna(subset=["slot"])
        if df.empty:
            return empty
        df["slot"] = df["slot"].astype(int)
        out = df[["date", "slot", "hedge_price_eur_mwh"]]
    else:
        df["hour"] = pd.to_numeric(df["hour"], errors="coerce")
        df = df.dropna(subset=["hour"])
        if df.empty:
            return empty
        df = df[(df["hour"] >= 0) & (df["hour"] <= 23)]
        if df.empty:
            return empty
        df["hour"] = df["hour"].astype(int)
        df = df.groupby(["date", "hour"], as_index=False)["hedge_price_eur_mwh"].mean()

        expanded: List[pd.DataFrame] = []
        for offset in range(4):
            tmp = df.copy()
            tmp["slot"] = tmp["hour"] * 4 + offset
            expanded.append(tmp[["date", "slot", "hedge_price_eur_mwh"]])
        if not expanded:
            return empty
        out = pd.concat(expanded, ignore_index=True)

    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out = out.dropna(subset=["date", "slot"])
    if out.empty:
        return empty
    out["slot"] = out["slot"].astype(int).clip(lower=0, upper=95)
    out = out.sort_values(["date", "slot"]).drop_duplicates(["date", "slot"], keep="last")
    return out


@st.cache_data(show_spinner=False)
def load_system_imbalance_from_excel(
    path_or_dir: str,
    target_dates: Optional[pd.DatetimeIndex] = None,
) -> pd.DataFrame:
    """Load Transelectrica system imbalance data and normalise to date/slot/mW."""
    path_obj = Path(path_or_dir)
    targets: List[Path] = []
    if path_obj.is_dir():
        targets = [*path_obj.rglob("*.xls"), *path_obj.rglob("*.xlsx"), *path_obj.rglob("*.csv")]
    elif path_obj.is_file():
        targets = [path_obj]
    else:
        return pd.DataFrame(columns=["date", "slot", "imbalance_mw"])

    frames: List[pd.DataFrame] = []

    for target in targets:
        if target.suffix.lower() == ".xlsx":
            try:
                raw = pd.read_excel(target, skiprows=4)
                lower_cols = [str(c).lower() for c in raw.columns]
                if any("estimated system imbalance" in c for c in lower_cols):
                    tmp = raw.copy()
                    tmp["Time interval"] = tmp["Time interval"].astype(str)
                    split = tmp["Time interval"].str.split(" - ", n=1, expand=True)
                    tmp["start"] = split[0]
                    tmp["date"] = pd.to_datetime(tmp["start"], dayfirst=True, errors="coerce")
                    tmp = tmp.dropna(subset=["date", "ISP"])
                    tmp["slot"] = pd.to_numeric(tmp["ISP"], errors="coerce") - 1
                    tmp = tmp.dropna(subset=["slot"])
                    tmp["slot"] = tmp["slot"].astype(int).clip(lower=0, upper=95)
                    tmp["imbalance_mw"] = pd.to_numeric(
                        tmp.get("Estimated system imbalance [MWh]"), errors="coerce"
                    ) / 0.25
                    frame = tmp[["date", "slot", "imbalance_mw"]].dropna(subset=["imbalance_mw"])
                    frames.append(frame)
                    continue
            except Exception:
                pass

        try:
            df = _imb_read_any(target)
        except Exception:
            continue
        if df is None or df.empty:
            continue

        candidate_col = None
        for column in df.columns:
            lowered = str(column).lower()
            if any(
                key in lowered
                for key in [
                    "imbalance",
                    "dezechilibru",
                    "power system imbalance",
                    "sistem",
                    "desechilibru",
                ]
            ):
                candidate_col = column
                break
        if candidate_col is None:
            num_cols = [column for column in df.columns if pd.api.types.is_numeric_dtype(df[column])]
            if num_cols:
                candidate_col = num_cols[-1]
            else:
                continue

        dcol, tcol, _, _ = _imb_detect_columns(df)
        norm = _imb_normalize(df, dcol, tcol, candidate_col, None)
        if "price" in norm.columns:
            norm = norm.rename(columns={"price": "imbalance_mw"})
        if "imbalance_mw" not in norm.columns:
            if candidate_col in norm.columns:
                norm["imbalance_mw"] = pd.to_numeric(norm[candidate_col], errors="coerce")
            else:
                continue
        frames.append(norm[["date", "slot", "imbalance_mw"]])

    if not frames:
        return pd.DataFrame(columns=["date", "slot", "imbalance_mw"])

    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"])
    out["slot"] = pd.to_numeric(out["slot"], errors="coerce")
    out = out.dropna(subset=["slot"])
    out["slot"] = out["slot"].astype(int).clip(lower=0, upper=95)
    out["imbalance_mw"] = pd.to_numeric(out["imbalance_mw"], errors="coerce")
    out = out.dropna(subset=["imbalance_mw"])
    out = out.sort_values(["date", "slot"]).drop_duplicates(["date", "slot"], keep="last")

    if target_dates is not None and len(target_dates) > 0:
        target_dates = pd.to_datetime(target_dates, errors="coerce").dropna().normalize().unique()
        if len(target_dates) > 0:
            base_idx = pd.MultiIndex.from_product([target_dates, range(96)], names=["date", "slot"])
            base = pd.DataFrame(index=base_idx).reset_index()
            base = base.merge(out, on=["date", "slot"], how="left")
            slot_means = base.groupby("slot")["imbalance_mw"].mean()
            base["imbalance_mw"] = base["imbalance_mw"].fillna(base["slot"].map(slot_means))
            base["imbalance_mw"] = base["imbalance_mw"].fillna(0.0)
            out = base

    out["date"] = out["date"].dt.date.astype(str)
    return out[["date", "slot", "imbalance_mw"]]


def find_in_data_dir(patterns: List[str]) -> Optional[str]:
    """Return first file path in ./data matching any provided pattern."""
    data_dir = project_root / "data"
    if not data_dir.exists():
        return None
    patterns_ci = [pattern.lower() for pattern in patterns]
    for path in data_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if any(re.search(pat, name) for pat in patterns_ci):
            return str(path)
    return None


def list_in_data_dir(patterns: List[str]) -> List[str]:
    """Return all file paths in known roots matching any provided pattern."""
    results: List[str] = []
    roots = [project_root / "data", project_root / "downloads", project_root]
    patterns_ci = [pattern.lower() for pattern in patterns]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            for pattern in patterns_ci:
                try:
                    if re.search(pattern, name):
                        results.append(str(path))
                        break
                except Exception:
                    continue
    seen = set()
    uniq = []
    for item in results:
        if item not in seen:
            uniq.append(item)
            seen.add(item)
    return uniq


def require_data_file(filename: str, *, description: Optional[str] = None) -> Path:
    """
    Return a Path to data/<filename>. If the file is missing, show a user-friendly
    error and halt the Streamlit script. This prevents blank pages on hosted deployments
    when required datasets aren't bundled with the app.
    """
    path = project_root / "data" / filename
    if path.exists():
        return path

    message = f"Required data file not found: {path}"
    if description:
        message += f" — {description}"
    message += (
        ". Add the file to the repository (data/ folder) or update the configuration "
        "before rerunning the app."
    )
    st.error(message)
    st.stop()


def require_any_data_file(
    filenames: List[str],
    *,
    description: Optional[str] = None,
) -> Path:
    """
    Return the first data/<filename> that exists. If none of the provided names exist,
    display a helpful error message and halt execution.
    """
    tried: List[Path] = []
    for name in filenames:
        path = project_root / "data" / name
        tried.append(path)
        if path.exists():
            return path

    message = "None of the required data files were found:\n" + "\n".join(f"- {p}" for p in tried)
    if description:
        message += f"\n{description}"
    else:
        message += "\nAdd one of these files to the repository or update configuration."
    st.error(message)
    st.stop()


@st.cache_data(show_spinner=False)
def parse_battery_specs_from_document(path: str) -> Dict[str, Optional[float]]:
    """Parse a document for headline battery specifications."""
    output: Dict[str, Optional[float]] = {
        "capacity_mwh": None,
        "power_mw": None,
        "round_trip_efficiency": None,
        "soc_min": None,
        "soc_max": None,
    }
    try:
        file_path = Path(path)
        text = ""
        if file_path.suffix.lower() == ".pdf":
            try:
                from pdfminer.high_level import extract_text  # type: ignore

                text = extract_text(path) or ""
            except Exception:
                text = ""
        elif file_path.suffix.lower() in (".txt", ".md"):
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        else:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
        content = text.replace("\n", " ")

        match = re.search(r"(\d{1,3})\s*MW\b", content, re.IGNORECASE)
        if match:
            output["power_mw"] = float(match.group(1))

        match = re.search(r"(\d{1,4})\s*MWh\b", content, re.IGNORECASE)
        if match:
            output["capacity_mwh"] = float(match.group(1))

        match = re.search(r"(round[-\s]?trip|RTE)[^%]{0,30}?(\d{2,3})\s*%", content, re.IGNORECASE)
        if match:
            rte = float(match.group(2)) / 100.0
            if 0 < rte <= 1.0:
                output["round_trip_efficiency"] = rte

        match = re.search(r"SOC\s*min[^0-9]{0,10}(\d{1,2})\s*%", content, re.IGNORECASE)
        if match:
            output["soc_min"] = float(match.group(1)) / 100.0

        match = re.search(r"SOC\s*max[^0-9]{0,10}(\d{1,3})\s*%", content, re.IGNORECASE)
        if match:
            output["soc_max"] = float(match.group(1)) / 100.0

        match = re.search(r"DoD[^0-9]{0,10}(\d{1,3})\s*%", content, re.IGNORECASE)
        if match and output["soc_min"] is None and output["soc_max"] is None:
            dod = float(match.group(1)) / 100.0
            output["soc_min"] = max(0.0, 1.0 - dod)
            output["soc_max"] = 1.0
    except Exception:
        pass
    return output


__all__ = [
    "load_config",
    "load_balancing_day_series",
    "load_transelectrica_imbalance_from_excel",
    "build_hedge_price_curve",
    "load_system_imbalance_from_excel",
    "find_in_data_dir",
    "list_in_data_dir",
    "require_data_file",
    "require_any_data_file",
    "parse_battery_specs_from_document",
]
