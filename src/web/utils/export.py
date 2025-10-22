"""
Financial Data Export Module for Banking and Investment Analysis

Generates professional Excel and CSV reports with:
- Executive Summary
- Detailed Cashflow Projections
- ROI Analysis
- Revenue Breakdown
- Debt Service Schedule
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Dict, List, Optional, Any

import pandas as pd
import streamlit as st


def format_currency_excel(value: float) -> str:
    """Format currency for Excel display"""
    if value >= 0:
        return f"€{value:,.2f}"
    else:
        return f"-€{abs(value):,.2f}"


def create_executive_summary(
    fr_metrics: Dict[str, Any],
    pzu_metrics: Dict[str, Any],
    investment_eur: float,
    equity_eur: float,
    debt_eur: float,
    loan_term_years: int,
    interest_rate: float,
    fr_years_analyzed: int,
    pzu_years_analyzed: int,
) -> pd.DataFrame:
    """Create executive summary sheet"""

    fr_annual = fr_metrics.get("annual", {})
    pzu_annual = pzu_metrics.get("annual", {})

    summary_data = [
        ["BATTERY ENERGY STORAGE PROJECT - EXECUTIVE SUMMARY", ""],
        ["Report Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["", ""],
        ["INVESTMENT STRUCTURE", ""],
        ["Total Investment", format_currency_excel(investment_eur)],
        ["Equity (30%)", format_currency_excel(equity_eur)],
        ["Debt (70%)", format_currency_excel(debt_eur)],
        ["Loan Term", f"{loan_term_years} years"],
        ["Interest Rate", f"{interest_rate*100:.1f}%"],
        ["", ""],
        ["FREQUENCY REGULATION (FR) BUSINESS", ""],
        ["Historical Data Period", f"{fr_years_analyzed} years analyzed"],
        ["Annual Revenue (avg)", format_currency_excel(fr_annual.get("total", 0))],
        ["Annual Energy Cost (avg)", format_currency_excel(fr_annual.get("energy_cost", 0))],
        ["Net Profit After Debt", format_currency_excel(fr_annual.get("net", 0))],
        ["Annual ROI", f"{(fr_annual.get('net', 0) / investment_eur * 100) if investment_eur > 0 else 0:.1f}%"],
        ["", ""],
        ["PZU ARBITRAGE BUSINESS", ""],
        ["Historical Data Period", f"{pzu_years_analyzed} years analyzed"],
        ["Annual Gross Profit (avg)", format_currency_excel(pzu_annual.get("total", 0))],
        ["Net Profit After Debt", format_currency_excel(pzu_annual.get("net", 0))],
        ["Annual ROI", f"{(pzu_annual.get('net', 0) / investment_eur * 100) if investment_eur > 0 else 0:.1f}%"],
        ["", ""],
        ["BUSINESS COMPARISON", ""],
    ]

    fr_net = fr_annual.get("net", 0)
    pzu_net = pzu_annual.get("net", 0)

    if fr_net > pzu_net:
        summary_data.append(["Recommended Strategy", "Frequency Regulation (FR)"])
        summary_data.append(["Advantage Over Alternative", format_currency_excel(fr_net - pzu_net)])
    else:
        summary_data.append(["Recommended Strategy", "PZU Arbitrage"])
        summary_data.append(["Advantage Over Alternative", format_currency_excel(pzu_net - fr_net)])

    return pd.DataFrame(summary_data, columns=["Metric", "Value"])


def create_fr_revenue_breakdown(fr_metrics: Dict[str, Any]) -> pd.DataFrame:
    """Create detailed FR revenue breakdown"""

    months = fr_metrics.get("months", [])
    if not months:
        return pd.DataFrame()

    breakdown_data = []
    for month_data in months:
        breakdown_data.append({
            "Month": month_data.get("month", ""),
            "Capacity Revenue (€)": month_data.get("capacity_revenue_eur", 0),
            "Activation Revenue (€)": month_data.get("activation_revenue_eur", 0),
            "Total Revenue (€)": month_data.get("total_revenue_eur", 0),
            "Energy Cost (€)": month_data.get("energy_cost_eur", 0),
            "Activation Energy (MWh)": month_data.get("activation_energy_mwh", 0),
            "Net Margin (€)": (
                month_data.get("total_revenue_eur", 0) -
                month_data.get("energy_cost_eur", 0)
            ),
        })

    df = pd.DataFrame(breakdown_data)

    # Add totals row
    if not df.empty:
        totals = {
            "Month": "TOTAL",
            "Capacity Revenue (€)": df["Capacity Revenue (€)"].sum(),
            "Activation Revenue (€)": df["Activation Revenue (€)"].sum(),
            "Total Revenue (€)": df["Total Revenue (€)"].sum(),
            "Energy Cost (€)": df["Energy Cost (€)"].sum(),
            "Activation Energy (MWh)": df["Activation Energy (MWh)"].sum(),
            "Net Margin (€)": df["Net Margin (€)"].sum(),
        }
        df = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)

    return df


def create_pzu_daily_summary(pzu_metrics: Dict[str, Any]) -> pd.DataFrame:
    """Create PZU daily profit summary (aggregated by month)"""

    daily_history = pzu_metrics.get("daily_history", [])
    if not daily_history:
        return pd.DataFrame()

    df = pd.DataFrame(daily_history)
    if "date" not in df.columns or "daily_profit_eur" not in df.columns:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    if df.empty:
        return pd.DataFrame()

    # Aggregate by month
    df["month"] = df["date"].dt.to_period("M").astype(str)
    monthly = df.groupby("month").agg({
        "daily_profit_eur": ["sum", "mean", "count"],
        "daily_revenue_eur": "sum",
        "daily_cost_eur": "sum",
    }).reset_index()

    monthly.columns = [
        "Month",
        "Total Profit (€)",
        "Avg Daily Profit (€)",
        "Days",
        "Total Revenue (€)",
        "Total Cost (€)",
    ]

    # Add totals row
    totals = {
        "Month": "TOTAL",
        "Total Profit (€)": monthly["Total Profit (€)"].sum(),
        "Avg Daily Profit (€)": monthly["Total Profit (€)"].sum() / monthly["Days"].sum(),
        "Days": monthly["Days"].sum(),
        "Total Revenue (€)": monthly["Total Revenue (€)"].sum(),
        "Total Cost (€)": monthly["Total Cost (€)"].sum(),
    }
    monthly = pd.concat([monthly, pd.DataFrame([totals])], ignore_index=True)

    return monthly


def create_cashflow_projection(
    annual_revenue: float,
    annual_cost: float,
    annual_opex: float,
    annual_debt_service: float,
    equity: float,
    loan_term_years: int,
    start_year: int = 2025,
    projection_years: int = 10,
) -> pd.DataFrame:
    """Create year-by-year cashflow projection"""

    cashflow_data = []
    cumulative = -equity  # Initial investment

    # Year 0: Initial investment
    cashflow_data.append({
        "Year": 0,
        "Period": "Construction (2024)",
        "Revenue (€)": 0,
        "Operating Cost (€)": 0,
        "Energy Cost (€)": 0,
        "Debt Service (€)": 0,
        "Net Cashflow (€)": -equity,
        "Cumulative (€)": cumulative,
    })

    # Operating years
    for year in range(1, projection_years + 1):
        # Debt service only during loan term
        debt = -annual_debt_service if year <= loan_term_years else 0

        net_before_debt = annual_revenue - annual_cost - annual_opex
        net_cashflow = net_before_debt + debt  # debt is negative
        cumulative += net_cashflow

        cashflow_data.append({
            "Year": year,
            "Period": str(start_year + year - 1),
            "Revenue (€)": annual_revenue,
            "Operating Cost (€)": -annual_opex,
            "Energy Cost (€)": -annual_cost,
            "Debt Service (€)": debt,
            "Net Cashflow (€)": net_cashflow,
            "Cumulative (€)": cumulative,
        })

    return pd.DataFrame(cashflow_data)


def create_debt_schedule(
    debt_principal: float,
    interest_rate: float,
    loan_term_years: int,
    start_year: int = 2025,
) -> pd.DataFrame:
    """Create detailed debt amortization schedule"""

    if debt_principal <= 0 or loan_term_years <= 0:
        return pd.DataFrame()

    # Calculate monthly payment
    monthly_rate = interest_rate / 12
    num_payments = loan_term_years * 12

    if monthly_rate > 0:
        monthly_payment = debt_principal * (
            monthly_rate * (1 + monthly_rate) ** num_payments
        ) / ((1 + monthly_rate) ** num_payments - 1)
    else:
        monthly_payment = debt_principal / num_payments

    schedule_data = []
    remaining_balance = debt_principal

    for month in range(1, num_payments + 1):
        year = start_year + ((month - 1) // 12)
        month_in_year = ((month - 1) % 12) + 1

        interest_payment = remaining_balance * monthly_rate
        principal_payment = monthly_payment - interest_payment
        remaining_balance -= principal_payment

        schedule_data.append({
            "Payment #": month,
            "Year": year,
            "Month": f"{year}-{month_in_year:02d}",
            "Payment (€)": monthly_payment,
            "Principal (€)": principal_payment,
            "Interest (€)": interest_payment,
            "Remaining Balance (€)": max(0, remaining_balance),
        })

    return pd.DataFrame(schedule_data)


def export_financial_package_to_excel(
    fr_metrics: Optional[Dict[str, Any]],
    pzu_metrics: Optional[Dict[str, Any]],
    investment_eur: float,
    equity_eur: float,
    debt_eur: float,
    loan_term_years: int,
    interest_rate: float,
    fr_opex_annual: float,
    pzu_opex_annual: float,
    fr_years_analyzed: int,
    pzu_years_analyzed: int,
) -> bytes:
    """
    Export complete financial package to Excel with multiple sheets

    Returns Excel file as bytes for download
    """

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Executive Summary
        if fr_metrics and pzu_metrics:
            summary_df = create_executive_summary(
                fr_metrics,
                pzu_metrics,
                investment_eur,
                equity_eur,
                debt_eur,
                loan_term_years,
                interest_rate,
                fr_years_analyzed,
                pzu_years_analyzed,
            )
            summary_df.to_excel(writer, sheet_name="Executive Summary", index=False)

        # Sheet 2: FR Revenue Breakdown
        if fr_metrics:
            fr_breakdown = create_fr_revenue_breakdown(fr_metrics)
            if not fr_breakdown.empty:
                fr_breakdown.to_excel(writer, sheet_name="FR Revenue Detail", index=False)

        # Sheet 3: PZU Monthly Summary
        if pzu_metrics:
            pzu_summary = create_pzu_daily_summary(pzu_metrics)
            if not pzu_summary.empty:
                pzu_summary.to_excel(writer, sheet_name="PZU Monthly Summary", index=False)

        # Sheet 4: FR Cashflow Projection (10 years)
        if fr_metrics:
            fr_annual = fr_metrics.get("annual", {})
            fr_cashflow = create_cashflow_projection(
                annual_revenue=fr_annual.get("total", 0),
                annual_cost=fr_annual.get("energy_cost", 0),
                annual_opex=fr_opex_annual,
                annual_debt_service=fr_annual.get("debt", 0),
                equity=equity_eur,
                loan_term_years=loan_term_years,
            )
            if not fr_cashflow.empty:
                fr_cashflow.to_excel(writer, sheet_name="FR Cashflow 10Y", index=False)

        # Sheet 5: PZU Cashflow Projection (10 years)
        if pzu_metrics:
            pzu_annual = pzu_metrics.get("annual", {})
            pzu_cashflow = create_cashflow_projection(
                annual_revenue=pzu_annual.get("total", 0),
                annual_cost=0,  # PZU profit already net of energy costs
                annual_opex=pzu_opex_annual,
                annual_debt_service=pzu_annual.get("debt", 0),
                equity=equity_eur,
                loan_term_years=loan_term_years,
            )
            if not pzu_cashflow.empty:
                pzu_cashflow.to_excel(writer, sheet_name="PZU Cashflow 10Y", index=False)

        # Sheet 6: Debt Amortization Schedule
        debt_schedule = create_debt_schedule(
            debt_principal=debt_eur,
            interest_rate=interest_rate,
            loan_term_years=loan_term_years,
        )
        if not debt_schedule.empty:
            debt_schedule.to_excel(writer, sheet_name="Debt Schedule", index=False)

    output.seek(0)
    return output.getvalue()


def add_export_buttons(
    fr_metrics: Optional[Dict[str, Any]],
    pzu_metrics: Optional[Dict[str, Any]],
    investment_eur: float,
    equity_eur: float,
    debt_eur: float,
    loan_term_years: int,
    interest_rate: float,
    fr_opex_annual: float,
    pzu_opex_annual: float,
    fr_years_analyzed: int,
    pzu_years_analyzed: int,
) -> None:
    """
    Add export buttons to Streamlit UI

    Call this function in the Investment & Finance view
    """

    st.markdown("---")
    st.markdown("### 📊 Export Financial Reports")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown("""
        **Professional reports for banks, investors, and stakeholders**

        Includes:
        - Executive Summary
        - Detailed Revenue Breakdown (FR & PZU)
        - 10-Year Cashflow Projections
        - Debt Amortization Schedule
        - ROI Analysis
        """)

    with col2:
        # Excel Export Button
        if st.button("📥 Export to Excel", type="primary", use_container_width=True):
            try:
                excel_data = export_financial_package_to_excel(
                    fr_metrics=fr_metrics,
                    pzu_metrics=pzu_metrics,
                    investment_eur=investment_eur,
                    equity_eur=equity_eur,
                    debt_eur=debt_eur,
                    loan_term_years=loan_term_years,
                    interest_rate=interest_rate,
                    fr_opex_annual=fr_opex_annual,
                    pzu_opex_annual=pzu_opex_annual,
                    fr_years_analyzed=fr_years_analyzed,
                    pzu_years_analyzed=pzu_years_analyzed,
                )

                filename = f"Battery_Financial_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

                st.download_button(
                    label="⬇️ Download Excel Report",
                    data=excel_data,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

                st.success("✅ Excel report generated successfully!")

            except Exception as e:
                st.error(f"❌ Error generating Excel report: {e}")

    with col3:
        # CSV Export Button (simpler alternative)
        if st.button("📄 Export Summary CSV", use_container_width=True):
            try:
                summary_df = create_executive_summary(
                    fr_metrics or {},
                    pzu_metrics or {},
                    investment_eur,
                    equity_eur,
                    debt_eur,
                    loan_term_years,
                    interest_rate,
                    fr_years_analyzed,
                    pzu_years_analyzed,
                )

                csv_data = summary_df.to_csv(index=False).encode('utf-8')
                filename = f"Battery_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

                st.download_button(
                    label="⬇️ Download CSV Summary",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    use_container_width=True,
                )

                st.success("✅ CSV summary generated successfully!")

            except Exception as e:
                st.error(f"❌ Error generating CSV: {e}")
