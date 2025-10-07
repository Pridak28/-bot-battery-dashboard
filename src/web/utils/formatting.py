from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd


def _thousands_sep(enabled: bool) -> str:
    return "," if enabled else ""


def format_currency(
    value: Optional[float],
    decimals: int = 0,
    thousands: bool = True,
    symbol: str = "€",
    *,
    tiny_threshold: float = 1.0,
    tiny_decimals: int = 2,
) -> str:
    """Human-friendly currency formatter with small-value preservation."""
    try:
        if value is None or pd.isna(value):
            return "—"
        if abs(value) > 0 and abs(value) < tiny_threshold:
            decimals = max(decimals, tiny_decimals)
        sep = _thousands_sep(thousands)
        return f"{symbol}{value:,.{decimals}f}".replace(",", sep)
    except Exception:
        return str(value)


def format_percent(value: Optional[float], decimals: int = 1, thousands: bool = False) -> str:
    try:
        if value is None or pd.isna(value):
            return "—"
        sep = _thousands_sep(thousands)
        return (f"{value:.{decimals}f}%").replace(",", sep)
    except Exception:
        return str(value)


def get_status_indicator(value: float, metric_type: str = "profit") -> str:
    """Return a concise textual status based on value and metric type."""
    if metric_type == "profit":
        if value > 0:
            return "Positive"
        if value < 0:
            return "Negative"
        return "Neutral"
    if metric_type == "win_rate":
        if value >= 70:
            return "High"
        if value >= 50:
            return "Moderate"
        return "Low"
    if metric_type == "spread":
        if value >= 20:
            return "Outstanding"
        if value >= 10:
            return "Strong"
        if value >= 5:
            return "Moderate"
        return "Attention"
    return ""


def format_price_per_mwh(value: Optional[float], decimals: int = 2) -> str:
    try:
        if value is None or pd.isna(value):
            return "—"
        decimals = max(decimals, 2)
        return f"{format_currency(value, decimals=decimals, thousands=False)}/MWh"
    except Exception:
        return str(value)


def styled_table(
    df: pd.DataFrame,
    *,
    currency_cols: Optional[Iterable[str]] = None,
    percent_cols: Optional[Iterable[str]] = None,
    float_cols: Optional[Iterable[str]] = None,
    currency_decimals: int = 0,
    float_decimals: int = 2,
    thousands: bool = True,
) -> pd.io.formats.style.Styler:
    """Return a Styler with consistent numeric formatting."""
    currency_cols = list(currency_cols or [])
    percent_cols = list(percent_cols or [])
    float_cols = list(float_cols or [])

    fmt: dict[str, object] = {}

    for col in currency_cols:
        if col in df.columns:
            fmt[col] = lambda v, d=currency_decimals, t=thousands: format_currency(v, decimals=d, thousands=t)

    for col in percent_cols:
        if col in df.columns:
            fmt[col] = lambda v, d=1: format_percent(v, decimals=d)

    for col in float_cols:
        if col in df.columns:
            fmt[col] = f"{{:.{float_decimals}f}}"

    return df.style.format(fmt)


def get_chart_colors() -> dict[str, str]:
    """Color palette used by multiple charts."""
    return {
        "primary": "#525252",
        "accent": "#3b82f6",
        "green": "#10b981",
        "emerald": "#10b981",
        "red": "#ef4444",
        "orange": "#f59e0b",
        "darkgreen": "#059669",
        "black": "#000000",
        "white": "#ffffff",
        "grey_light": "#e5e5e5",
    }


__all__ = [
    "format_currency",
    "format_percent",
    "format_price_per_mwh",
    "get_status_indicator",
    "styled_table",
    "get_chart_colors",
]
