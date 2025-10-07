"""
AI Battery Assistant - Intelligent Q&A for Battery Analytics Platform
Provides context-aware answers about battery data, market analysis, and simulations
"""

from pathlib import Path
import pandas as pd
import streamlit as st
from typing import Dict, Any, Optional

def get_data_context(cfg: dict) -> Dict[str, Any]:
    """Gather all available data context for AI assistant"""

    context = {
        "data_sources": {},
        "market_stats": {},
        "configuration": {}
    }

    project_root = Path(__file__).parent.parent.parent.parent

    # Load FR (DAMAS) data
    try:
        fr_path = project_root / "data" / "imbalance_history.csv"
        if fr_path.exists():
            fr_df = pd.read_csv(fr_path)
            context["data_sources"]["fr_damas"] = {
                "rows": len(fr_df),
                "date_range": f"{fr_df['date'].min()} to {fr_df['date'].max()}",
                "has_activation_data": all(col in fr_df.columns for col in
                    ['afrr_up_activated_mwh', 'afrr_down_activated_mwh']),
                "sample_stats": {
                    "afrr_up_mean": fr_df['afrr_up_activated_mwh'].mean() if 'afrr_up_activated_mwh' in fr_df.columns else 0,
                    "afrr_down_mean": fr_df['afrr_down_activated_mwh'].mean() if 'afrr_down_activated_mwh' in fr_df.columns else 0,
                }
            }
    except Exception as e:
        context["data_sources"]["fr_damas"] = {"error": str(e)}

    # Load PZU data
    try:
        pzu_path = project_root / "data" / "pzu_history_3y.csv"
        if pzu_path.exists():
            pzu_df = pd.read_csv(pzu_path)
            context["data_sources"]["pzu"] = {
                "rows": len(pzu_df),
                "date_range": f"{pzu_df['date'].min() if 'date' in pzu_df.columns else 'N/A'} to {pzu_df['date'].max() if 'date' in pzu_df.columns else 'N/A'}",
            }
    except Exception as e:
        context["data_sources"]["pzu"] = {"error": str(e)}

    # Configuration info
    context["configuration"] = {
        "fr_products": cfg.get("fr_products", {}),
        "pzu_config": cfg.get("strategy", {}).get("pzu", {}),
    }

    return context


def build_context_summary(context: Dict[str, Any]) -> str:
    """Build a text summary of available data for AI context"""

    summary_parts = ["# Battery Analytics Platform Data Context\n"]

    # FR Data
    if "fr_damas" in context["data_sources"]:
        fr = context["data_sources"]["fr_damas"]
        if "error" not in fr:
            summary_parts.append(f"""
## Frequency Regulation (FR) Data
- **DAMAS Activation Data**: {fr['rows']:,} rows
- **Date Range**: {fr['date_range']}
- **Activation Columns**: {'✅ Present' if fr['has_activation_data'] else '❌ Missing'}
- **aFRR UP Mean**: {fr['sample_stats']['afrr_up_mean']:.2f} MWh
- **aFRR DOWN Mean**: {fr['sample_stats']['afrr_down_mean']:.2f} MWh
""")

    # PZU Data
    if "pzu" in context["data_sources"]:
        pzu = context["data_sources"]["pzu"]
        if "error" not in pzu:
            summary_parts.append(f"""
## PZU Arbitrage Data
- **Historical Data**: {pzu['rows']:,} rows
- **Date Range**: {pzu['date_range']}
""")

    return "\n".join(summary_parts)


