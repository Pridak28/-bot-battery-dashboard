from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False)
def analyze_monthly_trends(
    pzu_csv: str,
    capacity_mwh: float,
    round_trip_efficiency: float = 0.9,
) -> Dict:
    """Analyze monthly profitability trends from historical PZU data."""
    if not Path(pzu_csv).exists():
        return {"error": "Historical PZU data file not found"}

    try:
        df = pd.read_csv(pzu_csv)
        df["date"] = pd.to_datetime(df["date"])

        total_months = len(df["date"].dt.to_period("M").unique())
        if total_months < 12:
            return {
                "error": "Insufficient historical data. Found"
                f" {total_months} months, need minimum 12 months for trend analysis",
                "suggestion": "Use pzu_history_2y.csv or pzu_history_3y.csv for proper historical analysis",
            }

        df["month"] = df["date"].dt.to_period("M")
        monthly_results: List[Dict] = []
        for month, month_data in df.groupby("month"):
            month_profits: List[float] = []
            for _, day_data in month_data.groupby("date"):
                day_series = pd.Series(day_data.sort_values("hour")["price"].to_list())
                if len(day_series) >= 24:
                    min_price = day_series.min()
                    max_price = day_series.max()
                    net_spread = max_price * round_trip_efficiency - min_price
                    month_profits.append(net_spread * capacity_mwh)

            if month_profits:
                monthly_results.append(
                    {
                        "month": str(month),
                        "avg_daily_profit": float(np.mean(month_profits)),
                        "total_monthly_profit": float(sum(month_profits)),
                        "profitable_days": int(sum(p > 0 for p in month_profits)),
                        "total_days": int(len(month_profits)),
                        "success_rate": float(sum(p > 0 for p in month_profits) / len(month_profits) * 100),
                        "volatility": float(np.std(month_profits)),
                        "max_daily_profit": float(np.max(month_profits)),
                        "min_daily_profit": float(np.min(month_profits)),
                    }
                )

        monthly_results.sort(key=lambda x: x["month"])
        return {
            "monthly_data": monthly_results,
            "total_months": len(monthly_results),
            "data_period": f"{df['date'].min():%Y-%m-%d} to {df['date'].max():%Y-%m-%d}",
            "avg_monthly_profit": float(np.mean([m["total_monthly_profit"] for m in monthly_results]))
            if monthly_results
            else 0.0,
            "total_historical_profit": float(sum(m["total_monthly_profit"] for m in monthly_results)),
            "best_month": max(monthly_results, key=lambda x: x["total_monthly_profit"]) if monthly_results else None,
            "worst_month": min(monthly_results, key=lambda x: x["total_monthly_profit"]) if monthly_results else None,
            "overall_success_rate": float(np.mean([m["success_rate"] for m in monthly_results]))
            if monthly_results
            else 0.0,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": f"Error analyzing historical data: {exc}"}


@st.cache_data(show_spinner=False)
def analyze_historical_monthly_trends_only(
    pzu_csv: str,
    capacity_mwh: float,
    round_trip_efficiency: float = 0.9,
    start_year: int = 2023,
) -> Dict:
    """Return monthly profitability metrics from a given start year onward."""
    if not Path(pzu_csv).exists():
        return {"error": "Historical PZU data file not found"}

    try:
        df = pd.read_csv(pzu_csv)
        df["date"] = pd.to_datetime(df["date"])

        start_dt = pd.Timestamp(year=start_year, month=1, day=1)
        df = df[df["date"] >= start_dt]

        total_months = len(df["date"].dt.to_period("M").unique())
        if total_months < 12:
            return {
                "info": "Insufficient months from the selected start year",
                "reason": f"Found {total_months} months starting {start_year}-01-01; need at least 12.",
                "suggestion": "Switch to a longer history file (2y/3y) or adjust start year",
                "analysis_type": f"Historical Monthly Trends (from {start_year})",
                "total_months": total_months,
            }

        df["month"] = df["date"].dt.to_period("M")
        monthly_results: List[Dict] = []
        for month, month_data in df.groupby("month"):
            month_profits: List[float] = []
            for _, day_data in month_data.groupby("date"):
                day_series = pd.Series(day_data.sort_values("hour")["price"].to_list())
                if len(day_series) >= 24:
                    min_price = day_series.min()
                    max_price = day_series.max()
                    net_spread = max_price * round_trip_efficiency - min_price
                    month_profits.append(net_spread * capacity_mwh)
            if month_profits:
                monthly_results.append(
                    {
                        "month": str(month),
                        "avg_daily_profit": float(np.mean(month_profits)),
                        "total_monthly_profit": float(sum(month_profits)),
                        "profitable_days": int(sum(p > 0 for p in month_profits)),
                        "total_days": int(len(month_profits)),
                        "success_rate": float(sum(p > 0 for p in month_profits) / len(month_profits) * 100),
                        "volatility": float(np.std(month_profits)),
                        "max_daily_profit": float(np.max(month_profits)),
                        "min_daily_profit": float(np.min(month_profits)),
                    }
                )

        monthly_results.sort(key=lambda x: x["month"])
        return {
            "analysis_type": f"Historical Monthly Trends (from {start_year})",
            "monthly_data": monthly_results,
            "total_months": len(monthly_results),
            "data_period": f"{df['date'].min():%Y-%m-%d} to {df['date'].max():%Y-%m-%d}",
            "avg_monthly_profit": float(np.mean([m["total_monthly_profit"] for m in monthly_results]))
            if monthly_results
            else 0.0,
            "total_historical_profit": float(sum(m["total_monthly_profit"] for m in monthly_results)),
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": f"Error analyzing historical data: {exc}"}


@st.cache_data(show_spinner=False)
def analyze_pzu_best_hours(
    pzu_csv: str,
    start_year: int = 2023,
    window_months: int = 12,
) -> Dict:
    """Compute hour-of-day pivots to find best buy/sell windows over a recent window."""
    if not Path(pzu_csv).exists():
        return {"error": "PZU CSV not found"}
    try:
        df = pd.read_csv(pzu_csv)
        df["date"] = pd.to_datetime(df["date"])
        df["month"] = df["date"].dt.to_period("M")
        df = df[df["date"] >= pd.Timestamp(year=start_year, month=1, day=1)]

        months_sorted = sorted(df["month"].unique())
        if not months_sorted:
            return {"error": "No months found after filtering"}
        chosen = months_sorted[-window_months:]
        df = df[df["month"].isin(chosen)]

        full_days = df.groupby("date")["hour"].count()
        valid_dates = full_days[full_days >= 24].index
        df = df[df["date"].isin(valid_dates)]

        avg_by_hour = (
            df.groupby("hour")["price"].mean().reindex(range(24)).fillna(method="ffill").fillna(method="bfill")
        )
        best_buy = avg_by_hour.nsmallest(3)
        best_sell = avg_by_hour.nlargest(3)
        spread = float(best_sell.iloc[0] - best_buy.iloc[0])
        return {
            "window_months": len(chosen),
            "hours": list(range(24)),
            "avg_price_by_hour": [float(x) for x in avg_by_hour.values],
            "best_buy_hours": [{"hour": int(h), "avg_price": float(v)} for h, v in best_buy.items()],
            "best_sell_hours": [{"hour": int(h), "avg_price": float(v)} for h, v in best_sell.items()],
            "avg_spread_top_vs_bottom": spread,
            "start_month": str(chosen[0]) if chosen else None,
            "end_month": str(chosen[-1]) if chosen else None,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": f"Failed to analyze PZU best hours: {exc}"}


@st.cache_data(show_spinner=False)
def analyze_pzu_best_hours_min_years(
    pzu_csv: str,
    min_years: int = 3,
    round_trip_efficiency: float = 0.9,
    capacity_mwh: float = 0.0,
    investment_eur: float = 6_500_000,
) -> Dict:
    """Detect best buy/sell hours using minimum N years of history and estimate arbitrage profits."""
    if not Path(pzu_csv).exists():
        return {"error": "PZU CSV not found"}
    try:
        df = pd.read_csv(pzu_csv)
        required_cols = {"date", "hour", "price"}
        if not required_cols.issubset(df.columns):
            return {"error": "PZU CSV must contain columns: date,hour,price"}

        df["date"] = pd.to_datetime(df["date"])
        months = df["date"].dt.to_period("M").unique()
        total_months = len(months)
        if total_months < min_years * 12:
            return {
                "error": f"Insufficient history: found {total_months} months, need at least {min_years * 12} months",
                "suggestion": "Point pzu_forecast_csv to a >=3-year history (e.g., data/pzu_history_3y.csv)",
            }

        df = df.sort_values(["date", "hour"])
        hourly_avg = df.groupby("hour")["price"].mean().reindex(range(24))
        buy_hour = int(hourly_avg.idxmin())
        sell_hour = int(hourly_avg.idxmax())
        avg_buy = float(hourly_avg.min())
        avg_sell = float(hourly_avg.max())
        net_spread = avg_sell * float(round_trip_efficiency) - avg_buy
        daily_profit = max(0.0, net_spread) * float(capacity_mwh)
        annual_profit = daily_profit * 365.0
        roi_percent = (annual_profit / float(investment_eur) * 100.0) if investment_eur else 0.0
        payback_years = (float(investment_eur) / annual_profit) if annual_profit > 0 else float("inf")
        return {
            "analysis_type": f"{min_years}-Year Best-Hour Arbitrage Estimate",
            "period_months": total_months,
            "data_period": f"{df['date'].min().date()} to {df['date'].max().date()}",
            "buy_hour": buy_hour,
            "sell_hour": sell_hour,
            "avg_buy_eur_mwh": avg_buy,
            "avg_sell_eur_mwh": avg_sell,
            "net_spread_eur_mwh": net_spread,
            "daily_profit_eur": daily_profit,
            "annual_profit_eur": annual_profit,
            "roi_annual_percent": roi_percent,
            "payback_years": payback_years,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": f"Failed 3-year best-hour analysis: {exc}"}


@st.cache_data(show_spinner=False)
def estimate_pzu_profit_window(
    pzu_csv: str,
    capacity_mwh: float,
    round_trip_efficiency: float = 0.9,
    days: Optional[int] = None,
    months: Optional[int] = None,
) -> Dict:
    """Estimate profit over the last N days or months using daily min/max arbitrage."""
    if not Path(pzu_csv).exists():
        return {"error": "PZU CSV not found"}
    try:
        df = pd.read_csv(pzu_csv)
        required_cols = {"date", "hour", "price"}
        if not required_cols.issubset(df.columns):
            return {"error": "PZU CSV must contain columns: date,hour,price"}

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["date", "hour"])

        used_months = 0
        if months is not None:
            uniq_months = sorted(df["date"].dt.to_period("M").unique())
            if not uniq_months:
                return {"error": "No months in dataset"}
            chosen = uniq_months[-int(months) :]
            df = df[df["date"].dt.to_period("M").isin(chosen)]
            used_months = len(chosen)
        elif days is not None:
            uniq_days = sorted(df["date"].dt.date.unique())
            if not uniq_days:
                return {"error": "No days in dataset"}
            chosen_days = uniq_days[-int(days) :]
            df = df[df["date"].dt.date.isin(chosen_days)]

        eta = float(round_trip_efficiency)
        cap = float(capacity_mwh)
        daily_profits: List[float] = []
        for _, day_group in df.groupby(df["date"].dt.date):
            day_prices = day_group.sort_values("hour")["price"]
            if len(day_prices) < 4:
                continue
            min_p = float(day_prices.min())
            max_p = float(day_prices.max())
            net = max_p - (min_p / eta)
            daily_profits.append(max(0.0, net) * cap)

        used_days = len(daily_profits)
        total_profit = float(sum(daily_profits))
        avg_daily = (total_profit / used_days) if used_days > 0 else 0.0
        annualized = avg_daily * 365.0
        period = f"{df['date'].min().date()} to {df['date'].max().date()}"
        return {
            "used_days": used_days,
            "used_months": used_months,
            "total_profit_eur": total_profit,
            "avg_daily_profit_eur": avg_daily,
            "annualized_profit_eur": annualized,
            "data_period": period,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": f"Failed profit estimation: {exc}"}


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
    """Plan a simple daily arbitrage using hour-of-day averages over >= N years."""
    if not Path(pzu_csv).exists():
        return {"error": "PZU CSV not found"}
    try:
        df = pd.read_csv(pzu_csv)
        required_cols = {"date", "hour", "price"}
        if not required_cols.issubset(df.columns):
            return {"error": "PZU CSV must contain columns: date,hour,price"}

        df["date"] = pd.to_datetime(df["date"])
        months = df["date"].dt.to_period("M").unique()
        if len(months) < min_years * 12:
            return {"error": f"Insufficient history: need >= {min_years} years"}

        hourly_avg = df.groupby("hour")["price"].mean().reindex(range(24))
        k_b = max(1, int(buy_hours_buffer))
        k_s = max(1, int(sell_hours_buffer))
        buy_hours = list(hourly_avg.nsmallest(k_b).index.astype(int))
        sell_hours = list(hourly_avg.nlargest(k_s).index.astype(int))

        avg_buy = float(hourly_avg.iloc[buy_hours].mean()) if k_b > 0 else float("nan")
        avg_sell = float(hourly_avg.iloc[sell_hours].mean()) if k_s > 0 else float("nan")
        eta = float(round_trip_efficiency)
        cap = float(capacity_mwh)
        power = float(power_mw)

        max_discharge_by_power = power * k_s
        max_charge_by_power = power * k_b
        max_discharge_by_capacity = eta * min(cap, max_charge_by_power)
        energy_discharge = max(0.0, min(max_discharge_by_power, max_discharge_by_capacity))

        profit_per_cycle = (
            energy_discharge * avg_sell - (energy_discharge / eta) * avg_buy
            if energy_discharge > 0
            else 0.0
        )
        max_cycles_by_hours = max(1, 24 // (k_b + k_s))
        cycles_used = max(1, min(int(cycles_per_day), int(max_cycles_by_hours)))
        daily_profit = profit_per_cycle * cycles_used
        annual_profit = daily_profit * 365.0
        roi_percent = (annual_profit / float(investment_eur) * 100.0) if investment_eur and annual_profit > 0 else 0.0
        payback_years = (float(investment_eur) / annual_profit) if annual_profit > 0 else float("inf")
        return {
            "analysis_type": f"{min_years}y Hour-of-day buffer strategy",
            "buy_hours": buy_hours,
            "sell_hours": sell_hours,
            "avg_buy_eur_mwh": avg_buy,
            "avg_sell_eur_mwh": avg_sell,
            "energy_sold_mwh_per_cycle": energy_discharge,
            "profit_per_cycle_eur": profit_per_cycle,
            "cycles_used_per_day": cycles_used,
            "daily_profit_eur": daily_profit,
            "annual_profit_eur": annual_profit,
            "roi_annual_percent": roi_percent,
            "payback_years": payback_years,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": f"Failed multi-hour strategy planning: {exc}"}


__all__ = [
    "analyze_monthly_trends",
    "analyze_historical_monthly_trends_only",
    "analyze_pzu_best_hours",
    "analyze_pzu_best_hours_min_years",
    "estimate_pzu_profit_window",
    "plan_multi_hour_strategy_from_history",
]
