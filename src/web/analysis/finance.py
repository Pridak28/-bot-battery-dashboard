from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import streamlit as st

from .pzu import analyze_historical_monthly_trends_only


def enrich_cycle_stats(stats: Optional[dict], history: Optional[pd.DataFrame]) -> dict:
    """Fill in missing spread/cost metrics using available daily history."""
    stats = dict(stats or {})
    if history is None or history.empty:
        return stats

    total_cost = stats.get("total_cost_eur")
    if total_cost is None and "daily_cost_eur" in history:
        total_cost = float(history["daily_cost_eur"].sum())
        stats["total_cost_eur"] = total_cost

    total_revenue = stats.get("total_revenue_eur")
    if total_revenue is None and "daily_revenue_eur" in history:
        total_revenue = float(history["daily_revenue_eur"].sum())
        stats["total_revenue_eur"] = total_revenue

    if "total_loss_eur" not in stats and "daily_profit_eur" in history:
        loss = float(-history.loc[history["daily_profit_eur"] < 0, "daily_profit_eur"].sum())
        stats["total_loss_eur"] = abs(loss)

    charge_energy = float(history["charge_energy_mwh"].sum()) if "charge_energy_mwh" in history else None
    discharge_energy = float(history["discharge_energy_mwh"].sum()) if "discharge_energy_mwh" in history else None

    if stats.get("avg_buy_price_eur_mwh") is None and charge_energy and charge_energy > 0 and total_cost:
        stats["avg_buy_price_eur_mwh"] = float(total_cost / charge_energy)

    if stats.get("avg_sell_price_eur_mwh") is None and discharge_energy and discharge_energy > 0 and total_revenue:
        stats["avg_sell_price_eur_mwh"] = float(total_revenue / discharge_energy)

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
    """Aggregate cash-flow metrics over the most recent periods."""
    if history is None or history.empty:
        return pd.DataFrame(
            columns=[
                "Year" if freq.upper() == "Y" else "Month",
                "Days",
                "Turnover €",
                "Cost €",
                "Profit €",
                "Loss €",
                "Avg buy €/MWh",
                "Avg sell €/MWh",
                "Spread €/MWh",
            ]
        )

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
        df.loc[len(df)] = {
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

    label_key = "Year" if freq == "Y" else "Month"
    df[label_key] = df[label_key].astype(str)
    return df.reset_index(drop=True)


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
    """Compute ROI using historical monthly profits over a specified window with proper debt service."""
    trends = analyze_historical_monthly_trends_only(
        pzu_csv,
        capacity_mwh,
        round_trip_efficiency=round_trip_efficiency,
        start_year=start_year,
    )
    if "error" in trends or "info" in trends:
        return trends

    monthly = trends.get("monthly_data", [])
    if not monthly:
        return {"error": "No monthly data available for ROI calculation"}

    last_n = monthly[-window_months:]
    total_profit = float(sum(m["total_monthly_profit"] for m in last_n))
    months_count = len(last_n)
    if months_count == 0:
        return {"error": "Insufficient months for ROI window"}

    annualized_profit = total_profit * (12.0 / months_count)

    debt_amount = investment_eur * debt_ratio
    equity_amount = investment_eur * (1 - debt_ratio)

    if debt_amount > 0:
        monthly_rate = debt_interest_rate / 12
        num_payments = debt_term_years * 12
        monthly_payment = debt_amount * (
            monthly_rate * (1 + monthly_rate) ** num_payments
        ) / ((1 + monthly_rate) ** num_payments - 1)
        annual_debt_service = monthly_payment * 12
    else:
        annual_debt_service = 0

    net_annual_profit = annualized_profit - annual_debt_service
    roi_percent = (net_annual_profit / investment_eur) * 100 if investment_eur > 0 else 0.0
    equity_roi_percent = (net_annual_profit / equity_amount) * 100 if equity_amount > 0 else 0.0
    payback_years = investment_eur / net_annual_profit if net_annual_profit > 0 else float("inf")

    discount_rate = 0.065
    npv = sum(net_annual_profit / ((1 + discount_rate) ** year) for year in range(1, 6))
    npv -= investment_eur

    return {
        "analysis_type": f"Historical ROI ({months_count} months, from {start_year})",
        "window_months": months_count,
        "investment_eur": investment_eur,
        "debt_amount_eur": debt_amount,
        "equity_amount_eur": equity_amount,
        "annual_debt_service_eur": annual_debt_service,
        "gross_profit_eur": annualized_profit,
        "annualized_profit_eur": annualized_profit,
        "net_profit_eur": net_annual_profit,
        "roi_total_investment_percent": roi_percent,
        "roi_annual_percent": roi_percent,
        "roi_equity_percent": equity_roi_percent,
        "payback_years": payback_years,
        "npv_5y_eur": npv,
        "data_period": trends.get("data_period"),
        "total_months_available": trends.get("total_months", months_count),
    }


__all__ = [
    "enrich_cycle_stats",
    "build_cash_flow_summary",
    "calculate_historical_roi_metrics",
]
