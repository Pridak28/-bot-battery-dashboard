from __future__ import annotations
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Fix Python path for module imports
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

import inspect
import pytz
import yaml
import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to prevent React update loops
import matplotlib.pyplot as plt
import numpy as np
import json
import hashlib

from src.data.data_provider import DataProvider
try:
    from src.strategy.horizon import (
        compute_best_fixed_cycle,
        load_pzu_daily_history,
        load_pzu_price_series,
        compute_best_hours_by_year,
        compute_pzu_monthly_costs,
        summarize_profit_windows,
    )
except ImportError:
    from src.strategy.horizon import (  # type: ignore
        compute_best_fixed_cycle,
        load_pzu_daily_history,
        compute_best_hours_by_year,
        compute_pzu_monthly_costs,
        summarize_profit_windows,
    )

    def load_pzu_price_series(*_args, **_kwargs):  # type: ignore
        return pd.DataFrame(columns=["date", "avg_price_eur_mwh"])
from src.tools.aggregate_imbalance_manual import (
    _read_any as _imb_read_any,
    _detect_columns as _imb_detect_columns,
    _normalize as _imb_normalize,
)
import io
import re
import math

# ---------- Display helpers ----------
def _thousands_sep(enabled: bool) -> str:
    return "," if enabled else ""

def format_currency(
    value: float,
    decimals: int = 0,
    thousands: bool = True,
    symbol: str = "€",
    *,
    tiny_threshold: float = 1.0,
    tiny_decimals: int = 2,
) -> str:
    try:
        if value is None or pd.isna(value):
            return "—"
        # Preserve cents for small absolute values so non-zero amounts do not round to €0.
        if abs(value) > 0 and abs(value) < tiny_threshold:
            decimals = max(decimals, tiny_decimals)
        sep = _thousands_sep(thousands)
        return f"{symbol}{value:,.{decimals}f}".replace(",", sep)
    except Exception:
        return str(value)

def format_percent(value: float, decimals: int = 1, thousands: bool = False) -> str:
    try:
        if value is None or pd.isna(value):
            return "—"
        sep = _thousands_sep(thousands)
        return (f"{value:.{decimals}f}%").replace(",", sep)
    except Exception:
        return str(value)


def format_price_per_mwh(value: float, decimals: int = 2) -> str:
    """Format a €/MWh value while preserving cents."""
    try:
        if value is None or pd.isna(value):
            return "—"
        decimals = max(decimals, 2)
        return f"{format_currency(value, decimals=decimals, thousands=False)}/MWh"
    except Exception:
        return str(value)


def _sanitize_session_value(value):
    """Convert values to session-safe equivalents (no NaNs, numpy scalars, or Period types)."""
    try:
        if isinstance(value, dict):
            return {k: _sanitize_session_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_sanitize_session_value(v) for v in value]
        if isinstance(value, tuple):
            return tuple(_sanitize_session_value(v) for v in value)
        if isinstance(value, pd.DataFrame):
            return value.to_dict(orient="records")
        if isinstance(value, pd.Series):
            return value.to_list()
        if value is pd.NaT:
            return None
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        if isinstance(value, pd.Period):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            value = float(value)
            return None if math.isnan(value) else value
        if isinstance(value, float):
            return None if math.isnan(value) else value
        return value
    except Exception:
        return value