def answer_question(question: str, context: Dict[str, Any]) -> str:
    """
    Answer battery-related questions using available data context
    This is a rule-based system - for production, integrate with OpenAI/Anthropic API
    """

    question_lower = question.lower()

    # FR-related questions
    if any(word in question_lower for word in ['fr', 'frequency', 'regulation', 'afrr', 'mfrr', 'activation']):
        fr_data = context["data_sources"].get("fr_damas", {})

        if "date" in question_lower or "range" in question_lower:
            return f"📊 **FR Data Coverage**: The platform has DAMAS activation data from **{fr_data.get('date_range', 'N/A')}** with **{fr_data.get('rows', 0):,}** 15-minute data points."

        if "activation" in question_lower:
            stats = fr_data.get('sample_stats', {})
            return f"""📈 **FR Activation Statistics**:
- **aFRR UP**: Average {stats.get('afrr_up_mean', 0):.2f} MWh per activation
- **aFRR DOWN**: Average {stats.get('afrr_down_mean', 0):.2f} MWh per activation
- **Data Accuracy**: 90-95% (using real TSO dispatch signals from DAMAS)
"""

        if "revenue" in question_lower:
            return """💰 **FR Revenue Components**:
1. **Capacity Revenue** (€/MW/h): Paid for availability regardless of activation
2. **Activation Revenue** (€/MWh): Paid for actual energy delivered when called upon

**Formula**: Total Revenue = (Contracted MW × Hours × Capacity Price) + (Activation Energy × Activation Price)

**Typical Split**: 20-40% capacity, 60-80% activation (varies by month and market conditions)
"""

    # PZU-related questions
    if any(word in question_lower for word in ['pzu', 'arbitrage', 'trading']):
        pzu_data = context["data_sources"].get("pzu", {})

        if "date" in question_lower or "range" in question_lower:
            return f"📊 **PZU Data Coverage**: Historical arbitrage data from **{pzu_data.get('date_range', 'N/A')}** with **{pzu_data.get('rows', 0):,}** hourly price points."

        if "strategy" in question_lower or "how" in question_lower:
            return """⚡ **PZU Arbitrage Strategy**:
1. **Buy Low**: Purchase energy during off-peak hours (low prices)
2. **Charge Battery**: Store energy with ~90% round-trip efficiency
3. **Sell High**: Discharge during peak hours (high prices)
4. **Profit**: Spread between buy/sell prices minus efficiency losses

**Key Metrics**:
- Best hours identified using historical price patterns
- SOC (State of Charge) constraints: 10-90%
- Typical daily cycles: 1-2 (prevents battery degradation)
"""

    # Investment questions
    if any(word in question_lower for word in ['invest', 'roi', 'payback', 'financing']):
        return """💼 **Investment Analysis**:

**Metrics Tracked**:
- **Payback Period**: Time to recover initial investment from net profits
- **ROI**: Total return over project lifetime
- **NPV**: Net Present Value considering time value of money
- **IRR**: Internal Rate of Return

**Financing Structure**:
- **Total Investment**: Equipment + installation + development costs
- **Debt Financing**: Typically 70-80% @ 5-7% annual interest
- **Equity**: Remaining 20-30%
- **Loan Term**: Usually 7-10 years

**Cashflow Components**:
- Revenue (FR capacity + activation OR PZU trading)
- Operating Costs (maintenance, insurance, etc.)
- Debt Service (monthly principal + interest payments)
- Net Profit (revenue - costs - debt)
"""

    # Data quality questions
    if any(word in question_lower for word in ['accuracy', 'quality', 'reliable', 'damas']):
        return """✅ **Data Quality & Accuracy**:

**DAMAS Activation Data** (Frequency Regulation):
- **Source**: Romanian TSO (Transelectrica) official dispatch records
- **Accuracy**: 90-95% vs settlement data
- **Coverage**: Real 15-minute activation volumes and marginal prices
- **Use Case**: High-accuracy FR revenue forecasting

**Price-Threshold Proxy Method** (Legacy/Fallback):
- **Source**: Imbalance price correlations
- **Accuracy**: ±25-35% (estimation only)
- **Use Case**: When DAMAS data unavailable
- **Limitation**: Cannot account for merit-order dispatch logic

**PZU Historical Data**:
- **Source**: OPCOM day-ahead market prices
- **Accuracy**: 100% (actual settled prices)
- **Coverage**: Hourly spot prices for 3+ years
"""

    # Battery technical questions
    if any(word in question_lower for word in ['battery', 'capacity', 'power', 'mw', 'mwh', 'soc']):
        return """🔋 **Battery Technical Specifications**:

**Typical Configuration**:
- **Power**: 25 MW (max charge/discharge rate)
- **Capacity**: 50 MWh (energy storage)
- **Duration**: 2 hours (50 MWh ÷ 25 MW)
- **Round-Trip Efficiency**: 90% (10% losses)
- **SOC Operating Range**: 10-90% (prevents degradation)

**Key Constraints**:
- **C-Rate**: Power ÷ Capacity = 0.5C (conservative, extends lifetime)
- **Depth of Discharge**: 80% (10% to 90% SOC)
- **Daily Cycles**: 1-2 (PZU) or continuous (FR standby)
- **Lifetime**: 10-15 years or 4,000-6,000 cycles

**SOC (State of Charge)**:
- Tracked in real-time during simulations
- Prevents over-charge (>90%) and over-discharge (<10%)
- Critical for realistic revenue modeling
"""

    # Default response
    return f"""🤖 I'm the Battery Analytics AI Assistant. I can help with:

**📊 Data & Analytics**:
- FR (Frequency Regulation) activation data and revenue
- PZU (Arbitrage) trading strategies and profitability
- Investment analysis, ROI, and payback calculations

**🔋 Battery Technology**:
- Technical specifications (power, capacity, efficiency)
- SOC management and operational constraints
- Degradation and lifetime considerations

**💰 Financial Modeling**:
- Revenue forecasting (capacity + activation)
- Cost analysis and debt financing
- Cashflow projections and sensitivity analysis

**❓ Your Question**: "{question}"

Try asking about specific topics like:
- "What is the FR revenue breakdown?"
- "How does PZU arbitrage work?"
- "What's the typical battery configuration?"
- "Explain the investment metrics"
"""


