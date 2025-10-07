"""Analytical helpers for the Streamlit web app."""

from .pzu import (
    analyze_monthly_trends,
    analyze_historical_monthly_trends_only,
    analyze_pzu_best_hours,
    analyze_pzu_best_hours_min_years,
    estimate_pzu_profit_window,
    plan_multi_hour_strategy_from_history,
)
from .finance import (
    calculate_historical_roi_metrics,
    enrich_cycle_stats,
    build_cash_flow_summary,
)
from .balancing import (
    bm_stats,
    analyze_romanian_balancing_market,
    compute_activation_factor_series,
)

__all__ = [
    "analyze_monthly_trends",
    "analyze_historical_monthly_trends_only",
    "analyze_pzu_best_hours",
    "analyze_pzu_best_hours_min_years",
    "estimate_pzu_profit_window",
    "plan_multi_hour_strategy_from_history",
    "calculate_historical_roi_metrics",
    "enrich_cycle_stats",
    "build_cash_flow_summary",
    "bm_stats",
    "analyze_romanian_balancing_market",
    "compute_activation_factor_series",
]