def safe_session_state_update(key: str, new_value: dict) -> None:
    """Update Streamlit session state without triggering rerun loops."""
    try:
        sanitized = _sanitize_session_value(new_value)
        new_hash = hashlib.md5(
            json.dumps(sanitized, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        hash_key = f"{key}_hash"
        if (
            st.session_state.get(hash_key) != new_hash
            or key not in st.session_state
        ):
            st.session_state[key] = sanitized
            st.session_state[hash_key] = new_hash
    except Exception:
        st.session_state[key] = new_value



def enrich_cycle_stats(stats: Optional[dict], history: Optional[pd.DataFrame]) -> dict:
    """Fill in missing spread/cost metrics using the available daily history."""
    stats = dict(stats or {})
    if history is None or history.empty:
        return stats

    total_cost = stats.get("total_cost_eur")
    if total_cost is None:
        total_cost = float(history.get("daily_cost_eur", pd.Series(dtype=float)).sum())
        stats["total_cost_eur"] = total_cost

    total_revenue = stats.get("total_revenue_eur")
    if total_revenue is None:
        total_revenue = float(history.get("daily_revenue_eur", pd.Series(dtype=float)).sum())
        stats["total_revenue_eur"] = total_revenue

    if "total_loss_eur" not in stats:
        losing_mask = history.get("daily_profit_eur") < 0 if "daily_profit_eur" in history else None
        if losing_mask is not None:
            loss = float(-history.loc[losing_mask, "daily_profit_eur"].sum())
            stats["total_loss_eur"] = abs(loss)

    charge_energy = None
    discharge_energy = None
    if "charge_energy_mwh" in history:
        charge_energy = float(history["charge_energy_mwh"].sum())
    if "discharge_energy_mwh" in history:
        discharge_energy = float(history["discharge_energy_mwh"].sum())

    if stats.get("avg_buy_price_eur_mwh") is None and charge_energy and charge_energy > 0:
        stats["avg_buy_price_eur_mwh"] = float(total_cost / charge_energy) if total_cost is not None else None

    if stats.get("avg_sell_price_eur_mwh") is None and discharge_energy and discharge_energy > 0:
        stats["avg_sell_price_eur_mwh"] = (
            float(total_revenue / discharge_energy) if total_revenue is not None else None
        )

    buy_price = stats.get("avg_buy_price_eur_mwh")
    sell_price = stats.get("avg_sell_price_eur_mwh")
    if stats.get("spread_eur_mwh") is None and buy_price is not None and sell_price is not None:
        stats["spread_eur_mwh"] = float(sell_price - buy_price)

    return stats


def build_cash_flow_summary(
    history: Optional[pd.DataFrame],
    years: int = 3,
    include_total: bool = True,
    freq: str = "Y",
) -> pd.DataFrame:
    """Aggregate cash-flow metrics over the most recent periods.

    Parameters
    ----------
    history : DataFrame with daily_profit_eur/daily_cost_eur columns
    years : int
        Number of years to cover. For monthly summaries this translates to
        ``years * 12`` periods.
    include_total : bool
        Append a final total row.
    freq : str
        "Y" for yearly aggregation (default) or "M" for monthly aggregation.
    """
    if history is None or (isinstance(history, pd.DataFrame) and history.empty):
        return pd.DataFrame(columns=[
            "Year" if freq.upper() == "Y" else "Month",
            "Days",
            "Turnover €",
            "Cost €",
            "Profit €",
            "Loss €",
            "Avg buy €/MWh",
            "Avg sell €/MWh",
            "Spread €/MWh",
        ])

    working = history.copy()
    if "date" not in working:
        return pd.DataFrame()

    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["date"])
    if working.empty:
        return pd.DataFrame()

    freq = (freq or "Y").upper()
    period_key = "year" if freq == "Y" else "period"
    working[period_key] = working["date"].dt.to_period("Y" if freq == "Y" else "M")

    periods_available = sorted(working[period_key].unique())
    if not periods_available:
        return pd.DataFrame()

    if freq == "Y":
        selected_periods = periods_available[-years:]
    else:
        selected_periods = periods_available[-years * 12 :]

    working = working[working[period_key].isin(selected_periods)]
    if working.empty:
        return pd.DataFrame()

    rows = []
    for period in selected_periods:
        period_df = working[working[period_key] == period]
        if period_df.empty:
            continue

        revenue = float(period_df.get("daily_revenue_eur", pd.Series(dtype=float)).sum())
        cost = float(period_df.get("daily_cost_eur", pd.Series(dtype=float)).sum())
        profit = float(period_df.get("daily_profit_eur", pd.Series(dtype=float)).sum())
        loss = float(-period_df.loc[period_df.get("daily_profit_eur", pd.Series(dtype=float)) < 0, "daily_profit_eur"].sum())
        loss = abs(loss)

        charge_energy = (
            float(period_df.get("charge_energy_mwh", pd.Series(dtype=float)).sum())
            if "charge_energy_mwh" in period_df
            else 0.0
        )
        discharge_energy = (
            float(period_df.get("discharge_energy_mwh", pd.Series(dtype=float)).sum())
            if "discharge_energy_mwh" in period_df
            else 0.0
        )

        avg_buy = float(cost / charge_energy) if charge_energy > 0 else None
        avg_sell = float(revenue / discharge_energy) if discharge_energy > 0 else None
        spread = float(avg_sell - avg_buy) if avg_buy is not None and avg_sell is not None else None

        label_key = "Year" if freq == "Y" else "Month"
        label_value = str(period) if freq == "M" else str(int(period.year))

        rows.append(
            {
                label_key: label_value,
                "Days": int(len(period_df)),
                "Turnover €": revenue,
                "Cost €": cost,
                "Profit €": profit,
                "Loss €": loss,
                "Avg buy €/MWh": avg_buy,
                "Avg sell €/MWh": avg_sell,
                "Spread €/MWh": spread,
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    if include_total and not df.empty:
        label_key = "Year" if freq == "Y" else "Month"
        total_row = {
            label_key: "Total",
            "Days": int(df["Days"].sum()),
            "Turnover €": float(df["Turnover €"].sum()),
            "Cost €": float(df["Cost €"].sum()),
            "Profit €": float(df["Profit €"].sum()),
            "Loss €": float(df["Loss €"].sum()),
            "Avg buy €/MWh": None,
            "Avg sell €/MWh": None,
            "Spread €/MWh": None,
        }
        total_values = {col: total_row.get(col, None) for col in df.columns}
        df.loc[len(df)] = total_values

    label_key = "Year" if freq == "Y" else "Month"
    df[label_key] = df[label_key].astype(str)
    return df.reset_index(drop=True)


def styled_table(df: pd.DataFrame, currency_cols=None, percent_cols=None, float_cols=None, currency_decimals=0, float_decimals=2, thousands=True) -> pd.io.formats.style.Styler:
    currency_cols = currency_cols or []
    percent_cols = percent_cols or []
    float_cols = float_cols or []
    fmt = {}
    for c in currency_cols:
        if c in df.columns:
            fmt[c] = lambda v, d=currency_decimals, t=thousands: format_currency(v, decimals=d, thousands=t)
    for c in percent_cols:
        if c in df.columns:
            fmt[c] = lambda v, d=1: format_percent(v, decimals=d)
    for c in float_cols:
        if c in df.columns:
            fmt[c] = f"{{:.{float_decimals}f}}"
    return df.style.format(fmt)


# ---------- Color Management ----------
def get_chart_colors() -> dict:
    """Clean chart colors matching modern design"""
    return {
        'primary': '#525252',       # Clean gray-600
        'accent': '#3b82f6',        # Modern blue
        'green': '#10b981',         # Success green
        'emerald': '#10b981',       # Same as green
        'red': '#ef4444',           # Error red
        'orange': '#f59e0b',        # Warning orange
        'darkgreen': '#059669',     # Dark green for profits
        'black': '#000000',         # Grid lines
        'white': '#ffffff',         # Text overlays
        'grey_light': '#e5e5e5',    # Light gray for backgrounds
    }

from contextlib import contextmanager

@contextmanager
def safe_pyplot_figure(*args, **kwargs):
    """Context manager to ensure proper cleanup of matplotlib figures"""
    fig, ax = plt.subplots(*args, **kwargs)
    try:
        yield fig, ax
    finally:
        plt.close(fig)

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@st.cache_data(show_spinner=False)
def load_balancing_day_series(bm_csv: Optional[str], target_date_iso: str) -> Optional[pd.Series]:
    """Return 15-minute Balancing Market prices for a single day."""
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



def bm_stats(series: pd.Series) -> Dict[str, float]:
    return {
        "min": float(series.min()),
        "p10": float(series.quantile(0.10)),
        "median": float(series.median()),
        "p90": float(series.quantile(0.90)),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "std": float(series.std(ddof=0)),
    }


# New: Advanced market analysis functions
@st.cache_data(show_spinner=False)
def analyze_monthly_trends(pzu_csv: str, capacity_mwh: float, round_trip_efficiency: float = 0.9) -> Dict:
    """Analyze monthly profitability trends from historical PZU data - requires minimum 12 months"""
    if not Path(pzu_csv).exists():
        return {'error': 'Historical PZU data file not found'}
    
    try:
        df = pd.read_csv(pzu_csv)
        df['date'] = pd.to_datetime(df['date'])
        
        # Check if we have enough historical data
        date_range = df['date'].max() - df['date'].min()
        total_months = len(df['date'].dt.to_period('M').unique())
        
        if total_months < 12:
            return {
                'error': f'Insufficient historical data. Found {total_months} months, need minimum 12 months for trend analysis',
                'suggestion': 'Use pzu_history_2y.csv or pzu_history_3y.csv for proper historical analysis'
            }
        
        df['month'] = df['date'].dt.to_period('M')
        
        monthly_results = []
        for month, month_data in df.groupby('month'):
            month_profits = []
            for date, day_data in month_data.groupby('date'):
                day_series = pd.Series(day_data.sort_values('hour')['price'].to_list())
                if len(day_series) >= 24:  # Full day only
                    # Simple arbitrage: buy at min, sell at max
                    min_price = day_series.min()
                    max_price = day_series.max()
                    net_spread = max_price - (min_price / round_trip_efficiency)
                    daily_profit = net_spread * capacity_mwh
                    month_profits.append(daily_profit)
            
            if month_profits:
                monthly_results.append({
                    'month': str(month),
                    'avg_daily_profit': np.mean(month_profits),
                    'total_monthly_profit': sum(month_profits),
                    'profitable_days': len([p for p in month_profits if p > 0]),
                    'total_days': len(month_profits),
                    'success_rate': len([p for p in month_profits if p > 0]) / len(month_profits) * 100,
                    'volatility': np.std(month_profits),
                    'max_daily_profit': max(month_profits),
                    'min_daily_profit': min(month_profits)
                })
        
        # Sort by month for chronological order
        monthly_results.sort(key=lambda x: x['month'])
        
        return {
            'monthly_data': monthly_results,
            'total_months': len(monthly_results),
            'data_period': f"{df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}",
            'avg_monthly_profit': np.mean([m['total_monthly_profit'] for m in monthly_results]) if monthly_results else 0,
            'total_historical_profit': sum([m['total_monthly_profit'] for m in monthly_results]),
            'best_month': max(monthly_results, key=lambda x: x['total_monthly_profit']) if monthly_results else None,
            'worst_month': min(monthly_results, key=lambda x: x['total_monthly_profit']) if monthly_results else None,
            'overall_success_rate': np.mean([m['success_rate'] for m in monthly_results]) if monthly_results else 0
        }
    except Exception as e:
        return {'error': f'Error analyzing historical data: {str(e)}'}

@st.cache_data(show_spinner=False)
def analyze_historical_monthly_trends_only(
    pzu_csv: str,
    capacity_mwh: float,
    round_trip_efficiency: float = 0.9,
    start_year: int = 2023,
) -> Dict:
    """Historical monthly trends, filtered from start_year onward.
    Adds an 'analysis_type' field and returns only monthly-level insights.
    Requires at least 12 months in the filtered range.
    """
    if not Path(pzu_csv).exists():
        return {'error': 'Historical PZU data file not found'}

    try:
        df = pd.read_csv(pzu_csv)
        df['date'] = pd.to_datetime(df['date'])

        # Filter from the requested start year (e.g., business opened in 2023)
        start_dt = pd.Timestamp(year=start_year, month=1, day=1)
        df = df[df['date'] >= start_dt]

        total_months = len(df['date'].dt.to_period('M').unique())
        if total_months < 12:
            return {
                'info': 'Insufficient months from the selected start year',
                'reason': f'Found {total_months} months starting {start_year}-01-01; need at least 12.',
                'suggestion': 'Switch to a longer history file (2y/3y) or adjust start year',
                'analysis_type': f'Historical Monthly Trends (from {start_year})',
                'total_months': total_months
            }

        df['month'] = df['date'].dt.to_period('M')

        monthly_results = []
        for month, month_data in df.groupby('month'):
            month_profits = []
            for _, day_data in month_data.groupby('date'):
                day_series = pd.Series(day_data.sort_values('hour')['price'].to_list())
                if len(day_series) >= 24:
                    min_price = day_series.min()
                    max_price = day_series.max()
                    net_spread = max_price - (min_price / round_trip_efficiency)
                    daily_profit = net_spread * capacity_mwh
                    month_profits.append(daily_profit)
            if month_profits:
                monthly_results.append({
                    'month': str(month),
                    'avg_daily_profit': float(np.mean(month_profits)),
                    'total_monthly_profit': float(sum(month_profits)),
                    'profitable_days': int(len([p for p in month_profits if p > 0])),
                    'total_days': int(len(month_profits)),
                    'success_rate': float(len([p for p in month_profits if p > 0]) / len(month_profits) * 100),
                    'volatility': float(np.std(month_profits)),
                    'max_daily_profit': float(max(month_profits)),
                    'min_daily_profit': float(min(month_profits))
                })

        monthly_results.sort(key=lambda x: x['month'])
        return {
            'analysis_type': f'Historical Monthly Trends (from {start_year})',
            'monthly_data': monthly_results,
            'total_months': len(monthly_results),
            'data_period': f"{df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}",
            'avg_monthly_profit': float(np.mean([m['total_monthly_profit'] for m in monthly_results])) if monthly_results else 0.0,
            'total_historical_profit': float(sum([m['total_monthly_profit'] for m in monthly_results]))
        }
    except Exception as e:
        return {'error': f'Error analyzing historical data: {str(e)}'}

@st.cache_data(show_spinner=False)
def calculate_historical_roi_metrics(
    pzu_csv: str,
    capacity_mwh: float,
    investment_eur: float = 6_500_000,
    start_year: int = 2023,
    window_months: int = 12,
    round_trip_efficiency: float = 0.9,
    debt_ratio: float = 0.5,
    debt_term_years: int = 5,
    debt_interest_rate: float = 0.065,
) -> Dict:
    """Compute ROI using historical monthly profits over a specified window with proper debt service.
    Fixed to use total investment in ROI calculation, not just equity.
    """
    trends = analyze_historical_monthly_trends_only(
        pzu_csv,
        capacity_mwh,
        round_trip_efficiency=round_trip_efficiency,
        start_year=start_year,
    )
    if 'error' in trends or 'info' in trends:
        return trends

    monthly = trends.get('monthly_data', [])
    if not monthly:
        return {'error': 'No monthly data available for ROI calculation'}

    # Use the last N months within the filtered set
    last_n = monthly[-window_months:]
    total_profit = float(sum(m['total_monthly_profit'] for m in last_n))
    months_count = len(last_n)
    if months_count == 0:
        return {'error': 'Insufficient months for ROI window'}

    # Annualize the profit
    annualized_profit = total_profit * (12.0 / months_count)
    
    # Calculate debt service
    debt_amount = investment_eur * debt_ratio
    equity_amount = investment_eur * (1 - debt_ratio)
    
    # Annual debt payment (principal + interest)
    if debt_amount > 0:
        monthly_rate = debt_interest_rate / 12
        num_payments = debt_term_years * 12
        monthly_payment = debt_amount * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
        annual_debt_service = monthly_payment * 12
    else:
        annual_debt_service = 0
    
    # Net profit after debt service
    net_annual_profit = annualized_profit - annual_debt_service
    
    # FIXED: Calculate ROI based on TOTAL INVESTMENT, not just equity
    roi_percent = (net_annual_profit / investment_eur) * 100 if investment_eur > 0 else 0.0
    
    # Also calculate equity ROI for comparison
    equity_roi_percent = (net_annual_profit / equity_amount) * 100 if equity_amount > 0 else 0.0
    
    # Payback based on total investment
    payback_years = investment_eur / net_annual_profit if net_annual_profit > 0 else float('inf')
    
    # NPV calculation (5 years, 6.5% discount rate)
    discount_rate = 0.065
    npv = 0
    for year in range(1, 6):
        npv += net_annual_profit / ((1 + discount_rate) ** year)
    npv -= investment_eur  # Subtract initial investment

    return {
        'analysis_type': f'Historical ROI ({months_count} months, from {start_year})',
        'window_months': months_count,
        'investment_eur': investment_eur,
        'debt_amount_eur': debt_amount,
        'equity_amount_eur': equity_amount,
        'annual_debt_service_eur': annual_debt_service,
        'gross_profit_eur': annualized_profit,
        'annualized_profit_eur': annualized_profit,
        'net_profit_eur': net_annual_profit,
        'roi_total_investment_percent': roi_percent,
        'roi_annual_percent': roi_percent,
        'roi_equity_percent': equity_roi_percent,
        'payback_years': payback_years,
        'npv_5y_eur': npv,
        'data_period': trends.get('data_period'),
        'total_months_available': trends.get('total_months', months_count)
    }

def analyze_romanian_balancing_market(bm_series: pd.Series, capacity_mwh: float) -> Dict:
    """
    Analyze Romanian Balancing Market - operated by TRANSELECTRICA (NOT OPCOM)
    OPCOM operates: PZU (Day-Ahead) and Intraday markets (arbitrage possible)
    TRANSELECTRICA operates: Balancing Market (NO arbitrage - different purpose entirely)
    """
    if bm_series is None or len(bm_series) == 0:
        return {'error': 'No balancing market data available'}
    
    bm_prices = bm_series.to_list()
    
    # Romanian balancing market characteristics - TRANSELECTRICA ONLY
    analysis = {
        'market_name': 'Romanian Balancing Market',
        'operator': 'TRANSELECTRICA (TSO)',
        'trading_platform': 'TRANSELECTRICA Platform (NOT OPCOM)',
        'opcom_markets': 'PZU Day-Ahead, Intraday (arbitrage possible)',
        'transelectrica_markets': 'Balancing Market (NO arbitrage)',
        'time_resolution': '15 minutes (imbalance settlement)',
        'market_type': 'Real-time Grid Balancing',
        'purpose': 'Maintain grid frequency 50Hz ± tolerance',
        'data_points': len(bm_series),
        
        # Price analysis (imbalance settlement prices)
        'avg_imbalance_price_ron_mwh': np.mean(bm_prices),
        'min_imbalance_price_ron_mwh': min(bm_prices),
        'max_imbalance_price_ron_mwh': max(bm_prices),
        'price_volatility': np.std(bm_prices),
        'price_range_ron_mwh': max(bm_prices) - min(bm_prices),
        
        # Imbalance direction analysis
        'system_deficit_periods': len([p for p in bm_prices if p > 0]),  # Need more generation
        'system_surplus_periods': len([p for p in bm_prices if p < 0]),  # Too much generation
        'balanced_periods': len([p for p in bm_prices if p == 0]),       # System balanced
        
        # Market characteristics
        'imbalance_settlement': True,
        'real_time_operation': True,
        'requires_tso_prequalification': True,
        'minimum_response_time_seconds': 30,  # For primary reserves
        'grid_frequency_target': '50.0 Hz',
        
        # Services available for BESS
        'primary_frequency_control': True,   # FCR - automatic response
        'secondary_frequency_control': True, # aFRR - automatic response
        'tertiary_reserves': True,          # mFRR - manual activation
        'black_start_capability': False,    # Typically for conventional plants
        
        # Revenue model - COMPLETELY DIFFERENT from arbitrage
        'arbitrage_trading': False,
        'frequency_regulation_services': True,
        'revenue_structure': {
            'availability_payments': 'Fixed payments for being available',
            'activation_payments': 'Energy payments when activated',
            'capacity_payments': 'Monthly/yearly capacity reservations'
        },
        
        'regulatory_framework': {
            'grid_operator': 'TRANSELECTRICA',
            'market_regulator': 'ANRE',
            'european_compliance': 'SOGL, EBGL Network Codes',
            'grid_code': 'Romanian Grid Code compliance required'
        },
        
        'key_differences_from_opcom': [
            'OPCOM: Day-ahead & Intraday markets (arbitrage trading)',
            'TRANSELECTRICA: Real-time grid balancing (frequency regulation)',
            'OPCOM: Price-based energy trading',
            'TRANSELECTRICA: Grid stability services',
            'OPCOM: Profit from price spreads',
            'TRANSELECTRICA: Payments for grid services'
        ],
        
        'bess_participation_requirements': [
            'Technical prequalification with TRANSELECTRICA',
            'Grid Code compliance certification',
            'Real-time communication systems',
            'Minimum response time capabilities',
            'Frequency measurement and control systems',
            'Separate from OPCOM market participation'
        ]
    }
    
    # Calculate system imbalance indicators
    total_periods = len(bm_prices)
    if total_periods > 0:
        analysis['system_imbalance_analysis'] = {
            'deficit_percentage': (analysis['system_deficit_periods'] / total_periods) * 100,
            'surplus_percentage': (analysis['system_surplus_periods'] / total_periods) * 100,
            'balanced_percentage': (analysis['balanced_periods'] / total_periods) * 100,
            'dominant_imbalance': 'Generation Deficit' if analysis['system_deficit_periods'] > analysis['system_surplus_periods'] else 'Generation Surplus',
            'grid_stress_indicator': analysis['price_volatility']  # Higher volatility = more grid stress
        }
    
    # Convert RON to EUR (approximate rate: ~5 RON/EUR)
    ron_to_eur = 0.2
    analysis['avg_imbalance_price_eur_mwh'] = analysis['avg_imbalance_price_ron_mwh'] * ron_to_eur
    analysis['min_imbalance_price_eur_mwh'] = analysis['min_imbalance_price_ron_mwh'] * ron_to_eur
    analysis['max_imbalance_price_eur_mwh'] = analysis['max_imbalance_price_ron_mwh'] * ron_to_eur
    analysis['price_range_eur_mwh'] = analysis['price_range_ron_mwh'] * ron_to_eur
    
    return analysis


@st.cache_data(show_spinner=False)
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


def load_transelectrica_imbalance_from_excel(
    path_or_dir: str,
    fx_ron_per_eur: float = 5.0,
    declared_currency: Optional[str] = None,
) -> pd.DataFrame:
    """Load Transelectrica estimated imbalance prices from export-8 Excel or a folder of files.
    Normalizes to a DataFrame with columns: date(str), slot(int 0..95), price_eur_mwh(float).
    """
    p = Path(path_or_dir)
    frames: List[pd.DataFrame] = []
    if p.is_dir():
        for f in p.rglob("*.xls*"):
            try:
                df = _imb_read_any(f)
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
    elif p.is_file():
        df = _imb_read_any(p)
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "slot", "price_eur_mwh"])  # empty
        dcol, tcol, pcol, fcol = _imb_detect_columns(df)
        norm = _imb_normalize(df, dcol, tcol, pcol, fcol)
        detected = _guess_currency_column(df)
        if detected:
            norm["source_currency"] = detected.upper()
        frames.append(norm)
    else:
        return pd.DataFrame(columns=["date", "slot", "price_eur_mwh"])  # empty

    if not frames:
        return pd.DataFrame(columns=["date", "slot", "price_eur_mwh"])  # empty

    # Filter out empty DataFrames before concatenation
    non_empty_frames = [f for f in frames if not f.empty]
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
        src_cur = pd.Series([declared or "" ] * len(out))

    fx = float(fx_ron_per_eur) if float(fx_ron_per_eur or 0.0) != 0 else 5.0
    price_numeric = pd.to_numeric(out["price"], errors="coerce")

    # Determine which rows still need conversion.
    ron_aliases = {"RON", "LEI", "RON/MWH", "LEI/MWH"}
    eur_aliases = {"EUR", "EUR/MWH"}

    is_ron = src_cur.isin(ron_aliases)
    is_eur = src_cur.isin(eur_aliases)

    if not is_eur.any() and not is_ron.any():
        # Fall back to declared currency if detection failed.
        if declared == "EUR":
            is_eur = pd.Series([True] * len(out))
        elif declared == "RON":
            is_ron = pd.Series([True] * len(out))

    price_eur = price_numeric.copy()
    if is_ron.any():
        price_eur.loc[is_ron] = price_numeric.loc[is_ron] / fx
    original_currency = src_cur.where(src_cur != "", declared or ("RON" if is_ron.any() and not is_eur.any() else "EUR"))
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
    """Return a 15-minute hedge price curve (€/MWh) derived from PZU data.

    The returned frame always has columns: date (str, YYYY-MM-DD), slot (int 0..95),
    hedge_price_eur_mwh (float). When the PZU file is missing or malformed an empty
    frame is returned so callers can safely merge and fall back to imbalance prices.
    """

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
            fx = float(fx_ron_per_eur) if float(fx_ron_per_eur) != 0 else 5.0
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
        # Ensure hour within 0..23 to create quarter-hour slots; average duplicates first.
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


def compute_activation_factor_series(
    system_df: pd.DataFrame,
    reference_mw: float,
    *,
    smoothing: Optional[str] = None,
) -> pd.Series:
    """Compute activation duty factors from system imbalance data.

    Parameters
    ----------
    system_df : pd.DataFrame
        DataFrame with columns ``date`` (datetime-like), ``slot`` (int), ``imbalance_mw`` (float).
    reference_mw : float
        Reference MW against which to normalise imbalance. Represents the aggregate MW
        of reserve the user expects to cover.
    smoothing : {None, "monthly"}
        Optional aggregation level. If ``"monthly"``, average factors per calendar month
        to reduce volatility. Defaults to per-ISP factors.
    """

    if reference_mw <= 0:
        return pd.Series(dtype=float)
    if system_df is None or system_df.empty:
        return pd.Series(dtype=float)

    df = system_df.copy()
    df['date'] = pd.to_datetime(df['date'])
    if 'imbalance_mw' not in df.columns:
        return pd.Series(dtype=float)

    df['activation_factor'] = (df['imbalance_mw'].abs() / float(reference_mw)).clip(lower=0.0, upper=1.0)

    if smoothing == 'monthly':
        df['month'] = df['date'].dt.to_period('M')
        grouped = df.groupby(['month', 'slot'])['activation_factor'].mean().reset_index()
        grouped['date'] = grouped['month'].dt.to_timestamp()
        grouped = grouped.drop(columns=['month'])
        df = grouped

    df = df.dropna(subset=['date', 'slot', 'activation_factor'])
    if df.empty:
        return pd.Series(dtype=float)

    idx = pd.MultiIndex.from_arrays([
        pd.to_datetime(df['date']).values,
        df['slot'].astype(int).values,
    ], names=['date', 'slot'])
    return pd.Series(df['activation_factor'].values, index=idx)


def _month_key(d: pd.Timestamp) -> str:
    return f"{d.year:04d}-{d.month:02d}"


@st.cache_data(show_spinner=False)
def load_system_imbalance_from_excel(
    path_or_dir: str,
    target_dates: Optional[pd.DatetimeIndex] = None,
) -> pd.DataFrame:
    """Load Transelectrica system-imbalance data and normalize to date/slot/mW.

    Parameters
    ----------
    path_or_dir : str
        Excel/CSV file or directory tree containing imbalance exports.
    target_dates : DatetimeIndex, optional
        When provided, missing (date, slot) pairs will be forward-filled using
        slot averages so the returned frame covers the full price window.
    """

    p = Path(path_or_dir)
    targets: List[Path] = []
    if p.is_dir():
        targets = [*p.rglob("*.xls"), *p.rglob("*.xlsx"), *p.rglob("*.csv")]
    elif p.is_file():
        targets = [p]
    else:
        return pd.DataFrame(columns=["date", "slot", "imbalance_mw"])  # empty

    frames: List[pd.DataFrame] = []

    for f in targets:
        # First try to parse official Transelectrica "Estimated power system imbalance" exports
        if f.suffix.lower() == ".xlsx":
            try:
                raw = pd.read_excel(f, skiprows=4)
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
            df = _imb_read_any(f)
        except Exception:
            continue
        if df is None or df.empty:
            continue

        cand = None
        for c in df.columns:
            s = str(c).lower()
            if any(k in s for k in ["imbalance", "dezechilibru", "power system imbalance", "sistem", "desechilibru"]):
                cand = c
                break
        if cand is None:
            num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            if num_cols:
                cand = num_cols[-1]
            else:
                continue

        dcol, tcol, _, _ = _imb_detect_columns(df)
        norm = _imb_normalize(df, dcol, tcol, cand, None)
        if "price" in norm.columns:
            norm = norm.rename(columns={"price": "imbalance_mw"})
        if "imbalance_mw" not in norm.columns:
            if cand in norm.columns:
                norm["imbalance_mw"] = pd.to_numeric(norm[cand], errors="coerce")
            else:
                continue
        frames.append(norm[["date", "slot", "imbalance_mw"]])

    if not frames:
        return pd.DataFrame(columns=["date", "slot", "imbalance_mw"])  # empty

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
            base_idx = pd.MultiIndex.from_product(
                [target_dates, range(96)], names=["date", "slot"]
            )
            base = pd.DataFrame(index=base_idx).reset_index()
            base = base.merge(out, on=["date", "slot"], how="left")
            slot_means = base.groupby("slot")["imbalance_mw"].mean()
            base["imbalance_mw"] = base["imbalance_mw"].fillna(base["slot"].map(slot_means))
            base["imbalance_mw"] = base["imbalance_mw"].fillna(0.0)
            out = base

    out["date"] = out["date"].dt.date.astype(str)
    return out[["date", "slot", "imbalance_mw"]]


def _find_in_data_dir(patterns: List[str]) -> Optional[str]:
    """Return first file path in ./data matching any of the patterns (case-insensitive)."""
    data_dir = project_root / "data"
    if not data_dir.exists():
        return None
    patterns_ci = [p.lower() for p in patterns]
    for p in data_dir.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        if any(re.search(pat, name) for pat in patterns_ci):
            return str(p)
    return None


def _list_in_data_dir(patterns: List[str]) -> List[str]:
    """List all files in ./data (and known downloads dirs) matching any regex pattern (case-insensitive)."""
    out: List[str] = []
    roots = [project_root / "data", project_root / "downloads", project_root]
    patterns_ci = [p.lower() for p in patterns]
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            name = p.name.lower()
            for pat in patterns_ci:
                try:
                    if re.search(pat, name):
                        out.append(str(p))
                        break
                except Exception:
                    continue
    # De-duplicate while preserving order
    seen = set()
    uniq = []
    for s in out:
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    return uniq

@st.cache_data(show_spinner=False)
def parse_battery_specs_from_document(path: str) -> Dict[str, Optional[float]]:
    """Parse a technical proposal PDF/DOC/CSV for basic battery specs.
    Returns keys: capacity_mwh, power_mw, round_trip_efficiency, soc_min, soc_max.
    """
    out = {
        'capacity_mwh': None,
        'power_mw': None,
        'round_trip_efficiency': None,
        'soc_min': None,
        'soc_max': None,
    }
    try:
        p = Path(path)
        text = ""
        if p.suffix.lower() in (".pdf",):
            try:
                from pdfminer.high_level import extract_text
                text = extract_text(path) or ""
            except Exception:
                text = ""
        elif p.suffix.lower() in (".txt", ".md"):
            text = p.read_text(encoding="utf-8", errors="ignore")
        else:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
        s = text.replace("\n", " ")

        # Power MW
        m = re.search(r"(\d{1,3})\s*MW\b", s, re.IGNORECASE)
        if m:
            out['power_mw'] = float(m.group(1))
        # Capacity MWh
        m = re.search(r"(\d{1,4})\s*MWh\b", s, re.IGNORECASE)
        if m:
            out['capacity_mwh'] = float(m.group(1))
        # Round-trip efficiency
        m = re.search(r"(round[-\s]?trip|RTE)[^%]{0,30}?(\d{2,3})\s*%", s, re.IGNORECASE)
        if m:
            rte = float(m.group(2)) / 100.0
            if 0 < rte <= 1.0:
                out['round_trip_efficiency'] = rte
        # SOC min/max or DoD
        m = re.search(r"SOC\s*min[^0-9]{0,10}(\d{1,2})\s*%", s, re.IGNORECASE)
        if m:
            out['soc_min'] = float(m.group(1)) / 100.0
        m = re.search(r"SOC\s*max[^0-9]{0,10}(\d{1,3})\s*%", s, re.IGNORECASE)
        if m:
            out['soc_max'] = float(m.group(1)) / 100.0
        m = re.search(r"DoD[^0-9]{0,10}(\d{1,3})\s*%", s, re.IGNORECASE)
        if m and out['soc_min'] is None and out['soc_max'] is None:
            dod = float(m.group(1)) / 100.0
            out['soc_min'] = max(0.0, 1.0 - dod)
            out['soc_max'] = 1.0
    except Exception:
        pass
    return out


@st.cache_data(show_spinner=False)
def simulate_frequency_regulation_revenue(
    prices_eur: pd.DataFrame,
    contracted_mw: float,
    capacity_price_eur_mw_h: float,
    up_threshold_eur_mwh: float = 0.0,
    down_threshold_eur_mwh: float = 0.0,
    pay_down_as_positive: bool = True,
) -> Dict:
    """Estimate revenue using estimated imbalance prices as proxy for activation price.
    - Capacity revenue = contracted_mw * hours_available_in_month * capacity_price_eur_mw_h
      where hours_available_in_month is computed from the presence of any price entries that month.
    - Activation revenue: when price >= up_threshold or price <= -down_threshold, assume full contracted MW activated.
    - Energy per 15-min slot = contracted_mw * 0.25 MWh.
    - If pay_down_as_positive=True, down-activation uses |price|; else uses signed price.
    """
    if prices_eur is None or prices_eur.empty or contracted_mw <= 0:
        return {
            'monthly': [],
            'totals': {
                'capacity_revenue_eur': 0.0,
                'activation_revenue_eur': 0.0,
                'total_revenue_eur': 0.0,
                'months': 0
            }
        }

    df = prices_eur.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')

    monthly_rows = []
    cap_total = 0.0
    act_total = 0.0

    for month, mdf in df.groupby('month'):
        hours_in_data = len(mdf) * 0.25
        cap_rev = contracted_mw * hours_in_data * capacity_price_eur_mw_h
        # Activation flags
        up_mask = mdf['price_eur_mwh'] >= float(up_threshold_eur_mwh)
        down_mask = mdf['price_eur_mwh'] <= -float(down_threshold_eur_mwh)
        # Energy per slot
        energy_mwh_per_slot = contracted_mw * 0.25
        # Up activation revenue
        up_rev = float((mdf.loc[up_mask, 'price_eur_mwh'] * energy_mwh_per_slot).sum())
        # Down activation revenue (toggle absolute or signed)
        if pay_down_as_positive:
            down_rev = float((mdf.loc[down_mask, 'price_eur_mwh'].abs() * energy_mwh_per_slot).sum())
        else:
            down_rev = float((mdf.loc[down_mask, 'price_eur_mwh'] * energy_mwh_per_slot).sum())
        act_rev = up_rev + down_rev

        monthly_rows.append({
            'month': str(month),
            'hours_in_data': hours_in_data,
            'capacity_revenue_eur': cap_rev,
            'activation_revenue_eur': act_rev,
            'total_revenue_eur': cap_rev + act_rev,
            'up_slots': int(up_mask.sum()),
            'down_slots': int(down_mask.sum()),
        })
        cap_total += cap_rev
        act_total += act_rev

    monthly_rows.sort(key=lambda x: x['month'])

    return {
        'monthly': monthly_rows,
        'totals': {
            'capacity_revenue_eur': cap_total,
            'activation_revenue_eur': act_total,
            'total_revenue_eur': cap_total + act_total,
            'months': len(monthly_rows)
        }
    }

def _read_calendar_df(src: Optional[object]) -> Optional[pd.DataFrame]:
    """Read an availability calendar from a path string or an uploaded file-like object.
    Expected columns (any of): date, slot, available_mw OR available (0/1 or bool).
    """
    if not src:
        return None
    try:
        # UploadedFile-like object
        if hasattr(src, 'read'):
            data = src.read()
            bio = io.BytesIO(data)
            # Try CSV first, then Excel
            try:
                df = pd.read_csv(bio)
            except Exception:
                bio.seek(0)
                df = pd.read_excel(bio)
            return df
        # Path string
        p = Path(str(src))
        if not p.exists():
            return None
        if p.suffix.lower() in ('.xlsx', '.xls'):
            return pd.read_excel(p)
        return pd.read_csv(p)
    except Exception:
        return None

def _normalize_calendar_df(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        return None
    df2 = df.copy()
    # Normalize column names
    cols = {str(c).strip().lower(): c for c in df2.columns}
    date_col = None
    slot_col = None
    avail_mw_col = None
    avail_col = None
    for k in ['date', 'data', 'day']:
        if k in cols: date_col = cols[k]; break
    for k in ['slot', 'index', 'quarter', 'interval index']:
        if k in cols: slot_col = cols[k]; break
    for k in ['available_mw', 'avail_mw', 'mw', 'capacity_mw']:
        if k in cols: avail_mw_col = cols[k]; break
    for k in ['available', 'avail', 'flag']:
        if k in cols: avail_col = cols[k]; break
    if date_col is None or slot_col is None:
        # Try parse datetime and derive slot
        for c in df2.columns:
            if pd.api.types.is_datetime64_any_dtype(df2[c]):
                date_col = c
                df2['date'] = pd.to_datetime(df2[c]).dt.date.astype(str)
                df2['slot'] = pd.to_datetime(df2[c]).dt.hour * 4 + (pd.to_datetime(df2[c]).dt.minute // 15)
                break
    if 'date' not in df2.columns and date_col:
        df2['date'] = pd.to_datetime(df2[date_col], errors='coerce').dt.date.astype(str)
    if 'slot' not in df2.columns and slot_col:
        df2['slot'] = pd.to_numeric(df2[slot_col], errors='coerce')
    # Keep only needed
    keep = ['date', 'slot']
    if avail_mw_col and avail_mw_col in df2.columns:
        df2['available_mw'] = pd.to_numeric(df2[avail_mw_col], errors='coerce')
        keep.append('available_mw')
    if avail_col and avail_col in df2.columns and 'available_mw' not in df2.columns:
        df2['available'] = df2[avail_col].astype(int)
        keep.append('available')
    df2 = df2.dropna(subset=['date', 'slot'])
    df2['slot'] = df2['slot'].astype(int)
    return df2[keep]

@st.cache_data(show_spinner=False)
def simulate_frequency_regulation_revenue_multi(
    prices_eur: pd.DataFrame,
    products: Dict[str, Dict[str, float]],
    pay_down_as_positive: bool = True,
    pay_down_positive_map: Optional[Dict[str, bool]] = None,
    activation_factor_map: Optional[Dict[str, float]] = None,
    calendars: Optional[Dict[str, pd.DataFrame]] = None,
    system_imbalance_df: Optional[pd.DataFrame] = None,
    activation_curve_map: Optional[Dict[str, pd.Series]] = None,
    activation_price_mode: str = "market",
    pay_as_bid_map: Optional[Dict[str, Dict[str, float]]] = None,
    battery_power_mw: Optional[float] = None,
) -> Dict:
    """Multi-product simulation for FCR/aFRR/mFRR with separate contracted MW, capacity prices, and thresholds.
    products format example:
    {
      'FCR': {'enabled': True, 'mw': 10, 'cap_eur_mw_h': 7.5, 'up_thr': 0.0, 'down_thr': 0.0},
      'aFRR': {'enabled': True, 'mw': 15, 'cap_eur_mw_h': 5.0, 'up_thr': 0.0, 'down_thr': 0.0},
      'mFRR': {'enabled': False, 'mw': 0,  'cap_eur_mw_h': 0.0, 'up_thr': 0.0, 'down_thr': 0.0},
    }
    """
    if prices_eur is None or prices_eur.empty:
        return {'monthly_by_product': {}, 'totals_by_product': {}, 'combined_monthly': [], 'combined_totals': {'capacity_revenue_eur': 0.0, 'activation_revenue_eur': 0.0, 'total_revenue_eur': 0.0, 'months': 0}}

    df = prices_eur.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')

    has_imbalance = (system_imbalance_df is not None) and (not system_imbalance_df.empty)

    monthly_by_product: Dict[str, List[Dict]] = {}
    totals_by_product: Dict[str, Dict[str, float]] = {}

    # For combined monthly, accumulate by month label
    combined_month_map: Dict[str, Dict[str, float]] = {}

    for prod, cfg in products.items():
        if not cfg.get('enabled'):
            continue
        mw = float(cfg.get('mw', 0.0))
        cap = float(cfg.get('cap_eur_mw_h', 0.0))
        up_thr = float(cfg.get('up_thr', 0.0))
        down_thr = float(cfg.get('down_thr', 0.0))
        if mw <= 0:
            continue

        rows = []
        cap_total = 0.0
        act_total = 0.0
        # Merge with calendar if provided
        if calendars and prod in calendars and calendars[prod] is not None and not calendars[prod].empty:
            cal = calendars[prod].copy()
            cal['date'] = pd.to_datetime(cal['date'])
            merged = df.merge(cal, on=['date', 'slot'], how='left')
            # Determine available MW per slot
            if 'available_mw' in merged.columns:
                avail_mw_series = merged['available_mw'].fillna(0.0).astype(float).clip(lower=0.0)
                avail_mw_series = avail_mw_series.apply(lambda v: min(mw, v))
            elif 'available' in merged.columns:
                avail_mw_series = merged['available'].fillna(0).astype(float) * mw
            else:
                avail_mw_series = pd.Series([mw] * len(merged), index=merged.index)
            merged['avail_mw'] = avail_mw_series
        else:
            merged = df.copy()
            merged['avail_mw'] = mw

        # Merge system imbalance if provided
        if has_imbalance:
            simbal = system_imbalance_df.copy()
            simbal['date'] = pd.to_datetime(simbal['date'])
            merged = merged.merge(simbal, on=['date','slot'], how='left')

        for month, mdf in merged.groupby('month'):
            hours_in_data = len(mdf) * 0.25
            # Capacity revenue based on available MW per slot
            # Note: capacity revenue unaffected by activation factor; apply availability and optional battery power cap
            slot_cap_mw = mdf['avail_mw']
            if battery_power_mw is not None:
                slot_cap_mw = np.minimum(slot_cap_mw, float(battery_power_mw))
            cap_rev = float((slot_cap_mw * 0.25 * cap).sum())

            # Activation masks include price thresholds and optional imbalance direction
            up_mask = mdf['price_eur_mwh'] >= up_thr
            down_mask = mdf['price_eur_mwh'] <= -down_thr
            if has_imbalance and ('imbalance_mw' in mdf.columns):
                up_mask = up_mask & (mdf['imbalance_mw'].fillna(0) > 0)
                down_mask = down_mask & (mdf['imbalance_mw'].fillna(0) < 0)

            # Apply per-product activation factor (0..1)
            act_factor_default = 1.0
            if activation_factor_map and prod in activation_factor_map:
                try:
                    act_factor_default = max(0.0, float(activation_factor_map.get(prod, 1.0)))
                except Exception:
                    act_factor_default = 1.0

            custom_activation = None
            if activation_curve_map and prod in activation_curve_map:
                custom_activation = activation_curve_map.get(prod)

            if custom_activation is not None and not custom_activation.empty:
                lookup_index = pd.MultiIndex.from_arrays([
                    mdf['date'].values,
                    mdf['slot'].astype(int).values,
                ])
                looked_up = custom_activation.reindex(lookup_index)
                act_factor_series = pd.Series(looked_up.values, index=mdf.index)
                act_factor_series = act_factor_series.fillna(act_factor_default).clip(lower=0.0, upper=1.0)
            else:
                act_factor_series = pd.Series(act_factor_default, index=mdf.index)

            slot_act_mw = mdf['avail_mw'] * act_factor_series
            # Battery power cap during activation
            if battery_power_mw is not None:
                slot_act_mw = np.minimum(slot_act_mw, float(battery_power_mw))
            if has_imbalance and 'imbalance_mw' in mdf.columns:
                imbalance_cap = mdf['imbalance_mw'].abs().fillna(0.0)
                slot_act_mw = np.minimum(slot_act_mw, imbalance_cap)
            energy_per_slot_series = slot_act_mw * 0.25
            price_series = mdf['price_eur_mwh']

            activation_price_mode_lower = (activation_price_mode or "market").lower()
            up_price_series = price_series.copy()
            down_price_series = price_series.copy()

            if activation_price_mode_lower == "pay_as_bid" and pay_as_bid_map and prod in pay_as_bid_map:
                pay_prices = pay_as_bid_map.get(prod, {})
                try:
                    up_const = float(pay_prices.get('up_price', up_price_series.mean()))
                except Exception:
                    up_const = float(up_price_series.mean()) if not up_price_series.empty else 0.0
                try:
                    down_const = float(pay_prices.get('down_price', up_const))
                except Exception:
                    down_const = up_const
                up_price_series = pd.Series(up_const, index=mdf.index)
                down_price_series = pd.Series(down_const, index=mdf.index)

            up_rev = float((up_price_series[up_mask] * energy_per_slot_series[up_mask]).sum())
            # Per-product override for down-activation settlement sign
            prod_down_positive = pay_down_positive_map.get(prod, pay_down_as_positive) if pay_down_positive_map else pay_down_as_positive
            if prod_down_positive:
                down_rev = float((down_price_series[down_mask].abs() * energy_per_slot_series[down_mask]).sum())
            else:
                down_rev = float((down_price_series[down_mask] * energy_per_slot_series[down_mask]).sum())
            act_rev = up_rev + down_rev
            act_energy = float(energy_per_slot_series.sum())
            # Use hedge curve when available; otherwise fall back to absolute imbalance prices
            hedge_prices = None
            if 'hedge_price_eur_mwh' in mdf.columns:
                try:
                    hedge_prices = pd.to_numeric(mdf['hedge_price_eur_mwh'], errors='coerce')
                except Exception:
                    hedge_prices = None
            fallback_prices = price_series.abs()
            if hedge_prices is None:
                hedge_prices = fallback_prices
            else:
                hedge_prices = hedge_prices.fillna(fallback_prices)

            energy_cost = float(
                (energy_per_slot_series[up_mask] * hedge_prices[up_mask]).sum()
                + (energy_per_slot_series[down_mask] * hedge_prices[down_mask]).sum()
            )

            try:
                print(
                    f"[FR DEBUG] {prod} {month}: cap={cap_rev:.2f}€ act={act_rev:.2f}€ energy={act_energy:.2f}MWh hedge_cost={energy_cost:.2f}€ pricing={activation_price_mode_lower}",
                )
            except Exception:
                pass

            row = {
                'month': str(month),
                'hours_in_data': hours_in_data,
                'capacity_revenue_eur': cap_rev,
                'activation_revenue_eur': act_rev,
                'total_revenue_eur': cap_rev + act_rev,
                'up_slots': int(up_mask.sum()),
                'down_slots': int(down_mask.sum()),
                'activation_energy_mwh': act_energy,
                'energy_cost_eur': energy_cost,
            }
            rows.append(row)
            cap_total += cap_rev
            act_total += act_rev

            # Update combined monthly
            mkey = str(month)
            agg = combined_month_map.setdefault(mkey, {
                'month': mkey,
                'hours_in_data': 0.0,
                'capacity_revenue_eur': 0.0,
                'activation_revenue_eur': 0.0,
                'total_revenue_eur': 0.0,
                'up_slots': 0,
                'down_slots': 0,
                'activation_energy_mwh': 0.0,
                'energy_cost_eur': 0.0,
            })
            agg['hours_in_data'] = max(agg['hours_in_data'], hours_in_data)
            agg['capacity_revenue_eur'] += cap_rev
            agg['activation_revenue_eur'] += act_rev
            agg['total_revenue_eur'] += (cap_rev + act_rev)
            agg['up_slots'] += int(up_mask.sum())
            agg['down_slots'] += int(down_mask.sum())
            agg['activation_energy_mwh'] += act_energy
            agg['energy_cost_eur'] += energy_cost

        rows.sort(key=lambda x: x['month'])
        monthly_by_product[prod] = rows
        totals_by_product[prod] = {
            'capacity_revenue_eur': cap_total,
            'activation_revenue_eur': act_total,
            'total_revenue_eur': cap_total + act_total,
            'energy_cost_eur': float(sum(r['energy_cost_eur'] for r in rows)),
            'months': len(rows),
        }

    combined_monthly = sorted(combined_month_map.values(), key=lambda x: x['month'])
    comb_cap = sum(r['capacity_revenue_eur'] for r in combined_monthly)
    comb_act = sum(r['activation_revenue_eur'] for r in combined_monthly)
    comb_cost = sum(r.get('energy_cost_eur', 0.0) for r in combined_monthly)
    combined_totals = {
        'capacity_revenue_eur': comb_cap,
        'activation_revenue_eur': comb_act,
        'total_revenue_eur': comb_cap + comb_act,
        'energy_cost_eur': comb_cost,
        'months': len(combined_monthly),
    }

    try:
        comb_energy = sum(r.get('activation_energy_mwh', 0.0) for r in combined_monthly)
        print(
            f"[FR DEBUG] Combined totals: cap={comb_cap:.2f}€ act={comb_act:.2f}€ energy={comb_energy:.2f}MWh hedge_cost={comb_cost:.2f}€ months={len(combined_monthly)}",
        )
    except Exception:
        pass

    return {
        'monthly_by_product': monthly_by_product,
        'totals_by_product': totals_by_product,
        'combined_monthly': combined_monthly,
        'combined_totals': combined_totals,
    }

@st.cache_data(show_spinner=False)
def analyze_pzu_best_hours(pzu_csv: str, start_year: int = 2023, window_months: int = 12) -> Dict:
    """Compute hour-of-day average prices and best buy/sell hours over a historical window."""
    if not pzu_csv or not Path(pzu_csv).exists():
        return {'error': 'PZU CSV not found'}
    try:
        df = pd.read_csv(pzu_csv)
        df['date'] = pd.to_datetime(df['date'])
        df['month'] = df['date'].dt.to_period('M')
        df = df[df['date'] >= pd.Timestamp(year=start_year, month=1, day=1)]
        # keep last N months
        months_sorted = sorted(df['month'].unique())
        if not months_sorted:
            return {'error': 'No months found after filtering'}
        chosen = months_sorted[-window_months:]
        df = df[df['month'].isin(chosen)]
        # ensure full 24h days
        full_days = df.groupby('date')['hour'].count()
        valid_dates = full_days[full_days >= 24].index
        dfd = df[df['date'].isin(valid_dates)]
        # average by hour-of-day
        avg_by_hour = dfd.groupby('hour')['price'].mean().reindex(range(24)).fillna(method='ffill').fillna(method='bfill')
        # best hours: lowest 3 and highest 3
        best_buy = avg_by_hour.nsmallest(3)
        best_sell = avg_by_hour.nlargest(3)
        spread = float(best_sell.iloc[0] - best_buy.iloc[0])
        return {
            'window_months': len(chosen),
            'hours': list(range(24)),
            'avg_price_by_hour': [float(x) for x in avg_by_hour.values],
            'best_buy_hours': [{'hour': int(h), 'avg_price': float(v)} for h, v in best_buy.items()],
            'best_sell_hours': [{'hour': int(h), 'avg_price': float(v)} for h, v in best_sell.items()],
            'avg_spread_top_vs_bottom': spread,
            'start_month': str(chosen[0]) if chosen else None,
            'end_month': str(chosen[-1]) if chosen else None,
        }
    except Exception as e:
        return {'error': f'Failed to analyze PZU best hours: {e}'}

@st.cache_data(show_spinner=False)
def analyze_pzu_best_hours_min_years(
    pzu_csv: str,
    min_years: int = 3,
    round_trip_efficiency: float = 0.9,
    capacity_mwh: float = 0.0,
    investment_eur: float = 6_500_000,
) -> Dict:
    """Detect best buy/sell hours using minimum N years of PZU history and estimate arbitrage profits.
    Picks the hour-of-day with lowest average price as BUY and highest as SELL across the whole period.
    Returns daily and annual profit estimates (assuming one cycle/day), plus optional ROI.
    """
    if not pzu_csv or not Path(pzu_csv).exists():
        return {'error': 'PZU CSV not found'}
    try:
        df = pd.read_csv(pzu_csv)
        if not {'date','hour','price'}.issubset(df.columns):
            return {'error': 'PZU CSV must contain columns: date,hour,price'}
        df['date'] = pd.to_datetime(df['date'])
        months = df['date'].dt.to_period('M').unique()
        total_months = len(months)
        if total_months < (min_years * 12):
            return {
                'error': f'Insufficient history: found {total_months} months, need at least {min_years*12} months',
                'suggestion': 'Point pzu_forecast_csv to a >=3-year history (e.g., data/pzu_history_3y.csv)'
            }
        # Aggregate averages by hour-of-day over full history
        df_sorted = df.sort_values(['date','hour'])
        hourly_avg = df_sorted.groupby('hour')['price'].mean().reindex(range(24))
        buy_hour = int(hourly_avg.idxmin())
        sell_hour = int(hourly_avg.idxmax())
        avg_buy = float(hourly_avg.min())
        avg_sell = float(hourly_avg.max())
        net_spread = avg_sell - (avg_buy / float(round_trip_efficiency))
        daily_profit = max(0.0, net_spread) * float(capacity_mwh)
        annual_profit = daily_profit * 365.0
        roi_percent = (annual_profit / float(investment_eur) * 100.0) if investment_eur and investment_eur > 0 else 0.0
        payback_years = (float(investment_eur) / annual_profit) if annual_profit > 0 else float('inf')
        return {
            'analysis_type': f'{min_years}-Year Best-Hour Arbitrage Estimate',
            'period_months': total_months,
            'data_period': f"{df['date'].min().date()} to {df['date'].max().date()}",
            'buy_hour': buy_hour,
            'sell_hour': sell_hour,
            'avg_buy_eur_mwh': avg_buy,
            'avg_sell_eur_mwh': avg_sell,
            'net_spread_eur_mwh': net_spread,
            'daily_profit_eur': daily_profit,
            'annual_profit_eur': annual_profit,
            'roi_annual_percent': roi_percent,
            'payback_years': payback_years,
        }
    except Exception as e:
        return {'error': f'Failed 3-year best-hour analysis: {e}'}

@st.cache_data(show_spinner=False)
def estimate_pzu_profit_window(
    pzu_csv: str,
    capacity_mwh: float,
    round_trip_efficiency: float = 0.9,
    days: Optional[int] = None,
    months: Optional[int] = None,
) -> Dict:
    """Estimate profit over the last N days or last N months using a simple daily min/max arbitrage.
    Returns used_days, used_months, total_profit_eur, avg_daily_profit_eur, annualized_profit_eur, data_period.
    """
    if not pzu_csv or not Path(pzu_csv).exists():
        return {'error': 'PZU CSV not found'}
    try:
        df = pd.read_csv(pzu_csv)
        if not {'date','hour','price'}.issubset(df.columns):
            return {'error': 'PZU CSV must contain columns: date,hour,price'}
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(['date','hour'])
        # Window selection
        used_months = 0
        if months is not None:
            uniq_months = sorted(df['date'].dt.to_period('M').unique())
            if len(uniq_months) == 0:
                return {'error': 'No months in dataset'}
            chosen = uniq_months[-int(months):]
            df = df[df['date'].dt.to_period('M').isin(chosen)]
            used_months = len(chosen)
        elif days is not None:
            uniq_days = sorted(df['date'].dt.date.unique())
            if len(uniq_days) == 0:
                return {'error': 'No days in dataset'}
            chosen_days = uniq_days[-int(days):]
            df = df[df['date'].dt.date.isin(chosen_days)]
        # Group by day and compute daily profit
        eta = float(round_trip_efficiency)
        cap = float(capacity_mwh)
        daily_profits: List[float] = []
        for _date, g in df.groupby(df['date'].dt.date):
            day_prices = g.sort_values('hour')['price']
            if len(day_prices) < 4:
                continue
            min_p = float(day_prices.min())
            max_p = float(day_prices.max())
            net = max_p - (min_p / eta)
            daily_profits.append(max(0.0, net) * cap)
        used_days = len(daily_profits)
        total_profit = float(sum(daily_profits))
        avg_daily = (total_profit / used_days) if used_days > 0 else 0.0
        # Annualize based on days covered
        annualized = avg_daily * 365.0
        period = f"{df['date'].min().date()} to {df['date'].max().date()}"
        return {
            'used_days': used_days,
            'used_months': used_months,
            'total_profit_eur': total_profit,
            'avg_daily_profit_eur': avg_daily,
            'annualized_profit_eur': annualized,
            'data_period': period,
        }
    except Exception as e:
        return {'error': f'Failed profit estimation: {e}'}

@st.cache_data(show_spinner=False)
def plan_multi_hour_strategy_from_history(
    pzu_csv: str,
    min_years: int,
    round_trip_efficiency: float,
    capacity_mwh: float,
    power_mw: float,
    buy_hours_buffer: int,
    sell_hours_buffer: int,
    cycles_per_day: int = 1,
    investment_eur: float = 6_500_000,
) -> Dict:
    """Plan a simple daily arbitrage using hour-of-day averages over >= N years.
    - Picks k lowest-avg hours for charging and k' highest-avg hours for discharging
    - Respects power and capacity, round-trip efficiency, and cycles/day budget
    - Approximates profit using average prices for chosen hours
    """
    if not pzu_csv or not Path(pzu_csv).exists():
        return {'error': 'PZU CSV not found'}
    try:
        df = pd.read_csv(pzu_csv)
        if not {'date','hour','price'}.issubset(df.columns):
            return {'error': 'PZU CSV must contain columns: date,hour,price'}
        df['date'] = pd.to_datetime(df['date'])
        months = df['date'].dt.to_period('M').unique()
        if len(months) < (min_years * 12):
            return {'error': f'Insufficient history: need >= {min_years} years'},
        hourly_avg = df.groupby('hour')['price'].mean().reindex(range(24))
        k_b = max(1, int(buy_hours_buffer))
        k_s = max(1, int(sell_hours_buffer))
        buy_hours = list(hourly_avg.nsmallest(k_b).index.astype(int))
        sell_hours = list(hourly_avg.nlargest(k_s).index.astype(int))
        avg_buy = float(hourly_avg.iloc[buy_hours].mean()) if k_b > 0 else float('nan')
        avg_sell = float(hourly_avg.iloc[sell_hours].mean()) if k_s > 0 else float('nan')
        e = float(round_trip_efficiency)
        cap = float(capacity_mwh)
        P = float(power_mw)
        # Energy per cycle limited by power windows and capacity + efficiency
        max_discharge_by_power = P * k_s
        max_charge_by_power = P * k_b
        max_discharge_by_capacity = e * min(cap, max_charge_by_power)
        E_discharge = max(0.0, min(max_discharge_by_power, max_discharge_by_capacity))
        # Profit per cycle based on prices
        profit_per_cycle = E_discharge * avg_sell - (E_discharge / e) * avg_buy if E_discharge > 0 else 0.0
        # Cycles/day limited by available hours
        max_cycles_by_hours = max(1, 24 // (k_b + k_s))
        cycles_used = max(1, min(int(cycles_per_day), int(max_cycles_by_hours)))
        daily_profit = profit_per_cycle * cycles_used
        annual_profit = daily_profit * 365.0
        roi_percent = (annual_profit / float(investment_eur) * 100.0) if investment_eur and annual_profit > 0 else 0.0
        payback_years = (float(investment_eur) / annual_profit) if annual_profit > 0 else float('inf')
        return {
            'analysis_type': f'{min_years}y Hour-of-day buffer strategy',
            'buy_hours': buy_hours,
            'sell_hours': sell_hours,
            'avg_buy_eur_mwh': avg_buy,
            'avg_sell_eur_mwh': avg_sell,
            'energy_sold_mwh_per_cycle': E_discharge,
            'profit_per_cycle_eur': profit_per_cycle,
            'cycles_used_per_day': cycles_used,
            'daily_profit_eur': daily_profit,
            'annual_profit_eur': annual_profit,
            'roi_annual_percent': roi_percent,
            'payback_years': payback_years,
        }
    except Exception as e:
        return {'error': f'Failed multi-hour strategy planning: {e}'}

def render_historical_market_comparison(cfg: dict, capacity_mwh: float, eta_rt: float) -> None:
    """Render comparison using cached results from PZU Horizons and FR Simulator."""
    st.caption("This comparison reuses the most recent runs of the PZU Horizons and FR Simulator views.")

    pzu_metrics = st.session_state.get("pzu_market_metrics")
    if not pzu_metrics or not isinstance(pzu_metrics, dict) or "daily_history" not in pzu_metrics:
        st.info("Run the PZU Horizons view and recompute results to populate comparison data.")
        return

    daily_history_raw = pzu_metrics.get("daily_history")
    if daily_history_raw is None:
        st.info("No PZU profitability data available. Run PZU Horizons first.")
        return

    if isinstance(daily_history_raw, pd.DataFrame):
        daily_history = daily_history_raw.copy()
    else:
        daily_history = pd.DataFrame(daily_history_raw)

    if daily_history.empty:
        st.info("No PZU profitability data available. Run PZU Horizons first.")
        return

    daily_history["date"] = pd.to_datetime(daily_history["date"], errors="coerce")
    daily_history = daily_history.dropna(subset=["date"]).sort_values("date")
    pzu_monthly = (
        daily_history.assign(month=daily_history["date"].dt.to_period("M"))
        .groupby("month", as_index=False)["daily_profit_eur"]
        .sum()
        .rename(columns={"daily_profit_eur": "total_profit_eur"})
    )
    pzu_monthly["month"] = pzu_monthly["month"].astype(str)
    total_months = len(pzu_monthly)
    if total_months == 0:
        st.info("No monthly PZU data available for comparison.")
        return

    default_window = min(12, total_months)
    window = st.slider("Window (months)", min_value=1, max_value=total_months, value=default_window, step=1)

    pzu_window = pzu_monthly.tail(window).reset_index(drop=True)
    pzu_total_profit = float(pzu_window["total_profit_eur"].sum())
    pzu_annualized_profit = pzu_total_profit * (12.0 / len(pzu_window)) if len(pzu_window) else 0.0

    fr_metrics = st.session_state.get("fr_market_metrics")
    fr_window = pd.DataFrame()
    fr_total_revenue = 0.0
    fr_annualized_revenue = 0.0
    if isinstance(fr_metrics, dict) and fr_metrics.get("months"):
        fr_months_df = pd.DataFrame(fr_metrics["months"])
        if not fr_months_df.empty and "month" in fr_months_df.columns:
            try:
                fr_months_df["month_period"] = pd.PeriodIndex(fr_months_df["month"], freq="M")
            except Exception:
                fr_months_df["month_period"] = pd.to_datetime(fr_months_df["month"], errors="coerce").dt.to_period("M")
            fr_months_df = fr_months_df.dropna(subset=["month_period"]).sort_values("month_period")
            fr_months_df["month"] = fr_months_df["month_period"].astype(str)
            window_fr = min(window, len(fr_months_df))
            if window_fr > 0:
                fr_window = fr_months_df.tail(window_fr).reset_index(drop=True)
                fr_total_revenue = float(fr_window["total_revenue_eur"].sum())
                fr_annualized_revenue = fr_total_revenue * (12.0 / window_fr)

    st.subheader("Aggregated Results")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**OPCOM PZU (Arbitrage)**")
        st.metric("Total profit (window)", format_currency(pzu_total_profit, decimals=currency_decimals, thousands=thousands_sep))
        st.metric("Annualized profit", format_currency(pzu_annualized_profit, decimals=currency_decimals, thousands=thousands_sep))
        st.caption(
            "Months used: "
            + ", ".join(pzu_window["month"].tolist())
            if not pzu_window.empty
            else "No months selected"
        )
    with col2:
        st.markdown("**FR Revenue (TRANSELECTRICA)**")
        if not fr_window.empty:
            st.metric("Total revenue (window)", format_currency(fr_total_revenue, decimals=currency_decimals, thousands=thousands_sep))
            st.metric("Annualized revenue", format_currency(fr_annualized_revenue, decimals=currency_decimals, thousands=thousands_sep))
            window_energy_cost = float(fr_window.get("energy_cost_eur", 0.0).sum())
            st.metric(
                "Energy cost (window)",
                format_currency(window_energy_cost, decimals=currency_decimals, thousands=thousands_sep),
            )
            fr_net_margin = fr_total_revenue - window_energy_cost
            st.metric(
                "Net profit (window)",
                format_currency(fr_net_margin, decimals=currency_decimals, thousands=thousands_sep),
            )
            st.caption(
                "Months used: "
                + ", ".join(fr_window["month"].tolist())
            )
        else:
            st.info("FR Simulator data unavailable for the selected window.")

    st.subheader("PZU Monthly Detail")
    pzu_display = pzu_window.rename(columns={"month": "Month", "total_profit_eur": "Profit €"})
    pzu_display["Profit €"] = pzu_display["Profit €"].apply(
        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep)
    )
    st.dataframe(pzu_display, width='stretch')

    if not fr_window.empty:
        st.subheader("FR Monthly Detail")
        fr_display = fr_window.rename(
            columns={
                "month": "Month",
                "capacity_revenue_eur": "Capacity €",
                "activation_revenue_eur": "Activation €",
                "total_revenue_eur": "Total €",
            }
        )
        if "activation_energy_mwh" in fr_window.columns:
            fr_display["Energy MWh"] = fr_window["activation_energy_mwh"].map(lambda v: f"{float(v):.2f}")
        fr_display["Energy cost €"] = fr_window.get("energy_cost_eur", 0.0).apply(
            lambda v: format_currency(float(v), decimals=currency_decimals, thousands=thousands_sep)
        )
        for col in ["Capacity €", "Activation €", "Total €"]:
            fr_display[col] = fr_display[col].apply(
                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep)
            )
        st.dataframe(fr_display, width='stretch')

        annual_info = fr_metrics.get("annual") if isinstance(fr_metrics, dict) else None
        three_year_info = fr_metrics.get("three_year") if isinstance(fr_metrics, dict) else None

        if annual_info:
            annual_table = pd.DataFrame(
                [
                    ("Capacity revenue (12m)", format_currency(annual_info.get("capacity", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Activation revenue (12m)", format_currency(annual_info.get("activation", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Total revenue (12m)", format_currency(annual_info.get("total", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Energy cost (12m)", format_currency(annual_info.get("energy_cost", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Debt service (12m)", format_currency(annual_info.get("debt", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Net profit (12m)", format_currency(annual_info.get("net", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                ],
                columns=["Metric", "Value"],
            )
            st.subheader("FR Annual Cash Flow (from simulator)")
            st.table(annual_table)
            source_months = annual_info.get("source_months")
            if source_months and source_months < 12:
                st.caption(f"Scaled from last {int(source_months)} month(s) of FR data.")

        if three_year_info:
            outlook_table = pd.DataFrame(
                [
                    ("Capacity revenue (3y sim)", format_currency(three_year_info.get("capacity", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Activation revenue (3y sim)", format_currency(three_year_info.get("activation", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Total revenue (3y sim)", format_currency(three_year_info.get("total", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Energy cost (3y)", format_currency(three_year_info.get("energy_cost", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Debt service (3y)", format_currency(three_year_info.get("debt", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                    ("Net profit (3y sim)", format_currency(three_year_info.get("net", 0.0), decimals=currency_decimals, thousands=thousands_sep)),
                ],
                columns=["Metric", "Value"],
            )
            st.subheader("FR Simulated 3-Year Outlook (from simulator)")
            st.table(outlook_table)
def render_frequency_regulation_simulator(cfg: dict) -> None:
    """Render the FR simulator UI (TRANSELECTRICA) with per-product split and optional calendars."""
    st.subheader("⚡ Frequency Regulation Revenue Simulator (TRANSELECTRICA)")
    st.caption("Models grid services revenue: capacity (€/MW/h) + activation (€/MWh). No arbitrage.")
    with st.expander("What is this and how it works?", expanded=False):
        st.markdown(
            "- Operator: TRANSELECTRICA (TSO). Purpose: grid frequency regulation, not energy trading.\n"
            "- Inputs: contracted MW per product (FCR/aFRR/mFRR), capacity €/MW/h, optional activation thresholds.\n"
            "- Capacity revenue: sum(available_MW × 0.25 h × capacity_price) over all 15‑min slots.\n"
            "- Activation revenue: when estimated imbalance price ≥ up_thr or ≤ −down_thr, we assume full available MW is activated for that 15‑min slot; revenue = |price| × energy(MWh).\n"
            "- Source data: export‑8 Excel with estimated imbalance prices; RON→EUR converted at provided FX.\n"
            "- Caveats: This is an approximation; use official settlement data for precise results."
        )

    fr_cfg = cfg.get('fr_products', {}) if cfg else {}
    data_cfg = cfg.get('data', {}) if cfg else {}
    cfg_fx = float(data_cfg.get('fx_ron_per_eur', 5.0))

    sample_export8 = project_root / "data" / "export-8-sample.xlsx"
    sample_sysimb = project_root / "data" / "Estimated power system imbalance.xlsx"
    default_export8 = (
        "export-8.xlsx"
        if Path("export-8.xlsx").exists()
        else (
            "downloads/transelectrica_imbalance/export-8.xlsx"
            if Path("downloads/transelectrica_imbalance/export-8.xlsx").exists()
            else (str(sample_export8) if sample_export8.exists() else (
                _find_in_data_dir([
                    r"export-8\\.xlsx",
                    r"export_8\\.xlsx",
                    r"estimated.*price.*xlsx",
                    r"price.*imbalance.*xlsx",
                ])
                or ""
            ))
        )
    )
    colx1, colx2 = st.columns([2, 1])
    with colx1:
        price_candidates = _list_in_data_dir([r"export[-_]?8\\.xlsx", r"estimated.*price.*xlsx", r"price.*imbalance.*xlsx", r"imbalance.*price.*csv"]) or []
        if not price_candidates:
            price_candidates = _list_in_data_dir([r".*\\.xlsx$", r".*\\.xls$"]) or []
        selected_price = st.selectbox("Detected price files", options=["(none)"] + price_candidates, key='fr_price_detect')
        if 'fr_price_path' not in st.session_state:
            st.session_state['fr_price_path'] = default_export8 or (price_candidates[0] if price_candidates else "")
        use_sel_price = st.button("Use selected price", key='fr_use_price')
        if use_sel_price and selected_price != "(none)":
            st.session_state['fr_price_path'] = selected_price
        export8_path = st.text_input("Path to export-8 Excel or folder", key='fr_price_path')

        sysimb_candidates = _list_in_data_dir([
            r"estimated.*power.*system.*imbalance",
            r"power.*system.*imbalance",
            r"imbalance.*system.*xlsx",
            r"imbalance.*system.*csv",
        ]) or []
        if not sysimb_candidates:
            sysimb_candidates = _list_in_data_dir([r".*\\.xlsx$", r".*\\.xls$", r".*\\.csv$"]) or []
        selected_sysimb = st.selectbox(
            "Detected system imbalance files",
            options=["(none)"] + sysimb_candidates,
            key='fr_sysimb_detect',
        )
        if 'fr_sysimb_path' not in st.session_state:
            default_sysimb = ""
            if sample_sysimb.exists():
                default_sysimb = str(sample_sysimb)
            else:
                default_sysimb = _find_in_data_dir([
                    r"estimated.*power.*system.*imbalance",
                    r"imbalance.*power.*system",
                ]) or ""
            st.session_state['fr_sysimb_path'] = default_sysimb
        use_sel_sysimb = st.button("Use selected imbalance", key='fr_use_sysimb')
        if use_sel_sysimb and selected_sysimb != "(none)":
            st.session_state['fr_sysimb_path'] = selected_sysimb
        sysimb_path = st.text_input("System imbalance Excel/folder", key='fr_sysimb_path')

    with colx2:
        excel_currency = st.selectbox("Excel currency", options=["RON","EUR"], index=0)
        fx_rate = st.number_input("FX RON/EUR", min_value=1.0, max_value=10.0, value=cfg_fx, step=0.1, help="Used if Excel prices are in RON/MWh")

    pay_down_positive = st.checkbox("Pay down‑activation as positive", value=True, help="If off, negative prices reduce revenue. Some products may be settled differently; this toggle lets you choose.")

    st.markdown("---")
    st.caption("Per-product settings (enable at least one):")
    e1, e2, e3 = st.columns(3)
    with e1:
        fcrd = fr_cfg.get('FCR', {})
        fcr_enabled = st.checkbox("Enable FCR", value=bool(fcrd.get('enabled', True)))
        fcr_mw = st.number_input("FCR MW (contracted)", min_value=0.0, max_value=200.0, value=float(fcrd.get('contracted_mw', 10.0)), step=1.0, help="MW reserved/contracted for FCR")
        fcr_cap = st.number_input("FCR capacity €/MW/h", min_value=0.0, max_value=1000.0, value=float(fcrd.get('capacity_eur_per_mw_h', 7.5)), step=0.5, help="Availability payment per MW per hour")
        fcr_up = st.number_input("FCR up threshold €/MWh", min_value=0.0, max_value=500.0, value=float(fcrd.get('up_threshold_eur_mwh', 0.0)), step=1.0, help="Min price to count up‑activation")
        fcr_down = st.number_input("FCR down threshold €/MWh", min_value=0.0, max_value=500.0, value=float(fcrd.get('down_threshold_eur_mwh', 0.0)), step=1.0, help="Min |price| to count down‑activation")
        fcr_down_pos = st.checkbox("FCR: down‑activation paid positive", value=True, help="Treat down regulation energy as positive revenue (|price| × energy)")
        fcr_act = st.number_input("FCR activation factor (0–1)", min_value=0.0, max_value=1.0, value=0.05, step=0.01, help="Scales activation energy to a realistic duty factor")
    with e2:
        afrrd = fr_cfg.get('aFRR', {})
        afrr_enabled = st.checkbox("Enable aFRR", value=bool(afrrd.get('enabled', True)))
        afrr_mw = st.number_input("aFRR MW (contracted)", min_value=0.0, max_value=200.0, value=float(afrrd.get('contracted_mw', 10.0)), step=1.0, help="MW reserved/contracted for aFRR")
        afrr_cap = st.number_input("aFRR capacity €/MW/h", min_value=0.0, max_value=1000.0, value=float(afrrd.get('capacity_eur_per_mw_h', 5.0)), step=0.5, help="Availability payment per MW per hour")
        afrr_up = st.number_input("aFRR up threshold €/MWh", min_value=0.0, max_value=500.0, value=float(afrrd.get('up_threshold_eur_mwh', 0.0)), step=1.0, help="Min price to count up‑activation")
        afrr_down = st.number_input("aFRR down threshold €/MWh", min_value=0.0, max_value=500.0, value=float(afrrd.get('down_threshold_eur_mwh', 0.0)), step=1.0, help="Min |price| to count down‑activation")
        afrr_down_pos = st.checkbox("aFRR: down‑activation paid positive", value=True)
        afrr_act = st.number_input("aFRR activation factor (0–1)", min_value=0.0, max_value=1.0, value=0.10, step=0.01)
    with e3:
        mfrrd = fr_cfg.get('mFRR', {})
        mfrr_enabled = st.checkbox("Enable mFRR", value=bool(mfrrd.get('enabled', False)))
        mfrr_mw = st.number_input("mFRR MW (contracted)", min_value=0.0, max_value=200.0, value=float(mfrrd.get('contracted_mw', 0.0)), step=1.0, help="MW reserved/contracted for mFRR")
        mfrr_cap = st.number_input("mFRR capacity €/MW/h", min_value=0.0, max_value=1000.0, value=float(mfrrd.get('capacity_eur_per_mw_h', 0.0)), step=0.5, help="Availability payment per MW per hour")
        mfrr_up = st.number_input("mFRR up threshold €/MWh", min_value=0.0, max_value=500.0, value=float(mfrrd.get('up_threshold_eur_mwh', 0.0)), step=1.0, help="Min price to count up‑activation")
        mfrr_down = st.number_input("mFRR down threshold €/MWh", min_value=0.0, max_value=500.0, value=float(mfrrd.get('down_threshold_eur_mwh', 0.0)), step=1.0, help="Min |price| to count down‑activation")
        mfrr_down_pos = st.checkbox("mFRR: down‑activation paid positive", value=True)
        mfrr_act = st.number_input("mFRR activation factor (0–1)", min_value=0.0, max_value=1.0, value=0.10, step=0.01)

    products_cfg = {
        'FCR': {'enabled': fcr_enabled, 'mw': fcr_mw, 'cap_eur_mw_h': fcr_cap, 'up_thr': fcr_up, 'down_thr': fcr_down},
        'aFRR': {'enabled': afrr_enabled, 'mw': afrr_mw, 'cap_eur_mw_h': afrr_cap, 'up_thr': afrr_up, 'down_thr': afrr_down},
        'mFRR': {'enabled': mfrr_enabled, 'mw': mfrr_mw, 'cap_eur_mw_h': mfrr_cap, 'up_thr': mfrr_up, 'down_thr': mfrr_down},
    }
    paydown_map = {'FCR': fcr_down_pos, 'aFRR': afrr_down_pos, 'mFRR': mfrr_down_pos}
    act_map = {'FCR': fcr_act, 'aFRR': afrr_act, 'mFRR': mfrr_act}

    ref_cols = st.columns(3)
    with ref_cols[0]:
        fcr_ref_mw = st.number_input(
            "FCR activation reference MW",
            min_value=1.0,
            max_value=2000.0,
            value=float(fr_cfg.get('FCR', {}).get('activation_reference_mw', 50.0)),
            step=1.0,
            help="Approximate total MW of imbalance reserve to normalise FCR activation factors.",
        )
    with ref_cols[1]:
        afrr_ref_mw = st.number_input(
            "aFRR activation reference MW",
            min_value=1.0,
            max_value=2000.0,
            value=float(fr_cfg.get('aFRR', {}).get('activation_reference_mw', 80.0)),
            step=1.0,
        )
    with ref_cols[2]:
        mfrr_ref_mw = st.number_input(
            "mFRR activation reference MW",
            min_value=1.0,
            max_value=2000.0,
            value=float(fr_cfg.get('mFRR', {}).get('activation_reference_mw', 120.0)),
            step=1.0,
        )

    smoothing_option = st.selectbox(
        "Activation profile smoothing",
        options=["Per ISP", "Monthly average"],
        index=1,
        help="Whether to average activation factors per 15-min slot or by month to reduce volatility.",
    )

    pricing_mode_label = st.selectbox(
        "Activation pricing mode",
        options=["Pay-as-bid (manual)", "Market prices (export data)"]
    )
    activation_price_mode = "pay_as_bid" if pricing_mode_label == "Pay-as-bid (manual)" else "market"

    pay_as_bid_map: Dict[str, Dict[str, float]] = {}
    if activation_price_mode == "pay_as_bid":
        st.caption("Enter the accepted pay-as-bid activation prices (€/MWh) for each product.")
        pay_cols = st.columns(3)
        with pay_cols[0]:
            fcr_up_price = st.number_input(
                "FCR up €/MWh",
                min_value=0.0,
                max_value=1000.0,
                value=float(fr_cfg.get('FCR', {}).get('pay_as_bid_up', 80.0)),
                step=1.0,
            )
            fcr_down_price = st.number_input(
                "FCR down €/MWh",
                min_value=-1000.0,
                max_value=1000.0,
                value=float(fr_cfg.get('FCR', {}).get('pay_as_bid_down', 80.0)),
                step=1.0,
            )
            pay_as_bid_map['FCR'] = {'up_price': fcr_up_price, 'down_price': fcr_down_price}
        with pay_cols[1]:
            afrr_up_price = st.number_input(
                "aFRR up €/MWh",
                min_value=0.0,
                max_value=1000.0,
                value=float(fr_cfg.get('aFRR', {}).get('pay_as_bid_up', 90.0)),
                step=1.0,
            )
            afrr_down_price = st.number_input(
                "aFRR down €/MWh",
                min_value=-1000.0,
                max_value=1000.0,
                value=float(fr_cfg.get('aFRR', {}).get('pay_as_bid_down', 90.0)),
                step=1.0,
            )
            pay_as_bid_map['aFRR'] = {'up_price': afrr_up_price, 'down_price': afrr_down_price}
        with pay_cols[2]:
            mfrr_up_price = st.number_input(
                "mFRR up €/MWh",
                min_value=0.0,
                max_value=1000.0,
                value=float(fr_cfg.get('mFRR', {}).get('pay_as_bid_up', 100.0)),
                step=1.0,
            )
            mfrr_down_price = st.number_input(
                "mFRR down €/MWh",
                min_value=-1000.0,
                max_value=1000.0,
                value=float(fr_cfg.get('mFRR', {}).get('pay_as_bid_down', 100.0)),
                step=1.0,
            )
            pay_as_bid_map['mFRR'] = {'up_price': mfrr_up_price, 'down_price': mfrr_down_price}

    st.caption("Optional availability calendars (CSV/XLSX). Columns: date, slot, available_mw or available(0/1).")
    cal1, cal2, cal3 = st.columns(3)
    with cal1:
        fcr_cal_path = st.text_input("FCR calendar path", value=str(fr_cfg.get('FCR', {}).get('calendar_csv', "")))
        fcr_cal_upload = st.file_uploader("Upload FCR calendar", type=['csv','xlsx','xls'], key='fcr_cal')
    with cal2:
        afrr_cal_path = st.text_input("aFRR calendar path", value=str(fr_cfg.get('aFRR', {}).get('calendar_csv', "")))
        afrr_cal_upload = st.file_uploader("Upload aFRR calendar", type=['csv','xlsx','xls'], key='afrr_cal')
    with cal3:
        mfrr_cal_path = st.text_input("mFRR calendar path", value=str(fr_cfg.get('mFRR', {}).get('calendar_csv', "")))
        mfrr_cal_upload = st.file_uploader("Upload mFRR calendar", type=['csv','xlsx','xls'], key='mfrr_cal')

    calendars_cfg: Dict[str, pd.DataFrame] = {}
    fcr_df = _normalize_calendar_df(_read_calendar_df(fcr_cal_upload) or _read_calendar_df(fcr_cal_path))
    if fcr_df is not None:
        calendars_cfg['FCR'] = fcr_df
    afrr_df = _normalize_calendar_df(_read_calendar_df(afrr_cal_upload) or _read_calendar_df(afrr_cal_path))
    if afrr_df is not None:
        calendars_cfg['aFRR'] = afrr_df
    mfrr_df = _normalize_calendar_df(_read_calendar_df(mfrr_cal_upload) or _read_calendar_df(mfrr_cal_path))
    if mfrr_df is not None:
        calendars_cfg['mFRR'] = mfrr_df

    # Sanity check: enforce power cap warning and allow auto-load battery specs from technical proposal
    try:
        total_mw = sum([v for k, v in {'FCR': fcr_mw, 'aFRR': afrr_mw, 'mFRR': mfrr_mw}.items() if {'FCR': fcr_enabled, 'aFRR': afrr_enabled, 'mFRR': mfrr_enabled}[k]])
        if total_mw > power_mw:
            st.warning(f"Configured MW ({total_mw} MW) exceeds battery power ({power_mw} MW). Consider reducing per‑product MW or using calendars.")
    except Exception:
        pass

    with st.expander("Battery specs (auto from Technical Proposal)", expanded=False):
        tech_doc = _find_in_data_dir([r"technical.*proposal.*mey.*energy", r"20mw.*55mwh", r"bess.*project"]) or ""
        tech_path = st.text_input("Battery spec document (PDF)", value=tech_doc)
        use_specs = st.checkbox("Use extracted specs to cap power/efficiency", value=True)
        extracted = parse_battery_specs_from_document(tech_path) if tech_path else {}
        if extracted:
            st.json(extracted)
        # Apply extracted power and efficiency if available
        cap_power_mw = power_mw
        if use_specs and extracted:
            if extracted.get('power_mw'):
                cap_power_mw = float(extracted['power_mw'])
            if extracted.get('round_trip_efficiency'):
                st.caption(f"Using extracted round-trip efficiency {extracted['round_trip_efficiency']:.2f} for activation energy scaling (informational)")
        else:
            cap_power_mw = power_mw

    sysimb_df = pd.DataFrame()
    activation_reference_map = {
        'FCR': fcr_ref_mw,
        'aFRR': afrr_ref_mw,
        'mFRR': mfrr_ref_mw,
    }
    activation_curves_map: Dict[str, pd.Series] = {}

    if sysimb_path:
        try:
            sysimb_df = load_system_imbalance_from_excel(sysimb_path)
            if sysimb_df.empty:
                st.info("System imbalance file loaded but contained no usable rows.")
        except Exception as exc:
            sysimb_df = pd.DataFrame()
            st.warning(f"Failed to load system imbalance data: {exc}")

    smoothing_flag = 'monthly' if smoothing_option == 'Monthly average' else None

    if not sysimb_df.empty:
        for prod, ref in activation_reference_map.items():
            if ref and ref > 0:
                series = compute_activation_factor_series(sysimb_df, ref, smoothing=smoothing_flag)
                if not series.empty:
                    activation_curves_map[prod] = series
        if activation_curves_map:
            st.caption("Using system imbalance history to derive activation duty factors.")

    has_imbalance_flag = not sysimb_df.empty

    if export8_path:
        try:
            imb_df = load_transelectrica_imbalance_from_excel(
                export8_path,
                fx_ron_per_eur=(1.0 if excel_currency == 'EUR' else fx_rate),
                declared_currency=excel_currency,
            )
            if not imb_df.empty and any(v.get('enabled') and v.get('mw', 0) > 0 for v in products_cfg.values()):
                src_cur = []
                if 'source_currency' in imb_df.columns:
                    src_cur = sorted({str(v) for v in imb_df['source_currency'].dropna().unique() if str(v).strip()})
                if src_cur:
                    if len(src_cur) == 1:
                        cur_label = src_cur[0]
                        st.caption(f"Detected imbalance currency: {cur_label} (internal pricing in EUR)")
                        if excel_currency.upper() != cur_label:
                            st.info(
                                f"File reports {cur_label}; the '{excel_currency}' selection was overridden during import."
                            )
                    else:
                        st.caption(
                            "Detected imbalance currencies: "
                            + ", ".join(src_cur)
                            + " (each converted to EUR before simulation)"
                        )
                price_dates_ts = pd.to_datetime(imb_df['date'], errors='coerce').dropna()
                hedge_coverage = 0.0
                hedge_avg = None
                if provider.pzu_csv and not price_dates_ts.empty:
                    hedge_curve = build_hedge_price_curve(
                        provider.pzu_csv,
                        start_date=price_dates_ts.min(),
                        end_date=price_dates_ts.max(),
                        fx_ron_per_eur=fx_rate,
                    )
                    if not hedge_curve.empty:
                        imb_df = imb_df.merge(hedge_curve, on=['date', 'slot'], how='left')
                        hedge_mask = imb_df['hedge_price_eur_mwh'].notna()
                        if hedge_mask.any():
                            hedge_coverage = float(hedge_mask.mean())
                            hedge_avg = float(imb_df.loc[hedge_mask, 'hedge_price_eur_mwh'].mean())
                            st.caption(
                                f"Energy cost reference: OPCOM PZU prices applied to {hedge_coverage*100:.1f}%"
                                " of slots"
                                + (f" (avg €{hedge_avg:.1f}/MWh)" if hedge_avg is not None else "")
                            )
                        else:
                            st.info("PZU hedge curve has no overlapping slots for this period; falling back to imbalance prices for energy cost.")
                    else:
                        st.info("PZU hedge curve not available for the selected window; falling back to imbalance prices for energy cost.")

                # Threshold suggestions from percentiles
                try:
                    pos = imb_df.loc[imb_df['price_eur_mwh'] > 0, 'price_eur_mwh']
                    neg = imb_df.loc[imb_df['price_eur_mwh'] < 0, 'price_eur_mwh'].abs()
                    if len(pos) > 0 or len(neg) > 0:
                        s1, s2 = st.columns(2)
                        with s1:
                            if len(pos) > 0:
                                st.caption("Suggested up thresholds (percentiles):")
                                st.write(f"P90: €{pos.quantile(0.9):.1f} | P95: €{pos.quantile(0.95):.1f}")
                        with s2:
                            if len(neg) > 0:
                                st.caption("Suggested down thresholds (percentiles of |price|):")
                                st.write(f"P90: €{neg.quantile(0.9):.1f} | P95: €{neg.quantile(0.95):.1f}")
                except Exception:
                    pass
                price_dates = pd.to_datetime(imb_df['date'], errors='coerce').dropna().dt.normalize().unique()
                has_imbalance_flag = bool(activation_curves_map)
                simm = simulate_frequency_regulation_revenue_multi(
                    imb_df,
                    products_cfg,
                    pay_down_as_positive=pay_down_positive,
                    pay_down_positive_map=paydown_map,
                    activation_factor_map=act_map,
                    calendars=calendars_cfg,
                    system_imbalance_df=sysimb_df,
                    activation_curve_map=activation_curves_map,
                    activation_price_mode=activation_price_mode,
                    pay_as_bid_map=pay_as_bid_map if activation_price_mode == 'pay_as_bid' else None,
                    battery_power_mw=cap_power_mw,
                )

                st.success(f"Computed revenue for {simm['combined_totals']['months']} months of data")
                months_comb = simm['combined_monthly']
                if months_comb:
                    st.subheader("Combined Monthly Revenue (All Products)")
                    comb_df = pd.DataFrame(months_comb)
                    currency_cols = ['capacity_revenue_eur','activation_revenue_eur','total_revenue_eur']
                    float_cols = ['hours_in_data']
                    if show_raw_tables:
                        st.dataframe(comb_df, width='stretch')
                    else:
                                st.dataframe(
                                    styled_table(
                                        comb_df,
                                        currency_cols=currency_cols,
                                        float_cols=float_cols,
                                        currency_decimals=currency_decimals,
                                        float_decimals=float_decimals,
                                        thousands=thousands_sep,
                                    ),
                                    width='stretch',
                                )

                    def sum_window(months, w):
                        sub = months[-w:]
                        cap = sum(m['capacity_revenue_eur'] for m in sub)
                        act = sum(m['activation_revenue_eur'] for m in sub)
                        tot = cap + act
                        return cap, act, tot, len(sub)

                    # Use only months we actually have
                    if len(months_comb) > 0:
                        cap_all = sum(m['capacity_revenue_eur'] for m in months_comb)
                        act_all = sum(m['activation_revenue_eur'] for m in months_comb)
                        tot_all = cap_all + act_all
                        energy_cost_total = float(sum(m.get('energy_cost_eur', 0.0) for m in months_comb))
                        activation_energy_total = float(sum(m.get('activation_energy_mwh', 0.0) for m in months_comb))
                        g1, g2, g3, g4 = st.columns(4)
                        label = f"{len(months_comb)}m"
                        g1.metric(f"Capacity revenue ({label})", format_currency(cap_all, decimals=currency_decimals, thousands=thousands_sep))
                        g2.metric(f"Activation revenue ({label})", format_currency(act_all, decimals=currency_decimals, thousands=thousands_sep))
                        g3.metric(f"Total ({label})", format_currency(tot_all, decimals=currency_decimals, thousands=thousands_sep))
                        g4.metric(
                            "Energy cost (window)",
                            format_currency(energy_cost_total, decimals=currency_decimals, thousands=thousands_sep),
                        )
                        st.caption(
                            f"Activation energy ({label}) ≈ {activation_energy_total:.0f} MWh"
                        )

                        try:
                            print(
                                f"[FR DEBUG] Window {label}: cap={cap_all:.2f}€ act={act_all:.2f}€ net_energy={activation_energy_total:.2f}MWh hedge_cost={energy_cost_total:.2f}€",
                            )
                        except Exception:
                            pass

                        # Highlight when external constraints suppress activation volumes
                        enabled_products = [
                            (prod, cfg)
                            for prod, cfg in products_cfg.items()
                            if cfg.get('enabled') and cfg.get('mw', 0) > 0
                        ]
                        total_enabled_mw = sum(cfg.get('mw', 0.0) for _, cfg in enabled_products)
                        if total_enabled_mw > 0:
                            weighted_activation = sum(
                                cfg.get('mw', 0.0) * act_map.get(prod, 1.0)
                                for prod, cfg in enabled_products
                            ) / total_enabled_mw
                            hours_total = sum(m.get('hours_in_data', 0.0) for m in months_comb)
                            theoretical_energy = hours_total * total_enabled_mw * weighted_activation
                            if theoretical_energy > 0:
                                utilisation = activation_energy_total / theoretical_energy
                                if utilisation < 0.15 and has_imbalance_flag:
                                    st.info(
                                        "Activation volumes are only "
                                        f"{utilisation:.1%} of the theoretical duty factor. Check the system imbalance data "
                                        "or activation factors if you expect higher dispatch."
                                    )

                        # Annual cash flow summary (normalized to 12 months)
                        annual_debt_service = 0.0
                        recent_months = months_comb[-12:]
                        months_used = len(recent_months)
                        if months_used > 0:
                            cap_recent = sum(m['capacity_revenue_eur'] for m in recent_months)
                            act_recent = sum(m['activation_revenue_eur'] for m in recent_months)
                            energy_recent = sum(m.get('activation_energy_mwh', 0.0) for m in recent_months)
                            energy_cost_recent = sum(m.get('energy_cost_eur', 0.0) for m in recent_months)
                            total_recent = cap_recent + act_recent
                            scale_factor = 12 / months_used
                            annual_cap = cap_recent * scale_factor
                            annual_act = act_recent * scale_factor
                            annual_total = annual_cap + annual_act
                            annual_energy = energy_recent * scale_factor
                            annual_energy_cost = energy_cost_recent * scale_factor
                            annual_net = annual_total - annual_debt_service - annual_energy_cost

                            annual_table = pd.DataFrame(
                                [
                                    ("Capacity revenue (12m)", format_currency(annual_cap, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Activation revenue (12m)", format_currency(annual_act, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Total revenue (12m)", format_currency(annual_total, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Energy cost (12m)", format_currency(annual_energy_cost, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Debt service (12m)", format_currency(annual_debt_service, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Net profit (12m)", format_currency(annual_net, decimals=currency_decimals, thousands=thousands_sep)),
                                ],
                                columns=["Metric", "Value"],
                            )
                            st.subheader("FR Annual Cash Flow (normalized 12m)")
                            st.table(annual_table)
                            if months_used < 12:
                                st.caption(f"Scaled from last {months_used} month(s) of data.")

                            three_year_cap = annual_cap * 3
                            three_year_act = annual_act * 3
                            three_year_total = annual_total * 3
                            three_year_debt = annual_debt_service * 3
                            three_year_energy_cost = annual_energy_cost * 3
                            three_year_net = three_year_total - three_year_debt - three_year_energy_cost

                            outlook_table = pd.DataFrame(
                                [
                                    ("Capacity revenue (3y sim)", format_currency(three_year_cap, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Activation revenue (3y sim)", format_currency(three_year_act, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Total revenue (3y sim)", format_currency(three_year_total, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Energy cost (3y)", format_currency(three_year_energy_cost, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Debt service (3y)", format_currency(three_year_debt, decimals=currency_decimals, thousands=thousands_sep)),
                                    ("Net profit (3y sim)", format_currency(three_year_net, decimals=currency_decimals, thousands=thousands_sep)),
                                ],
                                columns=["Metric", "Value"],
                            )
                            st.subheader("FR Simulated 3-Year Outlook")
                            st.table(outlook_table)

                            try:
                                months_payload = [
                                    _sanitize_session_value(dict(rec)) for rec in months_comb
                                ]
                                annual_payload = _sanitize_session_value(
                                    {
                                        "capacity": float(annual_cap),
                                        "activation": float(annual_act),
                                        "total": float(annual_total),
                                        "energy": float(annual_energy),
                                        "energy_cost": float(annual_energy_cost),
                                        "debt": float(annual_debt_service),
                                        "net": float(annual_net),
                                        "source_months": int(months_used),
                                        "cost_rate": (float(annual_energy_cost) / float(annual_energy)) if annual_energy > 0 else 0.0,
                                    }
                                )
                                three_year_payload = _sanitize_session_value(
                                    {
                                        "capacity": float(three_year_cap),
                                        "activation": float(three_year_act),
                                        "total": float(three_year_total),
                                        "energy_cost": float(three_year_energy_cost),
                                        "debt": float(three_year_debt),
                                        "net": float(three_year_net),
                                    }
                                )
                                new_fr_metrics = {
                                    "months": months_payload,
                                    "annual": annual_payload,
                                    "three_year": three_year_payload,
                                }
                                safe_session_state_update("fr_market_metrics", new_fr_metrics)
                            except Exception:
                                pass

                            monthly_debt_share = annual_debt_service / 12.0 if annual_debt_service else 0.0
                            monthly_rows = []
                            for rec in months_comb:
                                month_label = rec.get("month") or rec.get("month_period")
                                month_label = str(month_label)
                                cap_val = float(rec.get("capacity_revenue_eur", 0.0))
                                act_val = float(rec.get("activation_revenue_eur", 0.0))
                                tot_val = cap_val + act_val
                                energy_val = float(rec.get('activation_energy_mwh', 0.0))
                                monthly_energy_cost = float(rec.get('energy_cost_eur', 0.0))
                                net_val = tot_val - monthly_debt_share - monthly_energy_cost
                                monthly_rows.append(
                                    {
                                        "Month": month_label,
                                        "Capacity €": format_currency(cap_val, decimals=currency_decimals, thousands=thousands_sep),
                                        "Activation €": format_currency(act_val, decimals=currency_decimals, thousands=thousands_sep),
                                        "Total €": format_currency(tot_val, decimals=currency_decimals, thousands=thousands_sep),
                                        "Energy MWh": f"{energy_val:.2f}",
                                        "Energy cost €": format_currency(monthly_energy_cost, decimals=currency_decimals, thousands=thousands_sep),
                                        "Debt share €": format_currency(monthly_debt_share, decimals=currency_decimals, thousands=thousands_sep) if monthly_debt_share else "—",
                                        "Net €": format_currency(net_val, decimals=currency_decimals, thousands=thousands_sep),
                                    }
                                )

                            if monthly_rows:
                                monthly_df = pd.DataFrame(monthly_rows)
                                st.subheader("FR Monthly Cash Flow (all months)")
                                st.dataframe(monthly_df, width='stretch')
                else:
                    st.session_state.pop("fr_market_metrics", None)

                st.subheader("Per-Product Revenue")
                for prod in ['FCR', 'aFRR', 'mFRR']:
                        if not products_cfg[prod]['enabled'] or products_cfg[prod]['mw'] <= 0:
                            continue
                        st.caption(f"{prod} contracted: {products_cfg[prod]['mw']} MW @ {products_cfg[prod]['cap_eur_mw_h']} €/MW/h")
                        months_prod = simm['monthly_by_product'].get(prod, [])
                        if months_prod:
                            prod_df = pd.DataFrame(months_prod)
                            currency_cols = ['capacity_revenue_eur','activation_revenue_eur','total_revenue_eur']
                            float_cols = ['hours_in_data']
                            if show_raw_tables:
                                st.dataframe(prod_df, width='stretch')
                            else:
                                st.dataframe(
                                    styled_table(
                                        prod_df,
                                        currency_cols=currency_cols,
                                        float_cols=float_cols,
                                        currency_decimals=currency_decimals,
                                        float_decimals=float_decimals,
                                        thousands=thousands_sep,
                                    ),
                                    width='stretch',
                                )
                            totp = simm['totals_by_product'].get(prod, {})
                            p1, p2, p3 = st.columns(3)
                            p1.metric(f"{prod} Capacity total", format_currency(totp.get('capacity_revenue_eur', 0), decimals=currency_decimals, thousands=thousands_sep))
                            p2.metric(f"{prod} Activation total", format_currency(totp.get('activation_revenue_eur', 0), decimals=currency_decimals, thousands=thousands_sep))
                            p3.metric(f"{prod} Total", format_currency(totp.get('total_revenue_eur', 0), decimals=currency_decimals, thousands=thousands_sep))
                            # Diagnostics: sum of up/down slots
                            ups = sum(r.get('up_slots', 0) for r in months_prod)
                            dns = sum(r.get('down_slots', 0) for r in months_prod)
                            st.caption(f"Diagnostics: up_slots={ups}, down_slots={dns}")
            else:
                st.info("Provide a valid export-8 path and enable at least one product with MW > 0.")
        except Exception as e:
            st.error(f"Failed to read export-8 file(s): {e}")

st.set_page_config(page_title="Battery Bot - PZU & Balancing", layout="wide", page_icon="⚡")

def apply_theme() -> None:
    css_path = project_root / "assets" / "style.css"
    try:
        css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    except Exception:
        css = ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


st.title("Battery Trading Bot - Web Interface")
apply_theme()
st.caption("Choose a view below, set config in the sidebar, then Run Strategy.")

view = st.radio(
    "View",
    options=[
        "PZU Horizons",
        "FR Simulator",
        "Romanian BM",
        "Market Comparison",
        "FR Energy Hedging",
    ],
    horizontal=True,
)

history_start: Optional[pd.Timestamp] = None
history_end: Optional[pd.Timestamp] = None
earliest_available_ts: Optional[pd.Timestamp] = None
latest_available_ts: Optional[pd.Timestamp] = None

with st.sidebar:
    st.header("Configuration")
    cfg_path = st.text_input("Config file", value="config.yaml", help="Path to YAML settings")
    if not Path(cfg_path).exists():
        st.error("config.yaml not found. Adjust the path.")
        st.stop()
    cfg = load_config(cfg_path)
    tz = cfg["execution"]["timezone"]

    # Data sources
    with st.expander("Data Sources", expanded=True):
        default_pzu_csv = cfg["data"].get("pzu_forecast_csv")
        default_bm_csv = cfg["data"].get("bm_forecast_csv")
        pzu_csv_override = st.text_input("PZU history CSV", value=default_pzu_csv or "", help="At least 3 years for robust stats")
        bm_csv_override = st.text_input("BM history CSV", value=default_bm_csv or "")
        provider = DataProvider(pzu_csv=pzu_csv_override or default_pzu_csv, bm_csv=bm_csv_override or default_bm_csv)
        if provider.pzu_csv and not Path(provider.pzu_csv).exists():
            st.warning(f"PZU CSV not found: {provider.pzu_csv}")
        if provider.bm_csv and not Path(provider.bm_csv).exists():
            st.warning(f"Balancing CSV not found: {provider.bm_csv}")

        bm_dates: List[str] = []
        if provider.bm_csv and Path(provider.bm_csv).exists():
            try:
                df_bm_dates = pd.read_csv(provider.bm_csv, usecols=["date"]).dropna()
                bm_dates = sorted(df_bm_dates["date"].astype(str).unique().tolist())
            except Exception:
                bm_dates = []

        pzu_dates: List[str] = []
        if provider.pzu_csv and Path(provider.pzu_csv).exists():
            try:
                df_pzu_dates = pd.read_csv(provider.pzu_csv, usecols=["date"]).dropna()
                pzu_dates = sorted(df_pzu_dates["date"].astype(str).unique().tolist())
            except Exception:
                pzu_dates = []

        available_dates = pzu_dates or bm_dates
        default_date = datetime.fromisoformat((pzu_dates[-1] if pzu_dates else available_dates[-1])).date() if available_dates else date.today()
        min_date = datetime.fromisoformat((pzu_dates[0] if pzu_dates else available_dates[0])).date() if available_dates else None
        max_date = default_date
        chosen_date = st.date_input(
            "Target date",
            value=default_date,
            min_value=min_date,
            max_value=max_date,
            help="Used for balancing-market daily charts.",
        )
        if min_date:
            earliest_available_ts = pd.Timestamp(min_date)
        if max_date:
            latest_available_ts = pd.Timestamp(max_date)

        history_options = [
            "Full history",
            "Last 12 months",
            "Last 24 months",
            "Last 36 months",
            "Custom start date",
            "Custom years range",
        ]
        history_choice = st.selectbox(
            "History window for profitability analysis",
            history_options,
            index=0,
        )

        history_start = None
        history_end = None
        latest_available_ts = None
        if available_dates:
            available_ts = pd.to_datetime(available_dates, errors="coerce")
            available_ts = available_ts.dropna()
            if not available_ts.empty:
                earliest_available_ts = available_ts.min()
                latest_available_ts = available_ts.max()
        if latest_available_ts is None:
            latest_available_ts = pd.Timestamp(date.today())
        if earliest_available_ts is None:
            earliest_available_ts = latest_available_ts

        if history_choice == "Full history":
            history_start = earliest_available_ts
            history_end = latest_available_ts
        elif history_choice == "Last 12 months":
            history_start = latest_available_ts - pd.DateOffset(months=12)
        elif history_choice == "Last 24 months":
            history_start = latest_available_ts - pd.DateOffset(months=24)
        elif history_choice == "Last 36 months":
            history_start = latest_available_ts - pd.DateOffset(months=36)
        elif history_choice == "Custom start date":
            default_start = latest_available_ts - pd.DateOffset(months=12)
            custom_start_input = st.date_input(
                "Select custom start date",
                value=default_start.date(),
                help="Only data on or after this date will be used for cycle calculations.",
            )
            history_start = pd.Timestamp(custom_start_input)
        elif history_choice == "Custom years range":
            min_year = int(available_dates[0][:4]) if available_dates else 2020
            max_year = int(available_dates[-1][:4]) if available_dates else latest_available_ts.year
            col_a, col_b = st.columns(2)
            start_year = col_a.number_input("Start year", min_value=min_year, max_value=max_year, value=min_year)
            end_year = col_b.number_input("End year", min_value=start_year, max_value=max_year, value=max_year)
            history_start = pd.Timestamp(year=int(start_year), month=1, day=1)
            history_end = pd.Timestamp(year=int(end_year), month=12, day=31)

    with st.expander("Battery", expanded=True):
        capacity_default = float(cfg["battery"]["capacity_mwh"])
        power_default = float(cfg["battery"]["power_mw"])
        soc_initial = float(cfg["battery"]["soc_initial"])  # [0..1]
        eta_rt = float(cfg["battery"]["round_trip_efficiency"])  # [0..1]
        capacity_mwh = capacity_default
        power_mw = power_default
        st.caption(
            "Defaults come from config.yaml. Use the controls above the PZU Horizons view to experiment with alternative capacity/power values."
        )

    auto_run = st.checkbox("Auto run (recompute on change)", value=True)
    run_btn = auto_run or st.button("Run Analysis")

    # Display options
    with st.expander("Display", expanded=False):
        currency_decimals = st.slider("Currency decimals", 0, 2, 0)
        percent_decimals = st.slider("Percent decimals", 0, 2, 1)
        float_decimals = st.slider("Float decimals", 0, 4, 2)
        thousands_sep = st.checkbox("Thousands separator", value=True)
        show_raw_tables = st.checkbox("Show raw numeric tables", value=False, help="If on, tables are unformatted for sorting")

if view == "PZU Horizons":
    st.subheader("PZU Profitability Horizons")

    control_cols = st.columns(2)
    capacity_mwh = control_cols[0].number_input(
        "Capacity (MWh)",
        min_value=1.0,
        value=float(capacity_mwh),
        step=1.0,
        key="pzu_horizon_capacity",
    )
    power_mw = control_cols[1].number_input(
        "Power (MW)",
        min_value=0.1,
        value=float(power_mw),
        step=0.5,
        key="pzu_horizon_power",
    )

    date_cols = st.columns(2)
    start_default_ts = history_start or earliest_available_ts or pd.Timestamp(date.today())
    end_default_ts = history_end or latest_available_ts or pd.Timestamp(date.today())
    start_input = date_cols[0].date_input(
        "Start date (inclusive)",
        value=start_default_ts.to_pydatetime().date(),
        min_value=(earliest_available_ts or start_default_ts).to_pydatetime().date(),
        max_value=(latest_available_ts or end_default_ts).to_pydatetime().date(),
        key="pzu_horizon_start",
    )
    end_input = date_cols[1].date_input(
        "End date (inclusive)",
        value=end_default_ts.to_pydatetime().date(),
        min_value=start_input,
        max_value=(latest_available_ts or end_default_ts).to_pydatetime().date(),
        key="pzu_horizon_end",
    )
    history_start = pd.Timestamp(start_input)
    history_end = pd.Timestamp(end_input)
    if history_start > history_end:
        st.warning("Start date is after end date; swapping them.")
        history_start, history_end = history_end, history_start
    if history_start is not None and history_end is not None:
        st.caption(
            f"Analysis window: {history_start.strftime('%Y-%m-%d')} → {history_end.strftime('%Y-%m-%d')}"
        )
    else:
        st.caption("Analysis window: full available history")

if run_btn:
    load_pzu_params = {
        "pzu_csv": provider.pzu_csv,
        "capacity_mwh": capacity_mwh,
        "round_trip_efficiency": eta_rt,
        "power_mw": power_mw,
    }
    sig_load = inspect.signature(load_pzu_daily_history)
    if "start_date" in sig_load.parameters:
        load_pzu_params["start_date"] = history_start
    if "end_date" in sig_load.parameters:
        load_pzu_params["end_date"] = history_end

    daily_history = load_pzu_daily_history(**load_pzu_params)
    horizon_summaries = []
    bm_series = load_balancing_day_series(provider.bm_csv, chosen_date.isoformat())

    fixed_params = {
        "pzu_csv": provider.pzu_csv,
        "capacity_mwh": capacity_mwh,
        "power_mw": power_mw,
        "round_trip_efficiency": eta_rt,
    }
    sig_fixed = inspect.signature(compute_best_fixed_cycle)
    if "start_date" in sig_fixed.parameters:
        fixed_params["start_date"] = history_start
    if "end_date" in sig_fixed.parameters:
        fixed_params["end_date"] = history_end

    fixed_cycle = compute_best_fixed_cycle(**fixed_params)
    fixed_history: pd.DataFrame = fixed_cycle.get("daily_history", pd.DataFrame())
    fixed_summaries = summarize_profit_windows(fixed_history) if not fixed_history.empty else []

    if view == "PZU Horizons":
        fixed_params = {
            "pzu_csv": provider.pzu_csv,
            "capacity_mwh": capacity_mwh,
            "power_mw": power_mw,
            "round_trip_efficiency": eta_rt,
        }
        sig_fixed = inspect.signature(compute_best_fixed_cycle)
        if "start_date" in sig_fixed.parameters:
            fixed_params["start_date"] = history_start
        if "end_date" in sig_fixed.parameters:
            fixed_params["end_date"] = history_end

        fixed_cycle = compute_best_fixed_cycle(**fixed_params)
        fixed_history: pd.DataFrame = fixed_cycle.get("daily_history", pd.DataFrame())
        fixed_summaries = summarize_profit_windows(fixed_history) if not fixed_history.empty else []

        if fixed_history.empty:
            st.info("No historical PZU data available at the configured path.")
        else:
            start_dt = fixed_history['date'].iloc[0]
            end_dt = fixed_history['date'].iloc[-1]
            st.caption(
                f"History coverage: {start_dt.strftime('%Y-%m-%d')} → {end_dt.strftime('%Y-%m-%d')}"
                f" | {len(fixed_history)} full days"
            )

            price_series = load_pzu_price_series(
                provider.pzu_csv,
                start_date=history_start,
                end_date=history_end,
            )
            if not price_series.empty:
                st.line_chart(
                    price_series.set_index("date")["avg_price_eur_mwh"],
                    height=260,
                )
                st.caption("Average PZU price per day over the selected window.")

            st.subheader("Best Fixed 2h Cycle (historical across all days)")
            st.caption(
                "This summary finds the single 2-hour charge and discharge block that performs best over the selected window using the current capacity and power."
            )
            
            buy_hour = fixed_cycle.get("buy_start_hour")
            sell_hour = fixed_cycle.get("sell_start_hour")
            if buy_hour is None or sell_hour is None:
                st.info("Not enough consistent history to determine a fixed 2h schedule.")
            else:
                # ===== SCHEDULE OVERVIEW CONTAINER =====
                with st.container():
                    st.markdown("#### 📅 Optimal Schedule")
                    buy_end = min(int(buy_hour) + 2, 24)
                    sell_end = min(int(sell_hour) + 2, 24)
                    
                    schedule_cols = st.columns(4)
                    with schedule_cols[0]:
                        st.metric(
                            "⚡ Charge Window",
                            f"{int(buy_hour):02d}:00–{buy_end:02d}:00",
                            help="Optimal 2-hour charging period"
                        )
                    with schedule_cols[1]:
                        st.metric(
                            "🔋 Discharge Window", 
                            f"{int(sell_hour):02d}:00–{sell_end:02d}:00",
                            help="Optimal 2-hour discharging period"
                        )
                    with schedule_cols[2]:
                        st.metric(
                            "📥 Charge Energy",
                            f"{fixed_cycle['charge_energy_mwh']:.1f} MWh",
                            help="Energy absorbed during charging"
                        )
                    with schedule_cols[3]:
                        st.metric(
                            "📤 Discharge Energy",
                            f"{fixed_cycle['discharge_energy_mwh']:.1f} MWh",
                            help="Energy delivered during discharging"
                        )

                # ===== FINANCIAL PERFORMANCE CONTAINER =====
                with st.container():
                    st.markdown("#### 💰 Financial Performance")
                    stats = enrich_cycle_stats(fixed_cycle.get("stats", {}), fixed_history)
                    price_decimals = max(currency_decimals, 2)

                    # Save metrics for session state
                    try:
                        daily_history_subset = fixed_history[
                            [
                                "date",
                                "daily_profit_eur",
                                "daily_revenue_eur",
                                "daily_cost_eur",
                            ]
                        ].copy()
                        history_start_val = _sanitize_session_value(history_start)
                        history_end_val = _sanitize_session_value(history_end)
                        stats_clean = _sanitize_session_value(stats)
                        daily_history_records = _sanitize_session_value(
                            daily_history_subset.to_dict(orient="records")
                        )
                        new_pzu_metrics = {
                            "history_start": history_start_val,
                            "history_end": history_end_val,
                            "stats": stats_clean,
                            "daily_history": daily_history_records,
                        }
                        safe_session_state_update("pzu_market_metrics", new_pzu_metrics)
                    except Exception:
                        pass

                    # Main financial metrics
                    fin_cols = st.columns(4)
                    with fin_cols[0]:
                        st.metric(
                            "💵 Total Profit",
                            format_currency(stats.get("total_profit_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                            help="Total profit over the analysis period"
                        )
                    with fin_cols[1]:
                        st.metric(
                            "📊 Average Daily",
                            format_currency(stats.get("average_profit_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                            help="Average daily profit"
                        )
                    with fin_cols[2]:
                        st.metric(
                            "📈 Total Revenue",
                            format_currency(stats.get("total_revenue_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                            help="Total revenue from energy sales"
                        )
                    with fin_cols[3]:
                        st.metric(
                            "📉 Total Cost",
                            format_currency(stats.get("total_cost_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                            help="Total cost of energy purchases"
                        )

                # ===== PRICE ANALYSIS CONTAINER =====
                with st.container():
                    st.markdown("#### 📊 Price Analysis")
                    price_cols = st.columns(3)
                    with price_cols[0]:
                        st.metric(
                            "💰 Avg Sell Price",
                            format_price_per_mwh(stats.get("avg_sell_price_eur_mwh"), decimals=price_decimals),
                            help="Average price received when selling energy"
                        )
                    with price_cols[1]:
                        st.metric(
                            "💸 Avg Buy Price",
                            format_price_per_mwh(stats.get("avg_buy_price_eur_mwh"), decimals=price_decimals),
                            help="Average price paid when buying energy"
                        )
                    with price_cols[2]:
                        spread_value = stats.get("spread_eur_mwh")
                        delta_color = "normal"
                        if spread_value and spread_value > 0:
                            delta_color = "normal"
                        st.metric(
                            "📈 Spread",
                            format_price_per_mwh(spread_value, decimals=price_decimals),
                            help="Profit margin per MWh (sell price - buy price)"
                        )

                # ===== TRADING STATISTICS CONTAINER =====
                with st.container():
                    st.markdown("#### 📈 Trading Statistics")
                    total_days = stats.get("total_days", 0)
                    pos_days = stats.get("positive_days", 0)
                    neg_days = stats.get("negative_days", 0)
                    win_rate = (pos_days / total_days * 100) if total_days > 0 else 0
                    
                    stats_cols = st.columns(4)
                    with stats_cols[0]:
                        st.metric(
                            "✅ Winning Days",
                            f"{pos_days}/{total_days}",
                            delta=f"{win_rate:.1f}%",
                            help="Days with positive profit"
                        )
                    with stats_cols[1]:
                        st.metric(
                            "❌ Losing Days",
                            f"{neg_days}/{total_days}",
                            delta=f"{(100-win_rate):.1f}%",
                            delta_color="inverse",
                            help="Days with negative profit"
                        )
                    with stats_cols[2]:
                        st.metric(
                            "💔 Total Losses",
                            format_currency(stats.get("total_loss_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                            help="Total losses on losing days"
                        )
                    with stats_cols[3]:
                        efficiency_note = f"{eta_rt:.0%}"
                        st.metric(
                            "⚡ Round-trip Eff.",
                            efficiency_note,
                            help="Battery round-trip efficiency used in calculations"
                        )

                    st.caption(
                        f"💡 Discharge energy = charge energy × efficiency → {fixed_cycle['charge_energy_mwh']:.1f} MWh × {eta_rt:.2f} = {fixed_cycle['discharge_energy_mwh']:.1f} MWh"
                    )

                # ===== PROFITABILITY WINDOWS CONTAINER =====
                if fixed_summaries:
                    with st.container():
                        st.markdown("#### 📅 Profitability Windows")
                        st.caption("Historical performance analysis across different time horizons")
                        
                        fixed_table = []
                        for summary in fixed_summaries:
                            fixed_table.append(
                                {
                                    "Period": summary["period_label"],
                                    "Days": summary["recent_days"],
                                    "Coverage %": summary["coverage_ratio"] * 100 if summary["coverage_ratio"] is not None else None,
                                    "Recent total €": summary["recent_total_eur"],
                                    "Avg daily €": summary["recent_avg_eur"],
                                    "Recent revenue €": summary.get("recent_revenue_eur"),
                                    "Recent cost €": summary.get("recent_cost_eur"),
                                    "Loss €": summary.get("recent_loss_eur"),
                                    "Projected total €": summary.get("projected_total_eur"),
                                    "Projected revenue €": summary.get("projected_revenue_eur"),
                                    "Projected cost €": summary.get("projected_cost_eur"),
                                    "Projected loss €": summary.get("projected_loss_eur"),
                                    "Spread €/MWh": summary.get("recent_spread_eur_mwh"),
                                    "Win rate %": summary["recent_success_rate"],
                                }
                            )

                        fixed_df = pd.DataFrame(fixed_table)
                        preferred_order = [
                            "Period",
                            "Days",
                            "Coverage %",
                            "Recent total €",
                            "Recent revenue €",
                            "Recent cost €",
                            "Loss €",
                            "Projected total €",
                            "Projected revenue €",
                            "Projected cost €",
                            "Projected loss €",
                            "Avg daily €",
                            "Spread €/MWh",
                            "Win rate %",
                        ]
                        existing_order = [c for c in preferred_order if c in fixed_df.columns]
                        remaining_cols = [c for c in fixed_df.columns if c not in existing_order]
                        fixed_df = fixed_df[existing_order + remaining_cols]
                        
                        if show_raw_tables:
                            st.dataframe(fixed_df, width='stretch')
                        else:
                            display_fixed = fixed_df.copy()
                            display_fixed["Coverage %"] = display_fixed["Coverage %"].apply(
                                lambda v: format_percent(v, decimals=percent_decimals) if v is not None else "—"
                            )
                            display_fixed["Recent total €"] = display_fixed["Recent total €"].apply(
                                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                            )
                            display_fixed["Avg daily €"] = display_fixed["Avg daily €"].apply(
                                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                            )
                            display_fixed["Recent revenue €"] = display_fixed["Recent revenue €"].apply(
                                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                            )
                            display_fixed["Recent cost €"] = display_fixed["Recent cost €"].apply(
                                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                            )
                            display_fixed["Loss €"] = display_fixed["Loss €"].apply(
                                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                            )
                            display_fixed["Projected total €"] = display_fixed["Projected total €"].apply(
                                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                            )
                            display_fixed["Projected revenue €"] = display_fixed["Projected revenue €"].apply(
                                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                            )
                            display_fixed["Projected cost €"] = display_fixed["Projected cost €"].apply(
                                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                            )
                            display_fixed["Projected loss €"] = display_fixed["Projected loss €"].apply(
                                lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                            )
                            spread_decimals = max(currency_decimals, 2)
                            display_fixed["Spread €/MWh"] = display_fixed["Spread €/MWh"].apply(
                                lambda v: format_price_per_mwh(v, decimals=spread_decimals) if v is not None else "—"
                            )
                            display_fixed["Win rate %"] = display_fixed["Win rate %"].apply(
                                lambda v: format_percent(v, decimals=percent_decimals) if v is not None else "—"
                            )
                            st.dataframe(display_fixed, width='stretch')

                # ===== HISTORICAL CASH FLOW CONTAINER =====
                cash_flow_historical = build_cash_flow_summary(fixed_history)
                if not cash_flow_historical.empty:
                    with st.container():
                        st.markdown("#### 💸 3-Year Cash Flow (historical)")
                        st.caption("Annual cash flow breakdown based on historical performance")
                        
                        hist_display = cash_flow_historical.copy()
                        hist_currency_cols = ["Turnover €", "Cost €", "Profit €", "Loss €"]
                        for col in hist_currency_cols:
                            if col in hist_display.columns:
                                hist_display[col] = hist_display[col].apply(
                                    lambda v, d=currency_decimals: format_currency(
                                        v, decimals=d, thousands=thousands_sep
                                    )
                                    if v is not None
                                    else "—"
                                )
                        hist_price_cols = ["Avg buy €/MWh", "Avg sell €/MWh", "Spread €/MWh"]
                        hist_price_decimals = max(currency_decimals, 2)
                        for col in hist_price_cols:
                            if col in hist_display.columns:
                                hist_display[col] = hist_display[col].apply(
                                    lambda v, d=hist_price_decimals: format_price_per_mwh(v, decimals=d)
                                    if v is not None
                                    else "—"
                                )
                        st.dataframe(hist_display, width='stretch')

        st.subheader("Custom Fixed 2h Scenario")
        st.caption("Adjust capacity, power and date range to evaluate a separate fixed 2‑hour schedule without altering the main view above.")

        scenario_cols = st.columns(2)
        scenario_capacity = scenario_cols[0].number_input(
            "Scenario capacity (MWh)",
            min_value=1.0,
            value=float(capacity_mwh),
            step=1.0,
            key="scenario_capacity",
        )
        scenario_power = scenario_cols[1].number_input(
            "Scenario power (MW)",
            min_value=0.1,
            value=float(power_mw),
            step=0.5,
            key="scenario_power",
        )

        scenario_date_cols = st.columns(2)
        scenario_min = (earliest_available_ts or history_start or pd.Timestamp(date.today())).to_pydatetime().date()
        scenario_max = (latest_available_ts or history_end or pd.Timestamp(date.today())).to_pydatetime().date()
        scenario_start_input = scenario_date_cols[0].date_input(
            "Scenario start",
            value=(history_start or earliest_available_ts or pd.Timestamp(date.today())).to_pydatetime().date(),
            min_value=scenario_min,
            max_value=scenario_max,
            key="scenario_start",
        )
        scenario_end_input = scenario_date_cols[1].date_input(
            "Scenario end",
            value=(history_end or latest_available_ts or pd.Timestamp(date.today())).to_pydatetime().date(),
            min_value=scenario_start_input,
            max_value=scenario_max,
            key="scenario_end",
        )

        scenario_start_ts = pd.Timestamp(scenario_start_input)
        scenario_end_ts = pd.Timestamp(scenario_end_input)
        if scenario_start_ts > scenario_end_ts:
            scenario_start_ts, scenario_end_ts = scenario_end_ts, scenario_start_ts

        scenario_cycle = compute_best_fixed_cycle(
            provider.pzu_csv,
            capacity_mwh=scenario_capacity,
            power_mw=scenario_power,
            round_trip_efficiency=eta_rt,
            start_date=scenario_start_ts,
            end_date=scenario_end_ts,
        )

        scenario_history = scenario_cycle.get("daily_history", pd.DataFrame())
        if scenario_history.empty:
            st.info("No scenario results available for the selected period.")
        else:
            scenario_prices = load_pzu_price_series(
                provider.pzu_csv,
                start_date=scenario_start_ts,
                end_date=scenario_end_ts,
            )
            if not scenario_prices.empty:
                st.line_chart(
                    scenario_prices.set_index("date")["avg_price_eur_mwh"],
                    height=240,
                )
                st.caption("Average PZU price per day for the scenario window.")

            scenario_buy = scenario_cycle.get("buy_start_hour")
            scenario_sell = scenario_cycle.get("sell_start_hour")
            if scenario_buy is not None and scenario_sell is not None:
                scenario_buy_end = min(int(scenario_buy) + 2, 24)
                scenario_sell_end = min(int(scenario_sell) + 2, 24)
                sc_cols = st.columns(4)
                sc_cols[0].metric("Charge window", f"{int(scenario_buy):02d}:00–{scenario_buy_end:02d}:00")
                sc_cols[1].metric("Discharge window", f"{int(scenario_sell):02d}:00–{scenario_sell_end:02d}:00")
                sc_cols[2].metric("Charge energy", f"{scenario_cycle['charge_energy_mwh']:.1f} MWh")
                sc_cols[3].metric("Discharge energy", f"{scenario_cycle['discharge_energy_mwh']:.1f} MWh")

            scenario_stats = enrich_cycle_stats(scenario_cycle.get("stats", {}), scenario_history)
            sc_price_decimals = max(currency_decimals, 2)

            sc_stat_cols = st.columns(4)
            sc_stat_cols[0].metric(
                "Total profit",
                format_currency(scenario_stats.get("total_profit_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
            )
            sc_stat_cols[1].metric(
                "Average day",
                format_currency(scenario_stats.get("average_profit_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
            )
            sc_stat_cols[2].metric(
                "Total revenue",
                format_currency(scenario_stats.get("total_revenue_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
            )
            sc_stat_cols[3].metric(
                "Total cost",
                format_currency(scenario_stats.get("total_cost_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
            )

            sc_price_cols = st.columns(3)
            sc_price_cols[0].metric(
                "Avg sell price",
                format_price_per_mwh(scenario_stats.get("avg_sell_price_eur_mwh"), decimals=sc_price_decimals),
            )
            sc_price_cols[1].metric(
                "Avg buy price",
                format_price_per_mwh(scenario_stats.get("avg_buy_price_eur_mwh"), decimals=sc_price_decimals),
            )
            sc_price_cols[2].metric(
                "Spread €/MWh",
                format_price_per_mwh(scenario_stats.get("spread_eur_mwh"), decimals=sc_price_decimals),
            )

            sc_total_days = scenario_stats.get("total_days", 0)
            sc_positive_days = scenario_stats.get("positive_days", 0)
            sc_negative_days = scenario_stats.get("negative_days", 0)
            sc_day_cols = st.columns(3)
            sc_day_cols[0].metric("Winning days", f"{sc_positive_days}/{sc_total_days}")
            sc_day_cols[1].metric("Losing days", f"{sc_negative_days}/{sc_total_days}")
            sc_day_cols[2].metric(
                "Loss on losing days",
                format_currency(scenario_stats.get("total_loss_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
            )

            scenario_summary = summarize_profit_windows(scenario_history)
            if scenario_summary:
                sc_table = []
                for summary in scenario_summary:
                    sc_table.append(
                        {
                            "Period": summary["period_label"],
                            "Days": summary["recent_days"],
                            "Coverage %": summary["coverage_ratio"] * 100 if summary["coverage_ratio"] is not None else None,
                            "Recent total €": summary["recent_total_eur"],
                            "Avg daily €": summary["recent_avg_eur"],
                            "Recent revenue €": summary.get("recent_revenue_eur"),
                            "Recent cost €": summary.get("recent_cost_eur"),
                            "Loss €": summary.get("recent_loss_eur"),
                            "Projected total €": summary.get("projected_total_eur"),
                            "Projected revenue €": summary.get("projected_revenue_eur"),
                            "Projected cost €": summary.get("projected_cost_eur"),
                            "Projected loss €": summary.get("projected_loss_eur"),
                            "Spread €/MWh": summary.get("recent_spread_eur_mwh"),
                            "Win rate %": summary["recent_success_rate"],
                        }
                    )

                sc_df = pd.DataFrame(sc_table)
                preferred_order = [
                    "Period",
                    "Days",
                    "Coverage %",
                    "Recent total €",
                    "Recent revenue €",
                    "Recent cost €",
                    "Loss €",
                    "Projected total €",
                    "Projected revenue €",
                    "Projected cost €",
                    "Projected loss €",
                    "Avg daily €",
                    "Spread €/MWh",
                    "Win rate %",
                ]
                existing_order = [c for c in preferred_order if c in sc_df.columns]
                remaining_cols = [c for c in sc_df.columns if c not in existing_order]
                sc_df = sc_df[existing_order + remaining_cols]
                if show_raw_tables:
                    st.dataframe(sc_df, width='stretch')
                else:
                    sc_display = sc_df.copy()
                    sc_display["Coverage %"] = sc_display["Coverage %"].apply(
                        lambda v: format_percent(v, decimals=percent_decimals) if v is not None else "—"
                    )
                    sc_display["Recent total €"] = sc_display["Recent total €"].apply(
                        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                    )
                    sc_display["Avg daily €"] = sc_display["Avg daily €"].apply(
                        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                    )
                    sc_display["Recent revenue €"] = sc_display["Recent revenue €"].apply(
                        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                    )
                    sc_display["Recent cost €"] = sc_display["Recent cost €"].apply(
                        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                    )
                    sc_display["Loss €"] = sc_display["Loss €"].apply(
                        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                    )
                    sc_display["Projected total €"] = sc_display["Projected total €"].apply(
                        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                    )
                    sc_display["Projected revenue €"] = sc_display["Projected revenue €"].apply(
                        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                    )
                    sc_display["Projected cost €"] = sc_display["Projected cost €"].apply(
                        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                    )
                    sc_display["Projected loss €"] = sc_display["Projected loss €"].apply(
                        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep) if v is not None else "—"
                    )
                    spread_decimals = max(currency_decimals, 2)
                    sc_display["Spread €/MWh"] = sc_display["Spread €/MWh"].apply(
                        lambda v: format_price_per_mwh(v, decimals=spread_decimals) if v is not None else "—"
                    )
                    sc_display["Win rate %"] = sc_display["Win rate %"].apply(
                        lambda v: format_percent(v, decimals=percent_decimals) if v is not None else "—"
                    )
                    st.dataframe(sc_display, width='stretch')

            three_year_summary = next(
                (row for row in scenario_summary if row.get("period_label") == "3 years"),
                None,
            )
            if three_year_summary:
                projected_profit = three_year_summary.get("projected_total_eur")
                projected_revenue = three_year_summary.get("projected_revenue_eur")
                projected_cost = three_year_summary.get("projected_cost_eur")
                projected_loss = three_year_summary.get("projected_loss_eur")
                projected_spread = three_year_summary.get("projected_spread_eur_mwh")

                if any(
                    value is not None
                    for value in (
                        projected_profit,
                        projected_revenue,
                        projected_cost,
                        projected_loss,
                        projected_spread,
                    )
                ):
                    st.subheader("Simulated 3-Year Totals (scenario)")
                    sim_cols = st.columns(5)
                    sim_cols[0].metric(
                        "Profit (3y sim)",
                        format_currency(
                            projected_profit or three_year_summary.get("recent_total_eur", 0.0),
                            decimals=currency_decimals,
                            thousands=thousands_sep,
                        ),
                    )
                    sim_cols[1].metric(
                        "Revenue (3y sim)",
                        format_currency(
                            projected_revenue or three_year_summary.get("recent_revenue_eur", 0.0),
                            decimals=currency_decimals,
                            thousands=thousands_sep,
                        ),
                    )
                    sim_cols[2].metric(
                        "Cost (3y sim)",
                        format_currency(
                            projected_cost or three_year_summary.get("recent_cost_eur", 0.0),
                            decimals=currency_decimals,
                            thousands=thousands_sep,
                        ),
                    )
                    sim_cols[3].metric(
                        "Loss (3y sim)",
                        format_currency(
                            projected_loss or three_year_summary.get("recent_loss_eur", 0.0),
                            decimals=currency_decimals,
                            thousands=thousands_sep,
                        ),
                    )
                    sim_cols[4].metric(
                        "Spread €/MWh (3y sim)",
                        format_price_per_mwh(
                            projected_spread
                            or three_year_summary.get("recent_spread_eur_mwh"),
                            decimals=max(currency_decimals, 2),
                        ),
                    )

                    # Chart projections based on proportional scaling of the selected window
                    scenario_days = max(int(three_year_summary.get("recent_days", 0)), 1)
                    expected_days = max(int(three_year_summary.get("expected_days", scenario_days)), scenario_days)
                    scaling_factor = expected_days / scenario_days if scenario_days else 1.0

                    recent_history = three_year_summary.get("recent_total_eur", 0.0)
                    projected_history = projected_profit or recent_history * scaling_factor

                    comparison_table = pd.DataFrame(
                        {
                            "Phase": ["Actual window", "Projected 3y"],
                            "Profit €": [
                                format_currency(recent_history, decimals=currency_decimals, thousands=thousands_sep),
                                format_currency(projected_history, decimals=currency_decimals, thousands=thousands_sep),
                            ],
                        }
                    )
                    st.table(comparison_table)

            cash_flow_scenario = build_cash_flow_summary(scenario_history, freq="M")
            if not cash_flow_scenario.empty:
                st.subheader("36-Month Cash Flow (scenario)")
                scen_display = cash_flow_scenario.copy()
                period_col = "Month" if "Month" in scen_display.columns else "Year"
                preferred_cols = [
                    period_col,
                    "Days",
                    "Turnover €",
                    "Cost €",
                    "Profit €",
                    "Loss €",
                    "Avg buy €/MWh",
                    "Avg sell €/MWh",
                    "Spread €/MWh",
                ]
                remaining_cols = [c for c in scen_display.columns if c not in preferred_cols]
                scen_display = scen_display[[c for c in preferred_cols if c in scen_display.columns] + remaining_cols]
                scen_currency_cols = ["Turnover €", "Cost €", "Profit €", "Loss €"]
                for col in scen_currency_cols:
                    if col in scen_display.columns:
                        scen_display[col] = scen_display[col].apply(
                            lambda v, d=currency_decimals: format_currency(
                                v, decimals=d, thousands=thousands_sep
                            )
                            if v is not None
                            else "—"
                        )
                scen_price_cols = ["Avg buy €/MWh", "Avg sell €/MWh", "Spread €/MWh"]
                scen_price_decimals = max(currency_decimals, 2)
                for col in scen_price_cols:
                    if col in scen_display.columns:
                        scen_display[col] = scen_display[col].apply(
                            lambda v, d=scen_price_decimals: format_price_per_mwh(v, decimals=d)
                            if v is not None
                            else "—"
                        )
                st.dataframe(scen_display, width='stretch')

        # Year-by-year best fixed hours summary (PZU only)
        best_years_df = compute_best_hours_by_year(
            provider.pzu_csv,
            round_trip_efficiency=eta_rt,
            capacity_mwh=capacity_mwh,
            power_mw=power_mw,
            years=[2022, 2023, 2024, 2025],
        )

        if not best_years_df.empty:
            st.subheader("📊 Best Buy/Sell Hours Per Year (PZU)")
            st.caption(
                "Optimal 2-hour charge/discharge schedule computed separately for each calendar year,"
                " with annual profit at those hours."
            )

            display_years = []
            for _, row in best_years_df.iterrows():
                buy = int(row["buy_hour"])
                sell = int(row["sell_hour"])
                buy_end = min(buy + 2, 24)
                sell_end = min(sell + 2, 24)
                display_years.append(
                    {
                        "Year": str(int(row["year"])),
                        "Charge window": f"{buy:02d}:00–{buy_end:02d}:00",
                        "Discharge window": f"{sell:02d}:00–{sell_end:02d}:00",
                        "Profit €": format_currency(row.get("profit_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                        "Revenue €": format_currency(row.get("revenue_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                        "Cost €": format_currency(row.get("cost_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                        "Avg buy €/MWh": format_price_per_mwh(row.get("avg_buy_price_eur_mwh"), decimals=max(currency_decimals, 2)),
                        "Avg sell €/MWh": format_price_per_mwh(row.get("avg_sell_price_eur_mwh"), decimals=max(currency_decimals, 2)),
                        "Spread €/MWh": format_price_per_mwh(row.get("spread_eur_mwh"), decimals=max(currency_decimals, 2)),
                    }
                )

            year_df = pd.DataFrame(display_years)
            preferred_order = [
                "Year",
                "Charge window",
                "Discharge window",
                "Profit €",
                "Revenue €",
                "Cost €",
                "Avg buy €/MWh",
                "Avg sell €/MWh",
                "Spread €/MWh",
            ]
            year_df = year_df[[col for col in preferred_order if col in year_df.columns]]
            st.dataframe(year_df, width='stretch')

    if view == "ROI & Trends":
        if daily_history.empty:
            st.info("No historical PZU data available.")
        else:
            st.subheader("📅 Monthly Profitability Trends")
            monthly_trends = analyze_historical_monthly_trends_only(provider.pzu_csv, capacity_mwh, eta_rt, start_year=2023)
            if 'error' in monthly_trends:
                st.error(monthly_trends['error'])
                if 'suggestion' in monthly_trends:
                    st.info(monthly_trends['suggestion'])
            elif 'info' in monthly_trends:
                st.info(monthly_trends['info'])
                if 'reason' in monthly_trends:
                    st.caption(monthly_trends['reason'])
                if 'suggestion' in monthly_trends:
                    st.caption(f"💡 {monthly_trends['suggestion']}")
            else:
                st.success(f"✅ {monthly_trends['analysis_type']} - {monthly_trends['total_months']} months analyzed")
                if 'monthly_data' in monthly_trends and len(monthly_trends['monthly_data']) > 0:
                    monthly_data = monthly_trends['monthly_data']
                    months = [m['month'] for m in monthly_data]
                    profits = [m['total_monthly_profit'] for m in monthly_data]
                    with safe_pyplot_figure(figsize=(12, 6)) as (fig_monthly, ax_monthly):
                        chart_colors = get_chart_colors()
                        ax_monthly.bar(range(len(months)), profits, alpha=0.7, color=chart_colors['darkgreen'])
                        ax_monthly.set_xlabel('Month'); ax_monthly.set_ylabel('Monthly Profit (EUR)')
                        ax_monthly.set_title(f"Historical Monthly Profitability ({monthly_trends.get('data_period', 'historical range')})")
                        ax_monthly.set_xticks(range(len(months))); ax_monthly.set_xticklabels(months, rotation=45)
                        ax_monthly.grid(True, alpha=0.3); ax_monthly.axhline(y=0, color=chart_colors['red'], linestyle='-', alpha=0.5)
                        plt.tight_layout()
                        st.pyplot(fig_monthly, clear_figure=True)

            st.subheader("💡 Historical ROI (from 2023)")
            roi_window = st.radio("ROI window (months)", options=[12, 24], index=0, horizontal=True)
            roi12 = calculate_historical_roi_metrics(provider.pzu_csv, capacity_mwh, investment_eur=6_500_000, start_year=2023, window_months=12, round_trip_efficiency=eta_rt)
            roi24 = calculate_historical_roi_metrics(provider.pzu_csv, capacity_mwh, investment_eur=6_500_000, start_year=2023, window_months=24, round_trip_efficiency=eta_rt)
            chosen_roi = roi12 if roi_window == 12 else roi24
            if 'error' in chosen_roi:
                st.error(chosen_roi['error'])
            elif 'info' in chosen_roi:
                st.info(chosen_roi['info'])
                if 'reason' in chosen_roi:
                    st.caption(chosen_roi['reason'])
                if 'suggestion' in chosen_roi:
                    st.caption(f"💡 {chosen_roi['suggestion']}")
            else:
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("🎯 Annual ROI", format_percent(chosen_roi['roi_annual_percent'], decimals=percent_decimals))
                r2.metric("💰 Annualized Profit", format_currency(chosen_roi['annualized_profit_eur'], decimals=currency_decimals, thousands=thousands_sep))
                r3.metric("⏳ Payback Period", f"{chosen_roi['payback_years']:.1f} years" if chosen_roi['payback_years'] != float('inf') else "∞")
                r4.metric("🏁 Window", f"{chosen_roi['window_months']} mo")
                st.caption(f"Investment assumed: €{chosen_roi['investment_eur']:,.0f} | Data period: {chosen_roi.get('data_period','N/A')}")

            st.subheader("⏱️ 3‑Year Best‑Hour Arbitrage Estimate (OPCOM PZU)")
            best3 = analyze_pzu_best_hours_min_years(provider.pzu_csv, min_years=3, round_trip_efficiency=eta_rt, capacity_mwh=capacity_mwh, investment_eur=6_500_000)
            if 'error' in best3:
                st.warning(best3['error'])
                if 'suggestion' in best3:
                    st.caption(best3['suggestion'])
            else:
                b1, b2, b3, b4, b5 = st.columns(5)
                b1.metric("Best BUY hour", f"{best3['buy_hour']:02d}:00", help="Hour-of-day with lowest 3-year average price")
                b2.metric("Best SELL hour", f"{best3['sell_hour']:02d}:00", help="Hour-of-day with highest 3-year average price")
                b3.metric("Net spread", format_currency(best3['net_spread_eur_mwh'], decimals=2) + "/MWh")
                b4.metric("Daily profit", format_currency(best3['daily_profit_eur'], decimals=0))
                b5.metric("Annual profit", format_currency(best3['annual_profit_eur'], decimals=0))
                rb1, rb2 = st.columns(2)
                rb1.metric("Annual ROI", format_percent(best3['roi_annual_percent'], decimals=1))
                rb2.metric("Payback", f"{best3['payback_years']:.1f} years" if best3['payback_years'] != float('inf') else "∞")
                st.caption(f"Period: {best3['data_period']} ({best3['period_months']} months)")

            st.subheader("🕒 Multi‑hour Buffer Strategy (3y averages)")
            colb1, colb2, colb3 = st.columns(3)
            with colb1:
                buf_buy = st.slider("Buy hours (per cycle)", 1, 6, 2)
            with colb2:
                buf_sell = st.slider("Sell hours (per cycle)", 1, 6, 2)
            with colb3:
                cycles_day = st.slider("Cycles per day", 1, 3, int(cfg.get('strategy', {}).get('pzu', {}).get('daily_cycles_target', 1)))

            mh = plan_multi_hour_strategy_from_history(
                provider.pzu_csv,
                min_years=3,
                round_trip_efficiency=eta_rt,
                capacity_mwh=capacity_mwh,
                power_mw=power_mw,
                buy_hours_buffer=int(buf_buy),
                sell_hours_buffer=int(buf_sell),
                cycles_per_day=int(cycles_day),
                investment_eur=6_500_000,
            )
            if isinstance(mh, tuple) and 'error' in mh[0]:
                st.warning(mh[0]['error'])
            elif 'error' in mh:
                st.warning(mh['error'])
            else:
                mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                mcol1.metric("Profit/cycle", format_currency(mh['profit_per_cycle_eur'], decimals=0))
                mcol2.metric("Cycles/day used", f"{mh['cycles_used_per_day']}")
                mcol3.metric("Daily profit", format_currency(mh['daily_profit_eur'], decimals=0))
                mcol4.metric("Annual profit", format_currency(mh['annual_profit_eur'], decimals=0))
                mcol5, mcol6 = st.columns(2)
                mcol5.metric("Annual ROI", format_percent(mh['roi_annual_percent'], decimals=1))
                mcol6.metric("Payback", f"{mh['payback_years']:.1f} years" if mh['payback_years'] != float('inf') else "∞")
                st.caption(f"Buy hours: {sorted(mh['buy_hours'])} | Sell hours: {sorted(mh['sell_hours'])}")

    if view == "Romanian BM":
        st.subheader("🇷🇴 Romanian Balancing Market Analysis")
        if bm_series is None or len(bm_series) == 0:
            st.info("No balancing market data for the selected date.")
        else:
            # Romanian balancing market analysis
            romanian_bm_analysis = analyze_romanian_balancing_market(bm_series, capacity_mwh)
            
            if 'error' in romanian_bm_analysis:
                st.error(romanian_bm_analysis['error'])
            else:
                # Market Overview
                st.success(f"📊 {romanian_bm_analysis['market_name']}")
                st.caption(f"Operator: {romanian_bm_analysis['operator']} | Platform: {romanian_bm_analysis['trading_platform']}")
                
                # Key Market Characteristics
                st.subheader("⚡ Market Characteristics")
                char_col1, char_col2 = st.columns(2)
                char_col1.metric("Time Resolution", romanian_bm_analysis['time_resolution'])
                char_col2.metric("Market Type", romanian_bm_analysis['market_type'])
                char_col1.metric("Data Points", romanian_bm_analysis['data_points'])
                min_bid = romanian_bm_analysis.get('minimum_bid_size_mw')
                char_col2.metric("Min Bid Size", f"{min_bid} MW" if min_bid is not None else "N/A")
                
                # Price Analysis
                st.subheader("💰 Price Analysis")
                price_col1, price_col2, price_col3 = st.columns(3)
                price_col1.metric("Avg Price (EUR)", f"€{romanian_bm_analysis['avg_imbalance_price_eur_mwh']:.2f}/MWh")
                price_col2.metric("Price Range (EUR)", f"€{romanian_bm_analysis['price_range_eur_mwh']:.2f}/MWh")
                price_col3.metric("Volatility", f"{romanian_bm_analysis['price_volatility']:.2f}")
                
                # System Balance Analysis
                if 'system_imbalance_analysis' in romanian_bm_analysis:
                    st.subheader("⚖️ System Balance Analysis")
                    balance = romanian_bm_analysis['system_imbalance_analysis']
                    bal_col1, bal_col2, bal_col3 = st.columns(3)
                    bal_col1.metric("System Deficit", f"{balance['deficit_percentage']:.1f}%", help="Periods with positive prices")
                    bal_col2.metric("System Surplus", f"{balance['surplus_percentage']:.1f}%", help="Periods with negative prices")
                    bal_col3.metric("Balanced System", f"{balance['balanced_percentage']:.1f}%", help="Periods with zero prices")
                    
                    # Dominant condition indicator
                    if balance['dominant_imbalance'] == 'Generation Deficit':
                        st.warning(f"⚠️ System predominantly in **{balance['dominant_imbalance']}** (excess demand)")
                    else:
                        st.info(f"ℹ️ System predominantly in **{balance['dominant_imbalance']}** (excess generation)")
                
                # Frequency Regulation Services
                st.subheader("🔧 Frequency Regulation Services")
                response_times = romanian_bm_analysis['minimum_response_time_seconds']
                resp_col1, resp_col2, resp_col3 = st.columns(3)
                resp_col1.metric("FCR Response", f"{response_times}s", help="Frequency Containment Reserve")
                resp_col2.metric("aFRR Response", f"{response_times * 10}s", help="Automatic Frequency Restoration")
                resp_col3.metric("mFRR Response", f"{response_times * 30}s", help="Manual Frequency Restoration")
                
                # Revenue Model
                st.subheader("💼 Revenue Model for BESS")
                if romanian_bm_analysis['arbitrage_trading']:
                    st.success("✅ Suitable for arbitrage trading")
                else:
                    st.info("❌ Not suitable for arbitrage trading")
                
                if romanian_bm_analysis['frequency_regulation_services']:
                    st.success("✅ Suitable for frequency regulation services")
                    st.caption("Revenue streams: Availability payments + Activation payments")
                else:
                    st.warning("❌ Not suitable for frequency regulation")
                
                # Regulatory Framework
                st.subheader("📋 Regulatory Framework")
                reg_framework = romanian_bm_analysis['regulatory_framework']
                st.write(f"**Grid Operator:** {reg_framework['grid_operator']}")
                st.write(f"**Market Regulator:** {reg_framework['market_regulator']}")
                st.write(f"**EU Compliance:** {reg_framework['european_compliance']}")
                st.write(f"**Grid Code:** {reg_framework['grid_code']}")
                
                # Key Differences
                st.subheader("🔑 Key Differences from OPCOM")
                for difference in romanian_bm_analysis['key_differences_from_opcom']:
                    st.write(f"• {difference}")
                
                # BESS Participation Requirements
                st.subheader("📜 BESS Participation Requirements")
                for requirement in romanian_bm_analysis['bess_participation_requirements']:
                    st.write(f"• {requirement}")
                
                # Price chart (robust to empty/NaN; avoid Vega-Lite warnings by using Matplotlib)
                st.subheader("📈 Imbalance Prices")
                bm_df = pd.DataFrame({"slot": list(range(len(bm_series))), "price_ron_mwh": bm_series})
                bm_df = bm_df.replace([np.inf, -np.inf], np.nan).dropna()
                if bm_df.empty:
                    st.info("No balancing price points to plot for the selected date.")
                else:
                    with safe_pyplot_figure(figsize=(10, 3)) as (fig_bm, ax_bm):
                        chart_colors = get_chart_colors()
                        ax_bm.plot(bm_df["slot"], bm_df["price_ron_mwh"], color=chart_colors['primary'])
                        ax_bm.set_xlabel("Slot (15-min)")
                        ax_bm.set_ylabel("Price (RON/MWh)")
                        ax_bm.grid(True, alpha=0.3)
                        st.pyplot(fig_bm, clear_figure=True)
                
                # Traditional stats
                st.subheader("📊 Statistical Summary")
                st.json(bm_stats(bm_series))

        

if view == "FR Simulator":
    render_frequency_regulation_simulator(cfg)

if view == "Market Comparison":
    st.subheader("🔄 Market Comparison (latest runs)")
    render_historical_market_comparison(cfg, capacity_mwh, eta_rt)

if view == "FR Energy Hedging":
    st.subheader("⚖️ FR Energy Hedging Workbook")
    st.caption(
        "Reuse the latest FR Simulator run and our stored PZU data to estimate the cost of hedging"
        " activation energy on OPCOM while earning FR revenue on Transelectrica."
    )

    fr_metrics = st.session_state.get("fr_market_metrics")
    if not isinstance(fr_metrics, dict) or not fr_metrics.get("months"):
        st.info("Run the FR Simulator first to populate activation data.")
    else:
        fr_months_df = pd.DataFrame(fr_metrics["months"])
        if fr_months_df.empty or "month" not in fr_months_df.columns:
            st.info("No monthly activation data available; run the FR Simulator again.")
        else:
            try:
                fr_months_df["month_period"] = pd.PeriodIndex(fr_months_df["month"], freq="M")
            except Exception:
                fr_months_df["month_period"] = pd.to_datetime(fr_months_df["month"], errors="coerce").dt.to_period("M")
            fr_months_df = fr_months_df.dropna(subset=["month_period"]).sort_values("month_period")
            fr_months_df["month"] = fr_months_df["month_period"].astype(str)

            hedging_window = st.slider(
                "Hedging window (months)",
                min_value=1,
                max_value=len(fr_months_df),
                value=min(12, len(fr_months_df)),
                step=1,
            )

            fr_window = fr_months_df.tail(hedging_window).reset_index(drop=True)
            activation_mwh = float(fr_window.get("activation_energy_mwh", 0.0).sum())
            activation_revenue = float(fr_window.get("total_revenue_eur", 0.0).sum())
            activation_cost = float(fr_window.get("energy_cost_eur", 0.0).sum())

            pzu_start = fr_window["month_period"].min().to_timestamp() if not fr_window.empty else None
            pzu_end = fr_window["month_period"].max().to_timestamp() if not fr_window.empty else None

            pzu_monthly = compute_pzu_monthly_costs(
                provider.pzu_csv,
                start_date=pzu_start,
                end_date=pzu_end,
            )

            if pzu_monthly.empty:
                st.warning("No OPCOM PZU data available for the same window.")
                reference_price = 0.0
            else:
                st.subheader("OPCOM PZU Monthly Prices")
                pzu_display = pzu_monthly.rename(
                    columns={
                        "month": "Month",
                        "avg_price_eur_mwh": "Avg €/MWh",
                        "min_price_eur_mwh": "Min €/MWh",
                        "max_price_eur_mwh": "Max €/MWh",
                    }
                )
                for col in ["Avg €/MWh", "Min €/MWh", "Max €/MWh"]:
                    pzu_display[col] = pzu_display[col].apply(
                        lambda v: format_price_per_mwh(v, decimals=max(currency_decimals, 2))
                    )
                st.dataframe(pzu_display, width='stretch')

                reference_price = float(
                    pzu_monthly["avg_price_eur_mwh"].astype(float).mean()
                    if not pzu_monthly.empty
                    else 0.0
                )

            st.subheader("FR vs OPCOM Hedging Summary")
            summary_cols = st.columns(4)
            summary_cols[0].metric(
                "Activation energy (MWh)", f"{activation_mwh:.2f}", help="Energy delivered or absorbed in FR activations."
            )
            summary_cols[1].metric(
                "FR revenue (window)",
                format_currency(activation_revenue, decimals=currency_decimals, thousands=thousands_sep),
            )

            hedging_cost = activation_mwh * reference_price if reference_price else 0.0
            summary_cols[2].metric(
                "PZU hedging cost",
                format_currency(hedging_cost, decimals=currency_decimals, thousands=thousands_sep),
                help="Energy cost = activation MWh × average OPCOM price over the same months.",
            )

            summary_cols[3].metric(
                "Net margin",
                format_currency(activation_revenue - hedging_cost, decimals=currency_decimals, thousands=thousands_sep),
            )

            st.subheader("Detailed Hedging Breakdown")
            hedging_rows = []
            for _, row in fr_window.iterrows():
                month_label = str(row.get("month"))
                energy_mwh = float(row.get("activation_energy_mwh", 0.0))
                pzu_row = pzu_monthly[pzu_monthly["month"] == month_label]
                pzu_price = float(pzu_row["avg_price_eur_mwh"].iloc[0]) if not pzu_row.empty else reference_price
                row_cost = energy_mwh * pzu_price
                hedging_rows.append(
                    {
                        "Month": month_label,
                        "Activation MWh": f"{energy_mwh:.2f}",
                        "Hedge price €/MWh": format_price_per_mwh(pzu_price, decimals=max(currency_decimals, 2)),
                        "Hedging cost €": format_currency(row_cost, decimals=currency_decimals, thousands=thousands_sep),
                        "FR revenue €": format_currency(float(row.get("total_revenue_eur", 0.0)), decimals=currency_decimals, thousands=thousands_sep),
                        "FR energy cost €": format_currency(float(row.get("energy_cost_eur", 0.0)), decimals=currency_decimals, thousands=thousands_sep),
                    }
                )

            if hedging_rows:
                hedging_df = pd.DataFrame(hedging_rows)
                st.dataframe(hedging_df, width='stretch')
            else:
                st.info("No FR activation rows available for the selected window.")

    # ---- Annual best-hours table (always shown at page end) ----
    best_years_df = compute_best_hours_by_year(
        provider.pzu_csv,
        round_trip_efficiency=eta_rt,
        capacity_mwh=capacity_mwh,
        power_mw=power_mw,
        years=[2022, 2023, 2024, 2025],
    )

    if not best_years_df.empty:
        st.subheader("📊 Best Buy/Sell Hours Per Year (PZU)")
        st.caption(
            "Optimal 2-hour charge/discharge schedule computed separately for each calendar year,"
            " with annual profit at those hours."
        )

        display_years = []
        for _, row in best_years_df.iterrows():
            buy = int(row["buy_hour"])
            sell = int(row["sell_hour"])
            buy_end = min(buy + 2, 24)
            sell_end = min(sell + 2, 24)
            display_years.append(
                {
                    "Year": str(int(row["year"])),
                    "Charge window": f"{buy:02d}:00–{buy_end:02d}:00",
                    "Discharge window": f"{sell:02d}:00–{sell_end:02d}:00",
                    "Profit €": format_currency(row.get("profit_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                    "Revenue €": format_currency(row.get("revenue_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                    "Cost €": format_currency(row.get("cost_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                    "Avg buy €/MWh": format_price_per_mwh(row.get("avg_buy_price_eur_mwh"), decimals=max(currency_decimals, 2)),
                    "Avg sell €/MWh": format_price_per_mwh(row.get("avg_sell_price_eur_mwh"), decimals=max(currency_decimals, 2)),
                    "Spread €/MWh": format_price_per_mwh(row.get("spread_eur_mwh"), decimals=max(currency_decimals, 2)),
                }
            )

        year_df = pd.DataFrame(display_years)
        preferred_order = [
            "Year",
            "Charge window",
            "Discharge window",
            "Profit €",
            "Revenue €",
            "Cost €",
            "Avg buy €/MWh",
            "Avg sell €/MWh",
            "Spread €/MWh",
        ]
        year_df = year_df[[col for col in preferred_order if col in year_df.columns]]
        st.dataframe(year_df, width='stretch')
