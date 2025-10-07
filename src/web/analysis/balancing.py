from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


def bm_stats(series: pd.Series) -> Dict[str, float]:
    """Return basic descriptive statistics for a price series."""
    return {
        "min": float(series.min()),
        "p10": float(series.quantile(0.10)),
        "median": float(series.median()),
        "p90": float(series.quantile(0.90)),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "std": float(series.std(ddof=0)),
    }


def analyze_romanian_balancing_market(
    bm_series: pd.Series,
    capacity_mwh: float,
) -> Dict:
    """High-level qualitative and quantitative analysis of the balancing market."""
    if bm_series is None or bm_series.empty:
        return {"error": "No balancing market data available"}

    bm_prices = bm_series.to_list()
    analysis = {
        "market_name": "Romanian Balancing Market",
        "operator": "TRANSELECTRICA (TSO)",
        "trading_platform": "TRANSELECTRICA Platform (NOT OPCOM)",
        "opcom_markets": "PZU Day-Ahead, Intraday (arbitrage possible)",
        "transelectrica_markets": "Balancing Market (NO arbitrage)",
        "time_resolution": "15 minutes (imbalance settlement)",
        "market_type": "Real-time Grid Balancing",
        "purpose": "Maintain grid frequency 50Hz ± tolerance",
        "data_points": len(bm_series),
        "avg_imbalance_price_ron_mwh": float(np.mean(bm_prices)),
        "min_imbalance_price_ron_mwh": float(np.min(bm_prices)),
        "max_imbalance_price_ron_mwh": float(np.max(bm_prices)),
        "price_volatility": float(np.std(bm_prices)),
        "price_range_ron_mwh": float(np.max(bm_prices) - np.min(bm_prices)),
        "system_deficit_periods": int(sum(p > 0 for p in bm_prices)),
        "system_surplus_periods": int(sum(p < 0 for p in bm_prices)),
        "balanced_periods": int(sum(p == 0 for p in bm_prices)),
        "imbalance_settlement": True,
        "real_time_operation": True,
        "requires_tso_prequalification": True,
        "minimum_response_time_seconds": 30,
        "grid_frequency_target": "50.0 Hz",
        "arbitrage_trading": False,
        "frequency_regulation_services": True,
    }

    total_periods = len(bm_prices)
    if total_periods > 0:
        analysis["system_imbalance_analysis"] = {
            "deficit_percentage": analysis["system_deficit_periods"] / total_periods * 100,
            "surplus_percentage": analysis["system_surplus_periods"] / total_periods * 100,
            "balanced_percentage": analysis["balanced_periods"] / total_periods * 100,
            "dominant_imbalance": "Generation Deficit"
            if analysis["system_deficit_periods"] > analysis["system_surplus_periods"]
            else "Generation Surplus",
            "grid_stress_indicator": analysis["price_volatility"],
        }

    ron_to_eur = 0.2
    analysis["avg_imbalance_price_eur_mwh"] = analysis["avg_imbalance_price_ron_mwh"] * ron_to_eur
    analysis["min_imbalance_price_eur_mwh"] = analysis["min_imbalance_price_ron_mwh"] * ron_to_eur
    analysis["max_imbalance_price_eur_mwh"] = analysis["max_imbalance_price_ron_mwh"] * ron_to_eur
    analysis["price_range_eur_mwh"] = analysis["price_range_ron_mwh"] * ron_to_eur

    return analysis


def compute_activation_factor_series(
    system_df: pd.DataFrame,
    reference_mw: float,
    *,
    smoothing: Optional[str] = None,
) -> pd.Series:
    """Compute activation duty factors from system imbalance data using empirical utilisation rates."""
    if reference_mw <= 0:
        return pd.Series(dtype=float)
    if system_df is None or system_df.empty:
        return pd.Series(dtype=float)

    df = system_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    if "imbalance_mw" not in df.columns:
        return pd.Series(dtype=float)

    imbalance_intensity = df["imbalance_mw"].abs() / float(reference_mw)

    activation_base = 0.1
    activation_range = 0.85
    scaling_factor = 1.5

    df["activation_factor"] = activation_base + activation_range * np.tanh(scaling_factor * imbalance_intensity)
    df["activation_factor"] = df["activation_factor"].clip(lower=0.0, upper=0.95)

    if smoothing == "monthly":
        df["month"] = df["date"].dt.to_period("M")
        grouped = df.groupby(["month", "slot"])["activation_factor"].mean().reset_index()
        grouped["date"] = grouped["month"].dt.to_timestamp()
        grouped = grouped.drop(columns=["month"])
        df = grouped

    df = df.dropna(subset=["date", "slot", "activation_factor"])
    if df.empty:
        return pd.Series(dtype=float)

    idx = pd.MultiIndex.from_arrays(
        [pd.to_datetime(df["date"]).values, df["slot"].astype(int).values],
        names=["date", "slot"],
    )
    return pd.Series(df["activation_factor"].values, index=idx)


__all__ = [
    "bm_stats",
    "analyze_romanian_balancing_market",
    "compute_activation_factor_series",
]
