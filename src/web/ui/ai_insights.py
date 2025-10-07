"""
AI Insights - Intelligent Battery Analytics Assistant with Full Data Access
Uses Google Gemini 2.5 Flash with comprehensive platform data context
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from pathlib import Path
import json

import pandas as pd
import streamlit as st

from src.web.ai import call_google_text, get_google_api_key
from src.web.ai.context_builder import BatteryDataContext


def _build_pzu_summary() -> Optional[str]:
    metrics = st.session_state.get("pzu_market_metrics")
    if not metrics:
        return None

    daily_history = metrics.get("daily_history")
    if isinstance(daily_history, list):
        df = pd.DataFrame(daily_history)
    elif isinstance(daily_history, pd.DataFrame):
        df = daily_history.copy()
    else:
        return None

    if df.empty or "daily_profit_eur" not in df.columns:
        return None

    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    total_profit = float(df["daily_profit_eur"].sum())
    avg_profit = float(df["daily_profit_eur"].mean())

    buy_col = next((c for c in df.columns if "buy" in c and "price" in c), None)
    sell_col = next((c for c in df.columns if "sell" in c and "price" in c), None)

    buy_price = float(df[buy_col].mean()) if buy_col else None
    sell_price = float(df[sell_col].mean()) if sell_col else None

    start_date = df["date"].min().strftime("%Y-%m-%d")
    end_date = df["date"].max().strftime("%Y-%m-%d")

    lines: List[str] = [
        f"PZU window: {start_date} → {end_date}",
        f"Total profit: {total_profit:,.0f} EUR",
        f"Average daily profit: {avg_profit:,.0f} EUR",
    ]
    if buy_price is not None and sell_price is not None:
        spread = sell_price - buy_price
        lines.append(f"Average buy price: {buy_price:,.2f} EUR/MWh")
        lines.append(f"Average sell price: {sell_price:,.2f} EUR/MWh")
        lines.append(f"Average spread: {spread:,.2f} EUR/MWh")

    return "\n".join(lines)


def _build_fr_summary() -> Optional[str]:
    metrics = st.session_state.get("fr_market_metrics")
    if not metrics or not isinstance(metrics, dict):
        return None

    combined_totals = metrics.get("combined_totals") or {}
    months = metrics.get("combined_monthly") or metrics.get("months")

    lines: List[str] = []
    if combined_totals:
        months_count = combined_totals.get("months")
        if months_count:
            lines.append(f"FR coverage: {months_count} months")
        cap_rev = combined_totals.get("capacity_revenue_eur")
        act_rev = combined_totals.get("activation_revenue_eur")
        energy_cost = combined_totals.get("energy_cost_eur")
        if cap_rev is not None:
            lines.append(f"Capacity revenue: {cap_rev:,.0f} EUR")
        if act_rev is not None:
            lines.append(f"Activation revenue: {act_rev:,.0f} EUR")
        if energy_cost is not None:
            lines.append(f"Energy cost: {energy_cost:,.0f} EUR")
    if months and isinstance(months, list):
        df = pd.DataFrame(months)
        if not df.empty and "activation_energy_mwh" in df.columns:
            lines.append(
                f"Average activation energy: {df['activation_energy_mwh'].fillna(0.0).mean():,.1f} MWh/month"
            )
    return "\n".join(lines) if lines else None


def _compose_prompt(user_question: str) -> str:
    sections: List[str] = []

    pzu_section = _build_pzu_summary()
    if pzu_section:
        sections.append("PZU Horizons Summary:\n" + pzu_section)

    fr_section = _build_fr_summary()
    if fr_section:
        sections.append("Frequency Regulation Summary:\n" + fr_section)

    if not sections:
        sections.append("No analytics data is currently available in the session.")

    base_prompt = (
        "You are the Battery Analytics AI advisor. Use the following context to answer.\n\n"
        + "\n\n".join(sections)
        + "\n\nQuestion: "
        + user_question.strip()
        + "\n\nAnswer with a concise analysis that references the provided numbers. "
        "If information is missing, explain what else is required."
    )
    return base_prompt


def render_ai_insights(cfg: dict = None) -> None:
    """Render AI insights tab with full data access."""
    section_title = "AI Insights Assistant"
    st.header(section_title)
    st.caption(
        "This assistant has full access to FR/DAMAS activation data, PZU prices, revenue calculations, "
        "and investment metrics. It uses Google Gemini 2.5 Flash for intelligent analysis."
    )

    # Initialize session state
    if "ai_chat_history" not in st.session_state:
        st.session_state.ai_chat_history = []

    # Check for API key
    api_key_available = True
    try:
        get_google_api_key()
    except RuntimeError as exc:
        api_key_available = False
        st.error(
            f"{exc}\n\nAdd a `.streamlit/secrets.toml` with `GOOGLE_API_KEY = \"...\"` "
            "or export the `GOOGLE_API_KEY` environment variable to enable the assistant."
        )

    # Build comprehensive data context
    with st.spinner("Loading all platform data..."):
        context_builder = BatteryDataContext()
        data_context = context_builder.get_full_context(cfg)
        context_prompt = context_builder.format_for_llm(data_context)

    # Display data overview metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if data_context["fr_data"]["available"]:
            st.metric("FR Data Points", f"{data_context['fr_data']['total_rows']:,}",
                     data_context["fr_data"]["data_accuracy"])
        else:
            st.metric("FR Data", "Not Available", "X")

    with col2:
        if data_context["pzu_data"]["available"]:
            st.metric("PZU Data Points", f"{data_context['pzu_data']['total_rows']:,}", "Historical")
        else:
            st.metric("PZU Data", "Not Available", "X")

    with col3:
        if data_context["fr_data"].get("activation_stats"):
            rate = data_context["fr_data"]["activation_stats"]["afrr_up"]["activation_rate"]
            st.metric("aFRR Activation", f"{rate:.1%}", "of time slots")
        else:
            st.metric("Activation Rate", "N/A", "")

    with col4:
        quality = data_context["data_quality"]["overall_quality"]
        st.metric("Data Quality", quality, "Good" if quality == "Excellent" else "Check")

    # Display data context
    with st.expander("Available Data Context", expanded=False):
        st.code(json.dumps(data_context, indent=2, default=str)[:3000] + "...", language="json")

    # Chat history display in scrollable container
    if st.session_state.ai_chat_history:
        st.subheader("Conversation History")
        # Create a scrollable container for chat history
        chat_container = st.container(height=400)  # Fixed height for scrolling
        with chat_container:
            for message in st.session_state.ai_chat_history:
                if message["role"] == "user":
                    st.markdown(f"**You:** {message['content']}")
                    st.divider()
                else:
                    # Display AI response in a text area for better readability
                    st.markdown("**AI Response:**")
                    st.text_area(
                        label="AI Response",
                        value=message['content'],
                        height=200,
                        disabled=True,
                        label_visibility="collapsed"
                    )
                    st.divider()

    # Question input
    question = st.text_area(
        "Ask anything about battery data:",
        value="What's the FR activation revenue for January 2024? Compare it with PZU potential.",
        height=80
    )

    # Example questions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("FR Revenue Analysis"):
            question = "Analyze FR revenue breakdown for 2024 with capacity vs activation split"
    with col2:
        if st.button("PZU vs FR Comparison"):
            question = "Compare annual revenue potential between FR and PZU strategies"

    if st.button("Generate AI Insight", disabled=not api_key_available, type="primary", use_container_width=True):
        if question:
            # Add to chat history
            st.session_state.ai_chat_history.append({"role": "user", "content": question})

            # Create comprehensive prompt
            full_prompt = f"""{context_prompt}

User Question: {question}

Instructions:
1. Use specific numbers from the data context above
2. Show calculations where relevant
3. Cite data sources (FR/DAMAS, PZU, etc.)
4. Be precise and data-driven
5. Format with clear sections"""

            with st.spinner("Analyzing data with Gemini 2.5 Flash..."):
                try:
                    answer = call_google_text(prompt=full_prompt, temperature=0.3, max_tokens=2000)
                    st.session_state.ai_chat_history.append({"role": "assistant", "content": answer})
                    st.rerun()
                except Exception as exc:
                    st.error(f"AI request failed: {exc}")

    # Clear chat
    if st.button("Clear Chat History"):
        st.session_state.ai_chat_history = []
        st.rerun()

    # Show prompt preview
    with st.expander("Full Data Context & Prompt", expanded=False):
        st.code(context_prompt, language="markdown")
