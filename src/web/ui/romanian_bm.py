from __future__ import annotations

from datetime import date
import numpy as np
import pandas as pd
import streamlit as st

from src.data.data_provider import DataProvider
from src.web.analysis import analyze_romanian_balancing_market, bm_stats
from src.web.data import load_balancing_day_series
from src.web.utils import safe_pyplot_figure
from src.web.utils.formatting import get_chart_colors
from src.web.utils.styles import section_header, kpi_card, kpi_grid


def render_romanian_balancing_view(
    *,
    provider: DataProvider,
    chosen_date: date,
    capacity_mwh: float,
) -> None:
    """Render Romanian balancing market analysis for the selected date."""
    bm_series = load_balancing_day_series(provider.bm_csv, chosen_date.isoformat())

    section_header(" Romanian Balancing Market Analysis")
    if bm_series is None or len(bm_series) == 0:
        st.info("No balancing market data for the selected date.")
        return

    analysis = analyze_romanian_balancing_market(bm_series, capacity_mwh)
    if "error" in analysis:
        st.error(analysis["error"])
        return

    st.success(f"{analysis['market_name']}")
    st.caption(
        f"Operator: {analysis['operator']} | Platform: {analysis['trading_platform']}"
    )

    section_header(" Market Characteristics")
    char_col1, char_col2 = st.columns(2)
    char_col1.metric("Time Resolution", analysis["time_resolution"])
    char_col2.metric("Market Type", analysis["market_type"])
    char_col1.metric("Data Points", analysis["data_points"])
    min_bid = analysis.get("minimum_bid_size_mw")
    char_col2.metric("Min Bid Size", f"{min_bid} MW" if min_bid is not None else "N/A")

    section_header(" Price Analysis")
    price_col1, price_col2, price_col3 = st.columns(3)
    price_col1.metric("Avg Price (EUR)", f"€{analysis['avg_imbalance_price_eur_mwh']:.2f}/MWh")
    price_col2.metric("Price Range (EUR)", f"€{analysis['price_range_eur_mwh']:.2f}/MWh")
    price_col3.metric("Volatility", f"{analysis['price_volatility']:.2f}")

    balance = analysis.get("system_imbalance_analysis")
    if balance:
        section_header(" System Balance Analysis")
        bal_col1, bal_col2, bal_col3 = st.columns(3)
        bal_col1.metric("System Deficit", f"{balance['deficit_percentage']:.1f}%", help="Periods with positive prices")
        bal_col2.metric("System Surplus", f"{balance['surplus_percentage']:.1f}%", help="Periods with negative prices")
        bal_col3.metric("Balanced System", f"{balance['balanced_percentage']:.1f}%", help="Periods with zero prices")
        dominant = balance.get("dominant_imbalance")
        if dominant == "Generation Deficit":
            st.warning(f"⚠️ System predominantly in **{dominant}** (excess demand)")
        elif dominant:
            st.info(f"ℹ️ System predominantly in **{dominant}** (excess generation)")

    section_header(" Frequency Regulation Services")
    response_seconds = analysis.get("minimum_response_time_seconds", 0)
    resp_col1, resp_col2, resp_col3 = st.columns(3)
    resp_col1.metric("FCR Response", f"{response_seconds}s")
    resp_col2.metric("aFRR Response", f"{response_seconds * 10}s")
    resp_col3.metric("mFRR Response", f"{response_seconds * 30}s")

    section_header(" Revenue Model for BESS")
    if analysis.get("arbitrage_trading"):
        st.success("Suitable for arbitrage trading")
    else:
        st.info("❌ Not suitable for arbitrage trading")

    if analysis.get("frequency_regulation_services"):
        st.success("Suitable for frequency regulation services")
        st.caption("Revenue streams: Availability payments + Activation payments")
    else:
        st.warning("❌ Not suitable for frequency regulation")

    section_header(" Regulatory Framework")
    regulatory = analysis.get("regulatory_framework", {})
    st.write(f"**Grid Operator:** {regulatory.get('grid_operator', 'N/A')}")
    st.write(f"**Market Regulator:** {regulatory.get('market_regulator', 'N/A')}")
    st.write(f"**EU Compliance:** {regulatory.get('european_compliance', 'N/A')}")
    st.write(f"**Grid Code:** {regulatory.get('grid_code', 'N/A')}")

    section_header(" Key Differences from OPCOM")
    for difference in analysis.get("key_differences_from_opcom", []):
        st.write(f"• {difference}")

    section_header(" BESS Participation Requirements")
    for requirement in analysis.get("bess_participation_requirements", []):
        st.write(f"• {requirement}")

    section_header(" Imbalance Prices")
    bm_df = pd.DataFrame({"slot": list(range(len(bm_series))), "price_ron_mwh": bm_series})
    bm_df = bm_df.replace([np.inf, -np.inf], np.nan).dropna()
    if bm_df.empty:
        st.info("No balancing price points to plot for the selected date.")
    else:
        with safe_pyplot_figure(figsize=(10, 3)) as (fig_bm, ax_bm):
            chart_colors = get_chart_colors()
            ax_bm.plot(bm_df["slot"], bm_df["price_ron_mwh"], color=chart_colors["primary"])
            ax_bm.set_xlabel("Slot (15-min)")
            ax_bm.set_ylabel("Price (RON/MWh)")
            ax_bm.grid(True, alpha=0.3)
            st.pyplot(fig_bm, clear_figure=True)

    section_header(" Statistical Summary")
    st.json(bm_stats(bm_series))
