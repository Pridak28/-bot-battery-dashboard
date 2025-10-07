"""
Battery Analytics Platform - Main Application
Single unified stylesheet version (src/web/assets/style.css)
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use('Agg')

from src.data.data_provider import DataProvider
from src.web.data import load_config
from src.web.ui import (
    render_ai_insights,
    render_frequency_regulation_simulator,
    render_historical_market_comparison,
    render_investment_financing_analysis,
    render_pzu_horizons,
)
from src.web.utils.styles import load_css, page_header, sidebar_title

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Battery Analytics Platform",
    page_icon="BA",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load ONLY global CSS - single source of truth
load_css()

# ============================================================================
# HEADER
# ============================================================================

page_header(
    "Battery Energy Storage Analytics",
    "Professional Revenue Modeling & Market Analysis Platform"
)

# ============================================================================
# NAVIGATION
# ============================================================================

view = st.radio(
    "Navigation",
    options=[
        "AI Insights",
        "PZU Horizons",
        "FR Simulator",
        "Market Comparison",
        "Investment & Financing",
    ],
    horizontal=True,
    label_visibility="collapsed"
)

# ============================================================================
# SIDEBAR CONFIGURATION
# ============================================================================

history_start: Optional[pd.Timestamp] = None
history_end: Optional[pd.Timestamp] = None
earliest_available_ts: Optional[pd.Timestamp] = None
latest_available_ts: Optional[pd.Timestamp] = None

with st.sidebar:
    sidebar_title("Configuration")

    cfg_path = st.text_input("Config file", value="config.yaml")
    if not Path(cfg_path).exists():
        st.error("config.yaml not found")
        st.stop()

    cfg = load_config(cfg_path)

    # Data sources
    with st.expander("Data Sources", expanded=True):
        default_pzu_csv = cfg["data"].get("pzu_forecast_csv")
        default_bm_csv = cfg["data"].get("bm_forecast_csv")

        pzu_csv_override = st.text_input("PZU history CSV", value=default_pzu_csv or "")
        bm_csv_override = st.text_input("BM history CSV", value=default_bm_csv or "")

        provider = DataProvider(
            pzu_csv=pzu_csv_override or default_pzu_csv,
            bm_csv=bm_csv_override or default_bm_csv
        )

        # Get available dates
        bm_dates: List[str] = []
        if provider.bm_csv and Path(provider.bm_csv).exists():
            try:
                df_bm = pd.read_csv(provider.bm_csv, usecols=["date"]).dropna()
                bm_dates = sorted(df_bm["date"].astype(str).unique().tolist())
            except:
                pass

        pzu_dates: List[str] = []
        if provider.pzu_csv and Path(provider.pzu_csv).exists():
            try:
                df_pzu = pd.read_csv(provider.pzu_csv, usecols=["date"]).dropna()
                pzu_dates = sorted(df_pzu["date"].astype(str).unique().tolist())
            except:
                pass

        available_dates = pzu_dates or bm_dates
        default_date = datetime.fromisoformat(
            (pzu_dates[-1] if pzu_dates else available_dates[-1])
        ).date() if available_dates else date.today()

        min_date = datetime.fromisoformat(
            (pzu_dates[0] if pzu_dates else available_dates[0])
        ).date() if available_dates else None

        chosen_date = st.date_input(
            "Target date",
            value=default_date,
            min_value=min_date,
            max_value=default_date
        )

        if min_date:
            earliest_available_ts = pd.Timestamp(min_date)
        if default_date:
            latest_available_ts = pd.Timestamp(default_date)

        # History window
        history_choice = st.selectbox(
            "History window",
            ["Full history", "Last 12 months", "Last 24 months", "Last 36 months"],
            index=0
        )

        if latest_available_ts:
            if history_choice == "Full history":
                history_start = earliest_available_ts
                history_end = latest_available_ts
            elif history_choice == "Last 12 months":
                history_start = latest_available_ts - pd.DateOffset(months=12)
            elif history_choice == "Last 24 months":
                history_start = latest_available_ts - pd.DateOffset(months=24)
            elif history_choice == "Last 36 months":
                history_start = latest_available_ts - pd.DateOffset(months=36)

    # Battery config
    with st.expander("Battery", expanded=True):
        capacity_mwh = float(cfg["battery"]["capacity_mwh"])
        power_mw = float(cfg["battery"]["power_mw"])
        eta_rt = float(cfg["battery"]["round_trip_efficiency"])

    # Run controls
    auto_run = st.checkbox("Auto run", value=True)
    run_btn = auto_run or st.button("Run Analysis")

    # Display options
    with st.expander("Display", expanded=False):
        currency_decimals = st.slider("Currency decimals", 0, 2, 0)
        percent_decimals = st.slider("Percent decimals", 0, 2, 1)
        thousands_sep = st.checkbox("Thousands separator", value=True)
        show_raw_tables = st.checkbox("Show raw tables", value=False)

# ============================================================================
# RENDER SELECTED VIEW
# ============================================================================

if view == "AI Insights":
    render_ai_insights()

elif view == "PZU Horizons":
    capacity_mwh, power_mw, history_start, history_end = render_pzu_horizons(
        cfg=cfg,
        provider=provider,
        history_start=history_start,
        history_end=history_end,
        earliest_available_ts=earliest_available_ts,
        latest_available_ts=latest_available_ts,
        capacity_mwh=capacity_mwh,
        power_mw=power_mw,
        eta_rt=eta_rt,
        run_analysis=run_btn,
        currency_decimals=currency_decimals,
        percent_decimals=percent_decimals,
        thousands_sep=thousands_sep,
        show_raw_tables=show_raw_tables,
    )

elif view == "FR Simulator":
    render_frequency_regulation_simulator(
        cfg,
        provider=provider,
        power_mw=power_mw,
        currency_decimals=currency_decimals,
        thousands_sep=thousands_sep,
        show_raw_tables=show_raw_tables,
    )

elif view == "Market Comparison":
    render_historical_market_comparison(
        cfg,
        capacity_mwh,
        eta_rt,
        currency_decimals=currency_decimals,
        thousands_sep=thousands_sep,
    )

elif view == "Investment & Financing":
    render_investment_financing_analysis(cfg)
