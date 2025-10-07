"""Streamlit view rendering helpers - CLEAN VERSION"""

from .pzu_horizons import render_pzu_horizons
from .market_comparison import render_historical_market_comparison
from .fr_simulator import render_frequency_regulation_simulator
from .investment import render_investment_financing_analysis
from .battery_assistant import render_battery_assistant
from .ai_insights import render_ai_insights

__all__ = [
    "render_pzu_horizons",
    "render_historical_market_comparison",
    "render_frequency_regulation_simulator",
    "render_investment_financing_analysis",
    "render_battery_assistant",
    "render_ai_insights",
]
