from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from src.web.ai import call_google_text, get_google_api_key


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


def render_ai_insights() -> None:
    """Render AI insights tab."""
    section_title = "AI Insights (Beta)"
    st.header(section_title)
    st.caption(
        "This assistant summarises the latest PZU, Frequency Regulation and financing analytics. "
        "Run the individual modules first so the session state contains fresh data."
    )

    default_question = (
        "Provide an operational summary of the battery portfolio, including profitability, debt coverage, "
        "and any risks or opportunities you identify."
    )
    question = st.text_area("AI question", value=default_question, height=120)

    try:
        # Test for key presence before the user hits the button so we can surface a clear warning.
        get_google_api_key()
    except RuntimeError as exc:
        st.warning(str(exc))
        st.stop()

    if st.button("Generate AI Insight", use_container_width=True):
        prompt = _compose_prompt(question)
        with st.spinner("Contacting AI service..."):
            try:
                answer = call_google_text(prompt)
            except Exception as exc:  # noqa: BLE001
                st.error(f"AI request failed: {exc}")
            else:
                st.markdown("---")
                st.markdown("#### AI Response")
                st.markdown(answer)

    with st.expander("Prompt context preview", expanded=False):
        st.code(_compose_prompt(question), language="markdown")
