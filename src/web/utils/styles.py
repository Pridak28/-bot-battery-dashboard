"""
Professional styling utilities for Battery Analytics Platform
Provides centralized CSS injection and styling functions
"""

from pathlib import Path
import streamlit as st

def load_css():
    """Load the unified UI stylesheet."""
    css_path = Path(__file__).parent.parent / "assets" / "style.css"

    if css_path.exists():
        with open(css_path) as stylesheet:
            st.markdown(f"<style>{stylesheet.read()}</style>", unsafe_allow_html=True)
        return

    # Emergency fallback inline CSS if the file is missing
    st.markdown(
        """
        <style>
        :root {
            --brand-primary: #1e40af;
            --bg-main: #f8fafc;
            --text-primary: #111827;
        }
        .stApp { background-color: var(--bg-main) !important; }
        #MainMenu {visibility: hidden !important;}
        footer {visibility: hidden !important;}
        header {visibility: hidden !important;}
        * { font-family: 'Inter', sans-serif !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = ""):
    """Render professional page header"""
    subtitle_html = f'<p>{subtitle}</p>' if subtitle else ''

    st.markdown(f"""
        <div class="main-header">
            <h1>{title}</h1>
            {subtitle_html}
        </div>
    """, unsafe_allow_html=True)


def section_header(title: str):
    """Render professional section header"""
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str, delta: str = "", card_class: str = ""):
    """Render a single KPI card"""
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ''

    return f"""
    <div class="kpi-card {card_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {delta_html}
    </div>
    """


def kpi_grid(cards: list, columns: int = 4):
    """Render a grid of KPI cards"""
    cards_html = ''.join(cards)

    st.markdown(f"""
    <div class="grid-{columns}">
        {cards_html}
    </div>
    """, unsafe_allow_html=True)


def info_banner(message: str, banner_type: str = "info"):
    """Render styled info banner"""
    st.markdown(f"""
        <div class="{banner_type}-banner">
            {message}
        </div>
    """, unsafe_allow_html=True)


def data_card(title: str, content: str):
    """Render a data card with title and content"""
    st.markdown(f"""
        <div class="data-card">
            <div class="data-card-header">{title}</div>
            {content}
        </div>
    """, unsafe_allow_html=True)


def chart_container(title: str, chart_html: str):
    """Wrap chart in professional container"""
    st.markdown(f"""
        <div class="chart-container">
            <div class="chart-title">{title}</div>
            {chart_html}
        </div>
    """, unsafe_allow_html=True)


def sidebar_title(title: str):
    """Render sidebar title"""
    st.sidebar.markdown(f'<div class="sidebar-title">{title}</div>', unsafe_allow_html=True)


def executive_summary_section(kpi_cards_html: str):
    """Render executive summary with gradient background"""
    st.markdown(f"""
        <div class="executive-summary">
            <h2>Executive Summary</h2>
            <div class="grid-3">
                {kpi_cards_html}
            </div>
        </div>
    """, unsafe_allow_html=True)