def render_battery_assistant(cfg: dict):
    """Render the AI Battery Assistant interface"""

    st.markdown('<div class="section-header">🤖 AI Battery Assistant</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="info-banner">
    Ask me anything about battery energy storage, market strategies, data analysis, or financial modeling!
    </div>
    """, unsafe_allow_html=True)

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Get data context
    context = get_data_context(cfg)

    # Display data context summary (collapsible)
    with st.expander("📚 Available Data Context", expanded=False):
        st.markdown(build_context_summary(context))

    # Chat interface
    st.markdown("### 💬 Chat")

    # Display chat history
    for i, message in enumerate(st.session_state.chat_history):
        if message["role"] == "user":
            st.markdown(f"""
            <div style="background: #e3f2fd; padding: 1rem; border-radius: 8px; margin: 0.5rem 0;">
                <strong>You:</strong> {message["content"]}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: #f5f5f5; padding: 1rem; border-radius: 8px; margin: 0.5rem 0;">
                <strong>🤖 Assistant:</strong><br>
                {message["content"]}
            </div>
            """, unsafe_allow_html=True)

    # Input area
    col1, col2 = st.columns([5, 1])

    with col1:
        user_question = st.text_input(
            "Ask a question:",
            placeholder="e.g., What is the FR activation revenue for January 2024?",
            key="user_question"
        )

    with col2:
        ask_button = st.button("Ask", type="primary", use_container_width=True)

    # Quick questions
    st.markdown("**Quick Questions:**")
    quick_cols = st.columns(4)

    quick_questions = [
        "What is FR revenue?",
        "How does PZU work?",
        "Show data coverage",
        "Explain ROI metrics"
    ]

    for i, quick_q in enumerate(quick_questions):
        with quick_cols[i]:
            if st.button(quick_q, key=f"quick_{i}", use_container_width=True):
                user_question = quick_q
                ask_button = True

    # Process question
    if ask_button and user_question:
        # Add user message to history
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_question
        })

        # Get AI response
        response = answer_question(user_question, context)

        # Add assistant response to history
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response
        })

        # Rerun to display new messages
        st.rerun()

    # Clear chat button
    if st.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

    # Example questions panel
    st.markdown("---")
    st.markdown("### 💡 Example Questions")

    examples_cols = st.columns(2)

    with examples_cols[0]:
        st.markdown("""
        **📊 Data & Analysis**
        - What is the FR data date range?
        - How accurate is the DAMAS data?
        - Show activation statistics
        - Explain data quality levels
        """)

    with examples_cols[1]:
        st.markdown("""
        **💰 Financial & Strategy**
        - What is the FR revenue breakdown?
        - How does PZU arbitrage work?
        - Explain investment metrics
        - What is the typical payback period?
        """)
