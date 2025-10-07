from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def backfill_fr_monthly_dataframe(
    fr_months_df: Optional[pd.DataFrame],
    *,
    start_period: Optional[pd.Period] = None,
    end_period: Optional[pd.Period] = None,
) -> pd.DataFrame:
    """Return FR monthly data covering the requested period range, filling gaps with averages."""
    if fr_months_df is None:
        return pd.DataFrame()

    df = fr_months_df.copy()
    if df.empty:
        return df

    if "month_period" in df.columns:
        period_col = df["month_period"]
    elif "month" in df.columns:
        try:
            period_col = pd.PeriodIndex(df["month"], freq="M")
        except Exception:
            period_col = pd.to_datetime(df["month"], errors="coerce").dt.to_period("M")
    else:
        period_col = pd.to_datetime(df.index, errors="coerce").to_series().dt.to_period("M")

    period_col = pd.Series(period_col)
    df["month_period"] = period_col
    df = df.dropna(subset=["month_period"]).sort_values("month_period")

    if df.empty:
        return df

    default_start = df["month_period"].min()
    default_end = df["month_period"].max()

    period_start = start_period if start_period is not None else default_start
    period_end = end_period if end_period is not None else default_end

    if period_start is None or period_end is None:
        return df

    if period_start > period_end:
        period_start, period_end = period_end, period_start

    full_index = pd.period_range(period_start, period_end, freq="M")
    df = df.set_index("month_period").reindex(full_index)
    df.index.name = "month_period"

    numeric_cols = [
        "capacity_revenue_eur",
        "activation_revenue_eur",
        "total_revenue_eur",
        "energy_cost_eur",
        "activation_energy_mwh",
        "hours_in_data",
        "up_slots",
        "down_slots",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in df.columns:
        if col in {"month", "month_period"}:
            continue
        series = df[col]
        if not np.issubdtype(series.dtype, np.number):
            try:
                series = pd.to_numeric(series, errors="coerce")
            except Exception:
                continue
        df[col] = series

    for col in df.columns:
        if col in {"month", "month_period"}:
            continue
        series = df[col]
        if np.issubdtype(series.dtype, np.number):
            valid = series.dropna()
            fill_value = valid.mean() if not valid.empty else 0.0
            df[col] = series.fillna(fill_value)

    if "capacity_revenue_eur" in df.columns and "activation_revenue_eur" in df.columns:
        computed_total = df["capacity_revenue_eur"].fillna(0.0) + df["activation_revenue_eur"].fillna(0.0)
        if "total_revenue_eur" not in df.columns:
            df["total_revenue_eur"] = computed_total
        else:
            df["total_revenue_eur"] = df["total_revenue_eur"].fillna(computed_total)

    df = df.reset_index()
    df.rename(columns={"index": "month_period"}, inplace=True)
    df["month"] = df["month_period"].astype(str)

    return df


def read_calendar_df(src: Optional[object]) -> Optional[pd.DataFrame]:
    """Read an availability calendar from a path string or an uploaded file-like object."""
    if not src:
        return None
    try:
        if hasattr(src, "read"):
            data = src.read()
            buffer = io.BytesIO(data)
            try:
                df = pd.read_csv(buffer)
            except Exception:
                buffer.seek(0)
                df = pd.read_excel(buffer)
            return df
        path = Path(str(src))
        if not path.exists():
            return None
        if path.suffix.lower() in (".xlsx", ".xls"):
            return pd.read_excel(path)
        return pd.read_csv(path)
    except Exception:
        return None


def normalize_calendar_df(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Normalise calendar data to date/slot plus availability columns."""
    if df is None or df.empty:
        return None
    df2 = df.copy()
    cols = {str(col).strip().lower(): col for col in df2.columns}
    date_col = None
    slot_col = None
    avail_mw_col = None
    avail_col = None
    for key in ["date", "data", "day"]:
        if key in cols:
            date_col = cols[key]
            break
    for key in ["slot", "index", "quarter", "interval index"]:
        if key in cols:
            slot_col = cols[key]
            break
    for key in ["available_mw", "avail_mw", "mw", "capacity_mw"]:
        if key in cols:
            avail_mw_col = cols[key]
            break
    for key in ["available", "avail", "flag"]:
        if key in cols:
            avail_col = cols[key]
            break

    if date_col is None or slot_col is None:
        for column in df2.columns:
            if pd.api.types.is_datetime64_any_dtype(df2[column]):
                date_col = column
                df2["date"] = pd.to_datetime(df2[column]).dt.date.astype(str)
                df2["slot"] = (
                    pd.to_datetime(df2[column]).dt.hour * 4
                    + (pd.to_datetime(df2[column]).dt.minute // 15)
                )
                break
    if "date" not in df2.columns and date_col:
        df2["date"] = pd.to_datetime(df2[date_col], errors="coerce").dt.date.astype(str)
    if "slot" not in df2.columns and slot_col:
        df2["slot"] = pd.to_numeric(df2[slot_col], errors="coerce")

    keep = ["date", "slot"]
    if avail_mw_col and avail_mw_col in df2.columns:
        df2["available_mw"] = pd.to_numeric(df2[avail_mw_col], errors="coerce")
        keep.append("available_mw")
    if avail_col and avail_col in df2.columns and "available_mw" not in df2.columns:
        df2["available"] = df2[avail_col].astype(int)
        keep.append("available")

    df2 = df2.dropna(subset=["date", "slot"])
    df2["slot"] = df2["slot"].astype(int)
    return df2[keep]


__all__ = [
    "backfill_fr_monthly_dataframe",
    "read_calendar_df",
    "normalize_calendar_df",
]
