from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st

from src.web.data import backfill_fr_monthly_dataframe
from src.web.utils.formatting import format_currency
from src.web.utils.styles import section_header, kpi_card, kpi_grid


def render_investment_financing_analysis(cfg: dict) -> None:
    """Analyse investment and financing for FR and PZU businesses independently."""

    fr_metrics = st.session_state.get("fr_market_metrics")
    pzu_metrics = st.session_state.get("pzu_market_metrics")

    if not fr_metrics or not isinstance(fr_metrics, dict) or "annual" not in fr_metrics:
        st.info("Run the FR Simulator first to capture annual metrics.")
        return
    if not pzu_metrics or not isinstance(pzu_metrics, dict) or "daily_history" not in pzu_metrics:
        st.info("Run the PZU Horizons view to compute profitability before analysing financing.")
        return

    # Validate FR data has proper breakdown
    fr_months = fr_metrics.get("months", [])
    if fr_months:
        sample = fr_months[0] if len(fr_months) > 0 else {}
        if "capacity_revenue_eur" not in sample or "activation_revenue_eur" not in sample:
            st.warning("⚠️ **FR data needs to be regenerated**. Please re-run the FR Simulator to get detailed revenue breakdown (capacity vs activation). Using legacy data format may show €0 for breakdown columns.")

    section_header(" Investment & Financing Analysis")

    battery_cfg = cfg.get("battery", {})
    investment_cfg = cfg.get("investment", {})

    default_power = float(battery_cfg.get("power_mw", 20.0))
    default_capex_per_mw = float(investment_cfg.get("capex_per_mw", 250_000.0))
    default_additional_costs = float(investment_cfg.get("additional_costs", 0.0))
    default_equity_pct = float(investment_cfg.get("equity_percent", 30.0))
    default_interest = float(investment_cfg.get("loan_interest_percent", 6.0))
    default_term = int(investment_cfg.get("loan_term_years", 7))
    default_fr_opex = float(investment_cfg.get("fr_operating_cost_annual", 0.0))
    default_pzu_opex = float(investment_cfg.get("pzu_operating_cost_annual", 0.0))

    col_inputs = st.columns(3)
    with col_inputs[0]:
        capex_per_mw = st.number_input(
            "Capex per MW (€/MW)",
            min_value=0.0,
            value=default_capex_per_mw,
            step=50_000.0,
            help="Capital expenditure per contracted MW of power.",
        )
    with col_inputs[1]:
        project_power_mw = st.number_input(
            "Installed power (MW)",
            min_value=0.0,
            value=default_power,
            step=1.0,
            help="Total power deployed for FR/PZU strategies.",
        )
    with col_inputs[2]:
        additional_costs = st.number_input(
            "Additional fixed costs (€)",
            min_value=0.0,
            value=default_additional_costs,
            step=100_000.0,
            help="Balance of plant, integration, or other upfront costs not captured in capex per MW.",
        )

    total_investment = capex_per_mw * project_power_mw + additional_costs

    st.info("💡 **Business Comparison Mode**: Both FR and PZU are evaluated as separate competing business options using the SAME investment amount and financing structure.")
    st.metric("Total investment (per business)", format_currency(total_investment, decimals=0))

    col_fin = st.columns(3)
    with col_fin[0]:
        equity_pct = st.slider(
            "Equity share (%)",
            min_value=0,
            max_value=100,
            value=int(round(default_equity_pct)),
            help="Share of investment covered with equity for BOTH businesses (remainder financed with debt).",
        )
    with col_fin[1]:
        interest_rate_pct = st.number_input(
            "Loan interest (% p.a.)",
            min_value=0.0,
            max_value=30.0,
            value=default_interest,
            step=0.1,
        )
    with col_fin[2]:
        loan_term_years = int(
            st.number_input(
                "Loan term (years)",
                min_value=1,
                max_value=25,
                value=default_term,
                step=1,
            )
        )

    st.markdown("### Operating Cost Assumptions")
    cost_cols = st.columns(2)
    with cost_cols[0]:
        fr_operating_cost_annual = st.number_input(
            "FR operating cost (€/year)",
            min_value=0.0,
            value=default_fr_opex,
            step=25_000.0,
        )
    with cost_cols[1]:
        pzu_operating_cost_annual = st.number_input(
            "PZU operating cost (€/year)",
            min_value=0.0,
            value=default_pzu_opex,
            step=25_000.0,
        )

    equity_ratio = equity_pct / 100.0
    interest_rate = interest_rate_pct / 100.0

    # Both businesses use the SAME investment amount (competing alternatives)
    fr_investment = total_investment
    pzu_investment = total_investment
    fr_equity = fr_investment * equity_ratio
    pzu_equity = pzu_investment * equity_ratio
    fr_debt = fr_investment - fr_equity
    pzu_debt = pzu_investment - pzu_equity

    def _annuity_payment(principal: float, rate: float, periods: int) -> float:
        if principal <= 0 or periods <= 0:
            return 0.0
        if rate <= 0:
            return principal / periods
        factor = (1 + rate) ** periods
        return principal * rate * factor / (factor - 1)

    fr_annual_debt_service = _annuity_payment(fr_debt, interest_rate, loan_term_years)
    pzu_annual_debt_service = _annuity_payment(pzu_debt, interest_rate, loan_term_years)
    monthly_fr_opex = -fr_operating_cost_annual / 12.0 if fr_operating_cost_annual else 0.0
    monthly_pzu_opex = -pzu_operating_cost_annual / 12.0 if pzu_operating_cost_annual else 0.0
    monthly_fr_debt = -fr_annual_debt_service / 12.0 if fr_annual_debt_service else 0.0
    monthly_pzu_debt = -pzu_annual_debt_service / 12.0 if pzu_annual_debt_service else 0.0

    # Year range selection for simulation data
    st.markdown("### 📅 Simulation Data Period Selection")
    st.info("💡 Select which historical years to use for calculating average annual performance. Investment projection starts in 2025.")

    # Get available years from data
    raw_fr_months = fr_metrics.get("months") if isinstance(fr_metrics, dict) else None
    fr_months_df_temp = pd.DataFrame(raw_fr_months) if isinstance(raw_fr_months, list) and raw_fr_months else pd.DataFrame()

    daily_history_raw = pzu_metrics.get("daily_history")
    pzu_df_temp = pd.DataFrame(daily_history_raw) if isinstance(daily_history_raw, list) and daily_history_raw else pd.DataFrame()

    fr_available_years = []
    pzu_available_years = []

    if not fr_months_df_temp.empty:
        if "month" in fr_months_df_temp.columns:
            fr_months_df_temp["month_period"] = pd.to_datetime(fr_months_df_temp["month"], errors="coerce").dt.to_period("M")
        elif "month_period" in fr_months_df_temp.columns:
            fr_months_df_temp["month_period"] = pd.PeriodIndex(fr_months_df_temp["month_period"], freq="M")
        fr_months_df_temp = fr_months_df_temp.dropna(subset=["month_period"])
        if not fr_months_df_temp.empty:
            fr_available_years = sorted(fr_months_df_temp["month_period"].apply(lambda p: p.year).unique().tolist())

    if not pzu_df_temp.empty and "date" in pzu_df_temp.columns:
        pzu_df_temp["date"] = pd.to_datetime(pzu_df_temp["date"], errors="coerce")
        pzu_df_temp = pzu_df_temp.dropna(subset=["date"])
        if not pzu_df_temp.empty:
            pzu_available_years = sorted(pzu_df_temp["date"].dt.year.unique().tolist())

    year_cols = st.columns(2)
    with year_cols[0]:
        st.markdown("**FR Historical Data**")
        if fr_available_years:
            fr_year_range = st.multiselect(
                "Select years for FR averaging",
                options=fr_available_years,
                default=fr_available_years,
                key="fr_year_selection",
                help="Choose which years to include in the average calculation"
            )
        else:
            fr_year_range = []
            st.warning("No FR data available")

    with year_cols[1]:
        st.markdown("**PZU Historical Data**")
        if pzu_available_years:
            pzu_year_range = st.multiselect(
                "Select years for PZU averaging",
                options=pzu_available_years,
                default=pzu_available_years,
                key="pzu_year_selection",
                help="Choose which years to include in the average calculation"
            )
        else:
            pzu_year_range = []
            st.warning("No PZU data available")

    # Calculate FR average annual performance from selected years
    fr_months_df = pd.DataFrame(raw_fr_months) if isinstance(raw_fr_months, list) and raw_fr_months else pd.DataFrame()

    fr_gross_revenue = 0.0
    fr_energy_cost = 0.0
    fr_years_count = 0

    if not fr_months_df.empty and fr_year_range:
        # Parse month periods and extract years
        if "month" in fr_months_df.columns:
            fr_months_df["month_period"] = pd.to_datetime(fr_months_df["month"], errors="coerce").dt.to_period("M")
        elif "month_period" in fr_months_df.columns:
            fr_months_df["month_period"] = pd.PeriodIndex(fr_months_df["month_period"], freq="M")

        fr_months_df = fr_months_df.dropna(subset=["month_period"])

        if not fr_months_df.empty:
            fr_months_df["year"] = fr_months_df["month_period"].apply(lambda p: p.year)

            # Filter to selected years
            fr_months_df = fr_months_df[fr_months_df["year"].isin(fr_year_range)]

            if not fr_months_df.empty:
                # Group by year and sum revenues/costs
                yearly_fr = fr_months_df.groupby("year").agg({
                    "total_revenue_eur": "sum",
                    "energy_cost_eur": "sum"
                }).reset_index()

                fr_years_count = len(yearly_fr)

                # Calculate average annual values
                if fr_years_count > 0:
                    fr_gross_revenue = float(yearly_fr["total_revenue_eur"].mean())
                    fr_energy_cost = float(yearly_fr["energy_cost_eur"].mean())

    fr_base_net = fr_gross_revenue - fr_energy_cost
    fr_net_after_opex = fr_base_net - fr_operating_cost_annual
    fr_net_after_debt = fr_net_after_opex - fr_annual_debt_service

    # Calculate PZU average annual performance from selected years
    pzu_df = pd.DataFrame(daily_history_raw) if isinstance(daily_history_raw, list) and daily_history_raw else pd.DataFrame()

    pzu_base_net = 0.0
    pzu_years_count = 0

    if not pzu_df.empty and "daily_profit_eur" in pzu_df.columns and "date" in pzu_df.columns and pzu_year_range:
        pzu_df["date"] = pd.to_datetime(pzu_df["date"], errors="coerce")
        pzu_df = pzu_df.dropna(subset=["date"])

        if not pzu_df.empty:
            pzu_df["year"] = pzu_df["date"].dt.year

            # Filter to selected years
            pzu_df = pzu_df[pzu_df["year"].isin(pzu_year_range)]

            if not pzu_df.empty:
                # Group by year and sum daily profits
                yearly_pzu = pzu_df.groupby("year")["daily_profit_eur"].sum().reset_index()

                pzu_years_count = len(yearly_pzu)

                # Calculate average annual profit
                if pzu_years_count > 0:
                    pzu_base_net = float(yearly_pzu["daily_profit_eur"].mean())

    pzu_net_after_opex = pzu_base_net - pzu_operating_cost_annual
    pzu_net_after_debt = pzu_net_after_opex - pzu_annual_debt_service

    st.markdown("### 🏆 Business Comparison Summary")

    st.info(f"📊 **Analysis based on historical averages**: FR averaged over {fr_years_count} years | PZU averaged over {pzu_years_count} years")

    # Determine winner
    if fr_net_after_debt > pzu_net_after_debt:
        winner = "FR"
        winner_net = fr_net_after_debt
        loser_net = pzu_net_after_debt
        diff = fr_net_after_debt - pzu_net_after_debt
    else:
        winner = "PZU"
        winner_net = pzu_net_after_debt
        loser_net = fr_net_after_debt
        diff = pzu_net_after_debt - fr_net_after_debt

    st.success(f"✅ **{winner} is the better business option** with {format_currency(diff, decimals=0)} higher average annual net profit after debt")

    comp_cols = st.columns(3)
    with comp_cols[0]:
        st.metric("Same Investment", format_currency(total_investment, decimals=0))
    with comp_cols[1]:
        st.metric("FR Avg Annual Net Profit", format_currency(fr_net_after_debt, decimals=0), help=f"Average over {fr_years_count} years of historical data")
    with comp_cols[2]:
        st.metric("PZU Avg Annual Net Profit", format_currency(pzu_net_after_debt, decimals=0), help=f"Average over {pzu_years_count} years of historical data")

    st.markdown("### Financing Summary")
    summary_cols = st.columns(2)
    with summary_cols[0]:
        st.markdown("**🔋 Frequency Regulation (FR)**")
        st.metric("Investment", format_currency(fr_investment, decimals=0))
        st.metric("Equity", format_currency(fr_equity, decimals=0))
        st.metric("Debt principal", format_currency(fr_debt, decimals=0))
        st.metric("Annual debt service", format_currency(fr_annual_debt_service, decimals=0))
        st.metric("Net after debt", format_currency(fr_net_after_debt, decimals=0))
    with summary_cols[1]:
        st.markdown("**⚡ PZU Trading**")
        st.metric("Investment", format_currency(pzu_investment, decimals=0))
        st.metric("Equity", format_currency(pzu_equity, decimals=0))
        st.metric("Debt principal", format_currency(pzu_debt, decimals=0))
        st.metric("Annual debt service", format_currency(pzu_annual_debt_service, decimals=0))
        st.metric("Net after debt", format_currency(pzu_net_after_debt, decimals=0))

    st.markdown("### Operating Performance (Average Annual)")
    perf_cols = st.columns(2)
    with perf_cols[0]:
        st.metric("FR avg revenue", format_currency(fr_gross_revenue, decimals=0), help=f"Annual average over {fr_years_count} years")
        st.metric("FR avg energy cost", format_currency(fr_energy_cost, decimals=0), help=f"Annual average over {fr_years_count} years")
        st.metric("FR operating cost", format_currency(fr_operating_cost_annual, decimals=0))
        st.metric("FR avg net after opex", format_currency(fr_net_after_opex, decimals=0))
    with perf_cols[1]:
        st.metric("PZU avg gross profit", format_currency(pzu_base_net, decimals=0), help=f"Annual average over {pzu_years_count} years")
        st.metric("PZU operating cost", format_currency(pzu_operating_cost_annual, decimals=0))
        st.metric("PZU avg net after opex", format_currency(pzu_net_after_opex, decimals=0))

    raw_fr_months = fr_metrics.get("months") if isinstance(fr_metrics, dict) else None
    fr_months_df = pd.DataFrame(raw_fr_months) if isinstance(raw_fr_months, list) and raw_fr_months else pd.DataFrame()

    if not fr_months_df.empty:
        if "month" in fr_months_df.columns:
            try:
                fr_months_df["month_period"] = pd.PeriodIndex(fr_months_df["month"], freq="M")
            except Exception:
                fr_months_df["month_period"] = pd.to_datetime(fr_months_df["month"], errors="coerce").dt.to_period("M")
        elif "month_period" in fr_months_df.columns:
            fr_months_df["month_period"] = pd.PeriodIndex(fr_months_df["month_period"], freq="M")
        else:
            fr_months_df["month_period"] = pd.to_datetime(fr_months_df.index, errors="coerce").to_series().dt.to_period("M")
        fr_months_df = fr_months_df.dropna(subset=["month_period"]).sort_values("month_period")

    pzu_monthly = pd.DataFrame()
    if not pzu_df.empty and "date" in pzu_df.columns:
        pzu_df["date"] = pd.to_datetime(pzu_df["date"], errors="coerce")
        pzu_df = pzu_df.dropna(subset=["date"]).sort_values("date")
        if not pzu_df.empty and "daily_profit_eur" in pzu_df.columns:
            pzu_monthly = (
                pzu_df.assign(month=pzu_df["date"].dt.to_period("M"))
                .groupby("month", as_index=False)["daily_profit_eur"]
                .sum()
                .rename(columns={"daily_profit_eur": "total_profit_eur"})
                .sort_values("month")
            )
            pzu_monthly["month_period"] = pd.PeriodIndex(pzu_monthly["month"], freq="M")

    start_candidates: List[pd.Period] = []
    end_candidates: List[pd.Period] = []
    if not fr_months_df.empty:
        start_candidates.append(fr_months_df["month_period"].min())
        end_candidates.append(fr_months_df["month_period"].max())
    if not pzu_monthly.empty:
        start_candidates.append(pzu_monthly["month_period"].min())
        end_candidates.append(pzu_monthly["month_period"].max())

    range_start = min(start_candidates) if start_candidates else None
    range_end = max(end_candidates) if end_candidates else None

    if not fr_months_df.empty:
        fr_months_df = backfill_fr_monthly_dataframe(fr_months_df, start_period=range_start, end_period=range_end)
    if not pzu_monthly.empty and range_start is not None and range_end is not None:
        monthly_index = pd.period_range(range_start, range_end, freq="M")
        pzu_monthly = pzu_monthly.set_index("month_period").reindex(monthly_index)
        pzu_monthly["total_profit_eur"] = pd.to_numeric(pzu_monthly["total_profit_eur"], errors="coerce")
        if pzu_monthly["total_profit_eur"].notna().any():
            pzu_monthly["total_profit_eur"] = pzu_monthly["total_profit_eur"].fillna(pzu_monthly["total_profit_eur"].mean())
        else:
            pzu_monthly["total_profit_eur"] = 0.0
        pzu_monthly = pzu_monthly.reset_index().rename(columns={"index": "month_period"})
        pzu_monthly["month"] = pzu_monthly["month_period"].astype(str)

    fr_months_idx = fr_months_df.set_index("month_period") if not fr_months_df.empty else pd.DataFrame()
    pzu_months_idx = pzu_monthly.set_index("month_period") if not pzu_monthly.empty else pd.DataFrame()

    all_periods: List[pd.Period] = sorted(
        set(fr_months_idx.index.to_list() if not fr_months_idx.empty else [])
        | set(pzu_months_idx.index.to_list() if not pzu_months_idx.empty else [])
    )

    def _fill_mean(series: pd.Series) -> pd.Series:
        series = pd.to_numeric(series, errors="coerce")
        if series.notna().any():
            return series.fillna(series.mean())
        return series.fillna(0.0)

    if all_periods:
        if fr_months_idx.empty:
            fr_months_idx = pd.DataFrame(index=pd.Index(all_periods, name="month_period"))
        else:
            fr_months_idx = fr_months_idx.reindex(all_periods)
        # Ensure columns exist
        for col in ["capacity_revenue_eur", "activation_revenue_eur", "total_revenue_eur", "energy_cost_eur"]:
            if col not in fr_months_idx.columns:
                fr_months_idx[col] = np.nan

        # Fill missing values with mean
        for col in ["total_revenue_eur", "energy_cost_eur"]:
            fr_months_idx[col] = _fill_mean(fr_months_idx[col])

        # Calculate total if missing
        if fr_months_idx["total_revenue_eur"].isna().all():
            fr_months_idx["capacity_revenue_eur"] = _fill_mean(fr_months_idx["capacity_revenue_eur"])
            fr_months_idx["activation_revenue_eur"] = _fill_mean(fr_months_idx["activation_revenue_eur"])
            fr_months_idx["total_revenue_eur"] = fr_months_idx["capacity_revenue_eur"].fillna(0.0) + fr_months_idx["activation_revenue_eur"].fillna(0.0)
        else:
            # If we have total but missing breakdown, use total for capacity (conservative assumption)
            # This happens when historical data doesn't separate capacity vs activation
            if fr_months_idx["capacity_revenue_eur"].isna().all() and fr_months_idx["activation_revenue_eur"].isna().all():
                fr_months_idx["capacity_revenue_eur"] = fr_months_idx["total_revenue_eur"]
                fr_months_idx["activation_revenue_eur"] = 0.0
            else:
                # Fill individual components with mean if partially missing
                fr_months_idx["capacity_revenue_eur"] = _fill_mean(fr_months_idx["capacity_revenue_eur"])
                fr_months_idx["activation_revenue_eur"] = _fill_mean(fr_months_idx["activation_revenue_eur"])
        fr_months_idx["net_before_debt"] = (
            fr_months_idx["total_revenue_eur"].fillna(0.0) - fr_months_idx["energy_cost_eur"].fillna(0.0) + monthly_fr_opex
        )

        if pzu_months_idx.empty:
            pzu_months_idx = pd.DataFrame(index=pd.Index(all_periods, name="month_period"))
        else:
            pzu_months_idx = pzu_months_idx.reindex(all_periods)
        pzu_months_idx["net_before_debt"] = _fill_mean(pzu_months_idx.get("total_profit_eur", 0.0)) + monthly_pzu_opex

    loan_term_months = loan_term_years * 12

    def build_cashflow_tables(monthly_data_df: pd.DataFrame, monthly_debt_share: float, equity: float, is_fr: bool = True,
                               avg_annual_revenue: float = 0.0, avg_annual_cost: float = 0.0, avg_annual_profit: float = 0.0,
                               projection_mode: bool = True, start_year: int = 2025):
        """
        Build detailed cashflow tables with all revenue, cost, and debt components.

        monthly_data_df: DataFrame with columns like revenue, costs, operating expenses indexed by period (used only if projection_mode=False)
        monthly_debt_share: Monthly debt payment amount (negative)
        equity: Initial equity investment
        is_fr: True for FR (has capacity/activation revenue), False for PZU (has profit)
        avg_annual_revenue: Average annual revenue for projection
        avg_annual_cost: Average annual energy cost for projection
        avg_annual_profit: Average annual profit for projection (PZU only)
        projection_mode: If True, project forward from start_year using averages; if False, use historical data
        start_year: Year to start projection from (default 2025)
        """
        rows: List[Dict[str, object]] = []
        cumulative = -equity

        # Initial investment row
        initial_row = {
            "Period": None,
            "Month": "Initial (2024)",
            "Cumulative €": cumulative,
        }

        if is_fr:
            initial_row.update({
                "Capacity Revenue €": 0.0,
                "Activation Revenue €": 0.0,
                "Total Revenue €": 0.0,
                "Energy Cost €": 0.0,
                "Operating Cost €": 0.0,
                "Net before debt €": 0.0,
                "Debt Payment €": 0.0,
                "Net after debt €": -equity,
            })
        else:
            initial_row.update({
                "Trading Profit €": 0.0,
                "Operating Cost €": 0.0,
                "Net before debt €": 0.0,
                "Debt Payment €": 0.0,
                "Net after debt €": -equity,
            })

        rows.append(initial_row)

        # Projection mode: Generate forward-looking cashflow from start_year using averages
        if projection_mode:
            # Generate monthly cashflow for loan term using average annual values
            monthly_avg_revenue = avg_annual_revenue / 12.0
            monthly_avg_cost = avg_annual_cost / 12.0
            monthly_avg_profit = avg_annual_profit / 12.0
            monthly_operating_cost_val = abs(monthly_fr_opex) if is_fr else abs(monthly_pzu_opex)

            for month_idx in range(1, loan_term_months + 1):
                year = start_year + ((month_idx - 1) // 12)
                month_in_year = ((month_idx - 1) % 12) + 1
                month_label = f"{year}-{month_in_year:02d}"

                debt = monthly_debt_share if month_idx <= loan_term_months else 0.0

                if is_fr:
                    # Assume 70% capacity, 30% activation as rough split for projection
                    capacity_rev = monthly_avg_revenue * 0.7
                    activation_rev = monthly_avg_revenue * 0.3
                    total_rev = monthly_avg_revenue
                    energy_cost = monthly_avg_cost
                    net_before_debt = total_rev - energy_cost - monthly_operating_cost_val

                    net_after_debt = net_before_debt + debt
                    cumulative += net_after_debt

                    rows.append({
                        "Period": None,
                        "Month": month_label,
                        "Capacity Revenue €": capacity_rev,
                        "Activation Revenue €": activation_rev,
                        "Total Revenue €": total_rev,
                        "Energy Cost €": energy_cost,
                        "Operating Cost €": monthly_operating_cost_val,
                        "Net before debt €": net_before_debt,
                        "Debt Payment €": debt,
                        "Net after debt €": net_after_debt,
                        "Cumulative €": cumulative,
                    })
                else:
                    net_before_debt = monthly_avg_profit - monthly_operating_cost_val

                    net_after_debt = net_before_debt + debt
                    cumulative += net_after_debt

                    rows.append({
                        "Period": None,
                        "Month": month_label,
                        "Trading Profit €": monthly_avg_profit,
                        "Operating Cost €": monthly_operating_cost_val,
                        "Net before debt €": net_before_debt,
                        "Debt Payment €": debt,
                        "Net after debt €": net_after_debt,
                        "Cumulative €": cumulative,
                    })

            historical_months_count = loan_term_months

        # Process historical data months (only if not in projection mode)
        elif not monthly_data_df.empty:
            monthly_data_df = monthly_data_df.sort_index()

            for idx, (period, row_data) in enumerate(monthly_data_df.iterrows(), start=1):
                debt = monthly_debt_share if idx <= loan_term_months else 0.0

                if is_fr:
                    capacity_rev = float(row_data.get("capacity_revenue_eur", 0.0))
                    activation_rev = float(row_data.get("activation_revenue_eur", 0.0))
                    total_rev = float(row_data.get("total_revenue_eur", capacity_rev + activation_rev))
                    energy_cost = float(row_data.get("energy_cost_eur", 0.0))
                    operating_cost = abs(monthly_fr_opex)  # Display as positive cost
                    net_before_debt = float(row_data.get("net_before_debt", total_rev - energy_cost - operating_cost))

                    net_after_debt = net_before_debt + debt  # debt is negative
                    cumulative += net_after_debt

                    rows.append({
                        "Period": period,
                        "Month": str(period),
                        "Capacity Revenue €": capacity_rev,
                        "Activation Revenue €": activation_rev,
                        "Total Revenue €": total_rev,
                        "Energy Cost €": energy_cost,
                        "Operating Cost €": operating_cost,
                        "Net before debt €": net_before_debt,
                        "Debt Payment €": debt,
                        "Net after debt €": net_after_debt,
                        "Cumulative €": cumulative,
                    })
                else:
                    trading_profit = float(row_data.get("total_profit_eur", 0.0))
                    operating_cost = abs(monthly_pzu_opex)  # Display as positive cost
                    net_before_debt = float(row_data.get("net_before_debt", trading_profit - operating_cost))

                    net_after_debt = net_before_debt + debt  # debt is negative
                    cumulative += net_after_debt

                    rows.append({
                        "Period": period,
                        "Month": str(period),
                        "Trading Profit €": trading_profit,
                        "Operating Cost €": operating_cost,
                        "Net before debt €": net_before_debt,
                        "Debt Payment €": debt,
                        "Net after debt €": net_after_debt,
                        "Cumulative €": cumulative,
                    })

                historical_months_count = idx

        # CRITICAL FIX: Extend debt payments beyond historical data window (only for non-projection mode)
        # If loan term exceeds historical period, add remaining debt-only months
        if not projection_mode and historical_months_count < loan_term_months:
            remaining_months = loan_term_months - historical_months_count
            last_period = monthly_data_df.index[-1] if not monthly_data_df.empty else None

            for remaining_idx in range(1, remaining_months + 1):
                month_number = historical_months_count + remaining_idx
                # Project future period (approximate)
                if last_period:
                    future_period = last_period + remaining_idx
                    period_str = str(future_period)
                else:
                    period_str = f"Month {month_number}"

                # No operating revenue beyond historical data, only debt service
                debt = monthly_debt_share
                net_after_debt = debt  # Negative (debt payment only)
                cumulative += net_after_debt

                projected_row = {
                    "Period": None,
                    "Month": f"{period_str} (projected)",
                    "Net before debt €": 0.0,
                    "Debt Payment €": debt,
                    "Net after debt €": net_after_debt,
                    "Cumulative €": cumulative,
                }

                if is_fr:
                    projected_row.update({
                        "Capacity Revenue €": 0.0,
                        "Activation Revenue €": 0.0,
                        "Total Revenue €": 0.0,
                        "Energy Cost €": 0.0,
                        "Operating Cost €": 0.0,
                    })
                else:
                    projected_row.update({
                        "Trading Profit €": 0.0,
                        "Operating Cost €": 0.0,
                    })

                rows.append(projected_row)

        monthly_df = pd.DataFrame(rows)
        display_monthly = monthly_df.drop(columns=["Period"]).copy()

        # Format currency columns
        currency_cols = [col for col in display_monthly.columns if "€" in col]
        for col in currency_cols:
            display_monthly[col] = display_monthly[col].apply(lambda v: format_currency(v, decimals=0))

        # Build yearly summary
        initial_yearly_row = {"Year": 0, "Cumulative €": -equity}

        if is_fr:
            initial_yearly_row.update({
                "Capacity Revenue €": 0.0,
                "Activation Revenue €": 0.0,
                "Total Revenue €": 0.0,
                "Energy Cost €": 0.0,
                "Operating Cost €": 0.0,
                "Net before debt €": 0.0,
                "Debt Payment €": 0.0,
                "Net after debt €": -equity,
            })
        else:
            initial_yearly_row.update({
                "Trading Profit €": 0.0,
                "Operating Cost €": 0.0,
                "Net before debt €": 0.0,
                "Debt Payment €": 0.0,
                "Net after debt €": -equity,
            })

        yearly_rows: List[Dict[str, object]] = [initial_yearly_row]

        # For projection mode, parse year from Month string; for historical, use Period
        monthly_calc = monthly_df.copy()

        if projection_mode:
            # Parse year from Month string (e.g., "2025-01" -> 2025)
            monthly_calc = monthly_calc[monthly_calc["Month"] != "Initial (2024)"].copy()
            if not monthly_calc.empty:
                monthly_calc["Year"] = monthly_calc["Month"].apply(lambda m: int(str(m).split("-")[0]) if "-" in str(m) else None)
        else:
            # Use Period for historical data
            monthly_calc = monthly_calc.dropna(subset=["Period"]).copy()
            if not monthly_calc.empty:
                monthly_calc["Year"] = monthly_calc["Period"].apply(lambda p: int(p.year) if isinstance(p, pd.Period) else None)

        if not monthly_calc.empty:
            monthly_calc = monthly_calc.dropna(subset=["Year"]).copy()

            # Aggregate all numeric columns by year
            numeric_cols = [col for col in monthly_calc.columns if "€" in col and col != "Cumulative €"]
            yearly_group = (
                monthly_calc.groupby("Year")[numeric_cols]
                .sum()
                .reset_index()
                .sort_values("Year")
            )

            cumulative_year = -equity
            for _, row in yearly_group.iterrows():
                net_after = float(row["Net after debt €"])
                cumulative_year += net_after

                year_row = {
                    "Year": int(row["Year"]),
                    "Cumulative €": cumulative_year,
                }

                # Add all numeric columns to the year row
                for col in numeric_cols:
                    year_row[col] = float(row[col])

                yearly_rows.append(year_row)

        yearly_df = pd.DataFrame(yearly_rows)
        display_yearly = yearly_df.copy()

        # Format all currency columns
        yearly_currency_cols = [col for col in display_yearly.columns if "€" in col]
        for col in yearly_currency_cols:
            display_yearly[col] = display_yearly[col].apply(lambda v: format_currency(v, decimals=0))

        payback_year = next((row["Year"] for row in yearly_rows if row["Year"] and row["Cumulative €"] >= 0), None)
        total_net_after_debt = sum(row["Net after debt €"] for row in yearly_rows if row["Year"])
        roi = (total_net_after_debt / equity) if equity > 0 else 0.0

        # Calculate data coverage vs loan term
        data_months = historical_months_count
        data_coverage_pct = (data_months / loan_term_months * 100) if loan_term_months > 0 else 100

        return display_monthly, display_yearly, payback_year, roi, data_coverage_pct

    # Build projection cashflow tables from 2025 using calculated averages
    fr_monthly_display, fr_yearly_display, fr_payback_year, fr_roi, fr_data_coverage = build_cashflow_tables(
        fr_months_idx, monthly_fr_debt, fr_equity, is_fr=True,
        avg_annual_revenue=fr_gross_revenue, avg_annual_cost=fr_energy_cost, avg_annual_profit=0.0,
        projection_mode=True, start_year=2025
    )
    pzu_monthly_display, pzu_yearly_display, pzu_payback_year, pzu_roi, pzu_data_coverage = build_cashflow_tables(
        pzu_months_idx, monthly_pzu_debt, pzu_equity, is_fr=False,
        avg_annual_revenue=0.0, avg_annual_cost=0.0, avg_annual_profit=pzu_base_net,
        projection_mode=True, start_year=2025
    )

    # Warn if loan term exceeds data window
    if fr_data_coverage < 100:
        st.warning(
            f"⚠️ FR: Loan term ({loan_term_years} years) exceeds historical data period "
            f"({fr_data_coverage:.0f}% coverage). Remaining {100-fr_data_coverage:.0f}% of debt payments "
            f"projected with no operating revenue (conservative estimate)."
        )

    if pzu_data_coverage < 100:
        st.warning(
            f"⚠️ PZU: Loan term ({loan_term_years} years) exceeds historical data period "
            f"({pzu_data_coverage:.0f}% coverage). Remaining {100-pzu_data_coverage:.0f}% of debt payments "
            f"projected with no operating revenue (conservative estimate)."
        )

    st.markdown("### FR Cashflow")
    if not fr_monthly_display.empty:
        fr_view = st.radio("FR table view", ["Monthly", "Yearly"], key="fr_cashflow_view")
        if fr_view == "Monthly":
            st.dataframe(fr_monthly_display, width="stretch")
        else:
            st.dataframe(fr_yearly_display, width="stretch")
    else:
        st.info("FR monthly cashflow data unavailable; run the FR Simulator for historical periods.")

    st.markdown("### PZU Cashflow")
    if not pzu_monthly_display.empty:
        pzu_view = st.radio("PZU table view", ["Monthly", "Yearly"], key="pzu_cashflow_view")
        if pzu_view == "Monthly":
            st.dataframe(pzu_monthly_display, width="stretch")
        else:
            st.dataframe(pzu_yearly_display, width="stretch")
    else:
        st.info("PZU monthly cashflow data unavailable; run the PZU Horizons analysis for historical periods.")

    st.markdown("### 📊 Payback & ROI Analysis")

    # Calculate average annual profit and annualized ROI
    fr_years = len(fr_yearly_display) if not fr_yearly_display.empty else 0
    pzu_years = len(pzu_yearly_display) if not pzu_yearly_display.empty else 0

    fr_annual_roi = (fr_roi / fr_years * 100) if fr_years > 0 and fr_equity > 0 else 0.0
    pzu_annual_roi = (pzu_roi / pzu_years * 100) if pzu_years > 0 and pzu_equity > 0 else 0.0

    if fr_years == 0 and pzu_years == 0:
        st.info("⚠️ No data available. Run FR Simulator and PZU Horizons to populate ROI analysis.")
    else:
        payback_cols = st.columns(2)

        with payback_cols[0]:
            st.markdown("#### Frequency Regulation (FR)")

            if fr_years > 0:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Payback Year", "—" if fr_payback_year is None else str(fr_payback_year), help="Year when cumulative profit becomes positive")
                with col2:
                    st.metric("Total ROI", "—" if fr_equity <= 0 else f"{fr_roi * 100:.1f}%", help=f"Total return over {fr_years} years")
                with col3:
                    st.metric("Annual ROI", "—" if fr_equity <= 0 else f"{fr_annual_roi:.1f}%", help="Average return per year")

                # Monthly bank payment (use annuity output)
                monthly_debt_fr = -monthly_fr_debt
                st.caption(f"💳 **Monthly Bank Payment:** {format_currency(monthly_debt_fr, decimals=0)}")

                # Show yearly profits with coverage indicator
                if not fr_yearly_display.empty:
                    st.caption(f"**Yearly Profit Summary** ({fr_years} years)")

                    yearly_debt = monthly_debt_fr * 12

                    for idx, row in fr_yearly_display.iterrows():
                        year = row['Year']

                        if year in (0, None):
                            st.caption(
                                f"• {row['Year']}: {row['Net after debt €']} (Construction phase – equity deployed, loan repayment begins with operations)"
                            )
                            continue

                        # Parse the formatted currency string back to float
                        net_before_str = row.get('Net before debt €', '€0')
                        if isinstance(net_before_str, str):
                            net_before = float(net_before_str.replace('€', '').replace(',', '').replace(' ', ''))
                        else:
                            net_before = float(net_before_str)

                        profit_str = row['Net after debt €']

                        # Check if revenue covers debt payment
                        deficit = abs(yearly_debt) - net_before if net_before < abs(yearly_debt) else 0.0

                        if net_before >= abs(yearly_debt):
                            indicator = "✅ Covers debt"
                        else:
                            indicator = f"❌ Cannot cover debt (deficit: {format_currency(deficit, decimals=0)})"

                        st.caption(f"• {year}: {profit_str} ({indicator})")
            else:
                st.info("Run FR Simulator to see data")

        with payback_cols[1]:
            st.markdown("#### PZU Trading")

            if pzu_years > 0:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Payback Year", "—" if pzu_payback_year is None else str(pzu_payback_year), help="Year when cumulative profit becomes positive")
                with col2:
                    st.metric("Total ROI", "—" if pzu_equity <= 0 else f"{pzu_roi * 100:.1f}%", help=f"Total return over {pzu_years} years")
                with col3:
                    st.metric("Annual ROI", "—" if pzu_equity <= 0 else f"{pzu_annual_roi:.1f}%", help="Average return per year")

                # Monthly bank payment (use annuity output)
                monthly_debt_pzu = -monthly_pzu_debt
                st.caption(f"💳 **Monthly Bank Payment:** {format_currency(monthly_debt_pzu, decimals=0)}")

                # Show yearly profits with coverage indicator
                if not pzu_yearly_display.empty:
                    st.caption(f"**Yearly Profit Summary** ({pzu_years} years)")

                    yearly_debt = monthly_debt_pzu * 12

                    for idx, row in pzu_yearly_display.iterrows():
                        year = row['Year']

                        if year in (0, None):
                            st.caption(
                                f"• {row['Year']}: {row['Net after debt €']} (Construction phase – equity deployed, loan repayment begins with operations)"
                            )
                            continue

                        # Parse the formatted currency string back to float
                        net_before_str = row.get('Net before debt €', '€0')
                        if isinstance(net_before_str, str):
                            net_before = float(net_before_str.replace('€', '').replace(',', '').replace(' ', ''))
                        else:
                            net_before = float(net_before_str)

                        profit_str = row['Net after debt €']

                        # Check if revenue covers debt payment
                        deficit = abs(yearly_debt) - net_before if net_before < abs(yearly_debt) else 0.0

                        if net_before >= abs(yearly_debt):
                            indicator = "✅ Covers debt"
                        else:
                            indicator = f"❌ Cannot cover debt (deficit: {format_currency(deficit, decimals=0)})"

                        st.caption(f"• {year}: {profit_str} ({indicator})")
            else:
                st.info("Run PZU Horizons to see data")
