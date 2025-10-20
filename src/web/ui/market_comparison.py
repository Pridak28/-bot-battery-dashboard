from __future__ import annotations

import pandas as pd
import streamlit as st

from src.web.utils.formatting import format_currency
from src.web.utils.styles import section_header, kpi_card, kpi_grid


def render_historical_market_comparison(
    cfg: dict | None = None,
    capacity_mwh: float | None = None,
    eta_rt: float | None = None,
    *,
    currency_decimals: int,
    thousands_sep: bool,
) -> None:
    """Render comparison using cached results from PZU Horizons and FR Simulator."""
    st.caption("This comparison automatically loads data from PZU Horizons and FR Simulator.")

    # Auto-populate PZU data if missing
    pzu_metrics = st.session_state.get("pzu_market_metrics")
    if not pzu_metrics or not isinstance(pzu_metrics, dict) or "daily_history" not in pzu_metrics:
        # Try to auto-compute PZU data
        with st.spinner("Auto-loading PZU market data..."):
            try:
                from src.strategy.horizon import compute_best_fixed_cycle
                from src.web.data import find_in_data_dir
                from src.web.utils import safe_session_state_update, sanitize_session_value
                from datetime import datetime

                # Get provider data - use Path directly
                from pathlib import Path
                from src.web.config import project_root

                data_dir = project_root / "data"
                data_sources = cfg.get("data_sources", {})
                pzu_csv_name = (
                    cfg.get("pzu_hourly_csv") or
                    data_sources.get("pzu_forecast_csv") or
                    "pzu_history_3y.csv"
                )

                pzu_csv = data_dir / pzu_csv_name
                if not pzu_csv.exists():
                    st.warning(f"⚠️ PZU data file not found at: {pzu_csv}")
                    return

                # Use default battery specs if not provided
                if capacity_mwh is None:
                    capacity_mwh = float(cfg.get("capacity_mwh", 50.0))
                if eta_rt is None:
                    eta_rt = float(cfg.get("round_trip_efficiency", 0.9))

                power_mw = float(cfg.get("power_mw", 25.0))

                # Compute with default date range (last 12 months)
                result = compute_best_fixed_cycle(
                    pzu_csv,
                    capacity_mwh=capacity_mwh,
                    power_mw=power_mw,
                    round_trip_efficiency=eta_rt,
                    min_hours_per_day=24,
                )

                if result and result.get("daily_history") is not None:
                    daily_history = result.get("daily_history", pd.DataFrame())
                    if not daily_history.empty:
                        daily_history_dict = daily_history.to_dict('records')
                        safe_session_state_update("pzu_market_metrics", {
                            "daily_history": sanitize_session_value(daily_history_dict)
                        })
                        pzu_metrics = st.session_state.get("pzu_market_metrics")
                        st.success("✅ PZU data loaded successfully")
            except Exception as e:
                st.error(f"Failed to auto-load PZU data: {e}")
                return

    if not pzu_metrics or not isinstance(pzu_metrics, dict) or "daily_history" not in pzu_metrics:
        st.warning("⚠️ Unable to load PZU data. Please check PZU Horizons view.")
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

    # FR data - just check if it exists, don't auto-load
    # User needs to run FR Simulator first to populate data
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

            # Fill months without activation entries using averages from observed months
            for col in ["energy_cost_eur", "activation_revenue_eur", "activation_energy_mwh"]:
                if col in fr_months_df.columns:
                    fr_months_df[col] = pd.to_numeric(fr_months_df[col], errors="coerce")

            cost_mask = fr_months_df.get("energy_cost_eur", pd.Series(dtype=float)).fillna(0.0) > 0.0
            if cost_mask.any():
                avg_cost = fr_months_df.loc[cost_mask, "energy_cost_eur"].mean()
                fr_months_df.loc[~cost_mask, "energy_cost_eur"] = avg_cost

            act_mask = fr_months_df.get("activation_revenue_eur", pd.Series(dtype=float)).fillna(0.0) > 0.0
            if act_mask.any():
                avg_act = fr_months_df.loc[act_mask, "activation_revenue_eur"].mean()
                fr_months_df.loc[~act_mask, "activation_revenue_eur"] = avg_act

            energy_mask = fr_months_df.get("activation_energy_mwh", pd.Series(dtype=float)).fillna(0.0) > 0.0
            if energy_mask.any():
                avg_energy = fr_months_df.loc[energy_mask, "activation_energy_mwh"].mean()
                fr_months_df.loc[~energy_mask, "activation_energy_mwh"] = avg_energy

            if {"capacity_revenue_eur", "activation_revenue_eur"}.issubset(fr_months_df.columns):
                fr_months_df["total_revenue_eur"] = (
                    fr_months_df["capacity_revenue_eur"].fillna(0.0)
                    + fr_months_df["activation_revenue_eur"].fillna(0.0)
                )

            window_fr = min(window, len(fr_months_df))
            if window_fr > 0:
                fr_window = fr_months_df.tail(window_fr).reset_index(drop=True)
                fr_total_revenue = float(fr_window["total_revenue_eur"].sum())
                fr_annualized_revenue = fr_total_revenue * (12.0 / window_fr)

    section_header("Aggregated Results")
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
            st.info(
                "FR simulator data unavailable for the selected window. "
                "Run the Frequency Regulation simulator for the same date range "
                "to populate this comparison."
            )

    section_header("PZU Monthly Detail")
    pzu_display = pzu_window.rename(columns={"month": "Month", "total_profit_eur": "Profit €"})
    pzu_display["Profit €"] = pzu_display["Profit €"].apply(
        lambda v: format_currency(v, decimals=currency_decimals, thousands=thousands_sep)
    )
    st.dataframe(pzu_display, use_container_width=True)

    if not fr_window.empty:
        section_header("FR Monthly Detail")
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
        st.dataframe(fr_display, use_container_width=True)

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
            section_header("FR Annual Cash Flow (from simulator)")
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
            section_header("FR Simulated 3-Year Outlook (from simulator)")
            st.table(outlook_table)
