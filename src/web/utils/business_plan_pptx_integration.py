"""
PowerPoint Business Plan Integration for Streamlit UI
======================================================
Integrates the PowerPoint generator with Investment & Financing page
"""

from __future__ import annotations

import io
from typing import Dict, Optional, Any
import streamlit as st
from pathlib import Path

# Import the PowerPoint generator
from src.web.utils.business_plan_pptx import generate_business_plan_pptx


def add_powerpoint_button(
    fr_metrics: Optional[Dict[str, Any]],
    pzu_metrics: Optional[Dict[str, Any]],
    capacity_mwh: float,
    power_mw: float,
    investment_eur: float,
    equity_eur: float,
    debt_eur: float,
    loan_term_years: int,
    interest_rate: float,
    fr_opex_annual: float,
    pzu_opex_annual: float,
) -> None:
    """
    Add PowerPoint generation button to Streamlit UI with Bloomberg/tech design

    Integrates with Investment & Financing page alongside Excel and Word exports
    """

    st.markdown("---")
    st.markdown("## 🎯 Investment Pitch Deck (PowerPoint)")
    st.markdown("### Professional 12-Slide Presentation with Bloomberg Design")

    # Preview section with key highlights
    st.markdown("#### 📊 Presentation Contents")

    col1, col2 = st.columns(2)

    with col1:
        st.info("""
        **Executive Slides:**
        • Title & Executive Summary
        • Market Opportunity
        • Revenue Streams (PZU & FR)
        • Technical Specifications
        • Risk Management
        """)

    with col2:
        st.info("""
        **Financial Slides:**
        • 5-Year Revenue Forecast
        • Investment Structure
        • ROI & Payback Analysis
        • Financial Projections
        • Next Steps & Timeline
        """)

    # Calculate key metrics for preview
    if fr_metrics and "annual" in fr_metrics:
        fr_annual_revenue = fr_metrics["annual"].get("total", 0)
    else:
        # Conservative estimate
        fr_annual_revenue = power_mw * 7 * 8760 * 0.95  # €7/MW/h * hours * availability

    if pzu_metrics and "annual" in pzu_metrics:
        pzu_annual_revenue = pzu_metrics["annual"].get("total", 0)
    else:
        # Conservative estimate based on power rating
        pzu_annual_revenue = power_mw * 1.8 * 320 * 100 * 0.90  # cycles * days * spread * efficiency

    total_annual_revenue = fr_annual_revenue + pzu_annual_revenue
    roi = (total_annual_revenue / investment_eur * 100) if investment_eur > 0 else 0
    payback = investment_eur / total_annual_revenue if total_annual_revenue > 0 else 0

    # Display key metrics preview
    st.markdown("#### 💡 Key Investment Metrics")

    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric(
            "Total Investment",
            f"€{investment_eur/1_000_000:.1f}M",
            help="Total project investment"
        )

    with metric_cols[1]:
        st.metric(
            "Annual Revenue",
            f"€{total_annual_revenue/1_000_000:.2f}M",
            help="Combined PZU + FR revenue"
        )

    with metric_cols[2]:
        st.metric(
            "ROI",
            f"{roi:.1f}%",
            help="Annual return on investment"
        )

    with metric_cols[3]:
        st.metric(
            "Payback",
            f"{payback:.1f} years",
            help="Investment payback period"
        )

    st.markdown("")

    # Design preview
    st.markdown("#### 🎨 Professional Bloomberg/Tech Design")
    st.markdown("""
    - **Color Scheme**: Orange accent (#FF7800) + Dark gray (#1E1E1E) + Clean backgrounds
    - **Typography**: Modern, clean fonts with clear hierarchy
    - **Data Visualization**: Metric cards with key performance indicators
    - **Layout**: Clean, professional slides optimized for investor presentations
    """)

    st.markdown("")

    # Generate button
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])

    with col_btn2:
        if st.button("🚀 Generate PowerPoint Presentation", type="primary", use_container_width=True):
            with st.spinner("Creating professional PowerPoint presentation... This may take 10-15 seconds"):
                try:
                    # Prepare metrics for PowerPoint
                    pzu_metrics_ppt = {}
                    if pzu_metrics:
                        if "annual" in pzu_metrics:
                            pzu_metrics_ppt["avg_monthly_profit"] = pzu_metrics["annual"].get("total", 0) / 12
                        if "daily_history" in pzu_metrics:
                            # Calculate success rate from daily data if available
                            daily_data = pzu_metrics["daily_history"]
                            if daily_data:
                                profitable_days = sum(1 for d in daily_data if d.get("daily_profit_eur", 0) > 0)
                                total_days = len(daily_data)
                                pzu_metrics_ppt["overall_success_rate"] = (profitable_days / total_days * 100) if total_days > 0 else 85

                    fr_metrics_ppt = {}
                    if fr_metrics:
                        if "annual" in fr_metrics:
                            fr_metrics_ppt["annual_revenue"] = fr_metrics["annual"].get("total", 0)

                    # Calculate equity percentage
                    equity_percent = (equity_eur / investment_eur * 100) if investment_eur > 0 else 50

                    # Generate PowerPoint in memory
                    output_path = generate_business_plan_pptx(
                        pzu_metrics=pzu_metrics_ppt if pzu_metrics_ppt else None,
                        fr_metrics=fr_metrics_ppt if fr_metrics_ppt else None,
                        battery_power_mw=power_mw,
                        battery_capacity_mwh=capacity_mwh,
                        efficiency=0.90,  # 90% round-trip efficiency
                        investment_eur=investment_eur,
                        equity_percent=equity_percent,
                        output_path=f"business_plan_{capacity_mwh:.0f}MWh.pptx"
                    )

                    # Read the generated file
                    with open(output_path, "rb") as f:
                        pptx_data = f.read()

                    # Offer download
                    st.download_button(
                        label="⬇️ Download PowerPoint Presentation",
                        data=pptx_data,
                        file_name=f"BESS_Investment_Pitch_{capacity_mwh:.0f}MWh.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                    )

                    st.success(f"✅ PowerPoint presentation generated successfully! ({capacity_mwh:.0f} MWh project)")

                    # Show presentation stats
                    stats_cols = st.columns(3)
                    with stats_cols[0]:
                        st.info("📄 **12 Professional Slides**")
                    with stats_cols[1]:
                        st.info("🎨 **Bloomberg Design**")
                    with stats_cols[2]:
                        st.info("📊 **Real Data from Simulators**")

                except Exception as e:
                    st.error(f"❌ Error generating PowerPoint: {e}")
                    import traceback
                    st.code(traceback.format_exc())