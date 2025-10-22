"""
Translation Module for Romanian/English Export Documents

Provides comprehensive translations for all financial model and business plan content
"""

from typing import Dict, Any

TRANSLATIONS = {
    "en": {
        # Excel Sheet Names
        "sheet_transaction": "1_Transaction Summary",
        "sheet_historical": "2_Historical Data",
        "sheet_cashflow": "3_Cashflow 15Y",
        "sheet_debt_coverage": "4_Debt Coverage",
        "sheet_returns": "5_Returns Analysis",
        "sheet_sensitivity": "6_Sensitivity",
        "sheet_benchmarks": "7_Market Benchmarks",
        "sheet_opex": "8_OPEX Detail",
        "sheet_revenue": "9_Revenue Model",
        "sheet_risks": "10_Risk Register",
        "sheet_macro": "11_Macro & FX",
        "sheet_comparables": "12_Comparables",
        "sheet_debt_schedule": "13_Debt Schedule",
        "sheet_technical": "14_Technical Specs",
        "sheet_timeline": "15_Timeline",

        # Common Terms
        "currency": "€",
        "project_name": "BATTERY ENERGY STORAGE SYSTEM",
        "transaction_summary": "TRANSACTION SUMMARY",
        "project_overview": "PROJECT OVERVIEW",
        "technology": "Technology",
        "energy_capacity": "Energy Capacity",
        "power_rating": "Power Rating",
        "storage_duration": "Storage Duration",
        "efficiency": "Round-Trip Efficiency",
        "lifetime": "Expected Lifetime",
        "location": "Location",
        "grid_connection": "Grid Connection",
        "target_cod": "Target COD",

        # Sources & Uses
        "sources_uses": "SOURCES & USES OF FUNDS",
        "uses": "USES",
        "battery_system": "Battery System",
        "pcs": "Power Conversion System",
        "balance_plant": "Balance of Plant",
        "grid_connection_cost": "Grid Connection",
        "development": "Development & Fees",
        "contingency": "Contingency",
        "total_uses": "Total Uses",
        "sources": "SOURCES",
        "senior_debt": "Senior Debt",
        "sponsor_equity": "Sponsor Equity",
        "total_sources": "Total Sources",

        # Debt Terms
        "debt_terms": "DEBT TERMS",
        "principal": "Principal Amount",
        "interest_rate": "Interest Rate (Fixed)",
        "tenor": "Tenor",
        "amortization": "Amortization",
        "security": "Security",
        "years": "years",
        "level_debt": "Level debt service (annuity)",
        "first_lien": "First lien on all project assets",

        # Key Assumptions
        "key_assumptions": "KEY ASSUMPTIONS",
        "base_revenue": "Base Case Revenue",
        "capacity_factor": "Capacity Factor",
        "opex_escalation": "OPEX Escalation",
        "revenue_escalation": "Revenue Escalation",
        "battery_aug": "Battery Augmentation",
        "tax_structure": "Tax Structure",

        # Financial Metrics
        "equity_irr": "Equity IRR",
        "min_dscr": "Min DSCR",
        "moic": "MOIC",
        "payback": "Payback",
        "annual_revenue": "Annual Revenue",
        "capacity_payments": "Capacity Payments",
        "activation_revenue": "Activation Revenue",
        "energy_costs": "Energy Costs",
        "gross_margin": "Gross Margin",
        "fixed_opex": "Fixed OPEX",
        "ebitda": "EBITDA",
        "debt_service": "Debt Service",
        "free_cashflow": "Free Cashflow",
        "net_profit": "Net Annual Profit",
        "annual_roi": "Annual ROI",

        # Business Plan Sections
        "executive_summary": "EXECUTIVE SUMMARY",
        "investment_highlights": "Investment Highlights",
        "business_model": "Business Model Overview",
        "financial_summary": "Financial Summary",
        "strategic_rationale": "Strategic Rationale",
        "project_overview_section": "PROJECT OVERVIEW",
        "market_analysis": "MARKET ANALYSIS",
        "technical_specs": "TECHNICAL SPECIFICATIONS",
        "financial_analysis": "FINANCIAL ANALYSIS & PROJECTIONS",
        "risk_analysis": "RISK ANALYSIS & MITIGATION",
        "regulatory": "REGULATORY & COMPLIANCE",
        "timeline": "IMPLEMENTATION TIMELINE",
        "management": "MANAGEMENT TEAM & GOVERNANCE",
        "conclusions": "CONCLUSIONS & RECOMMENDATIONS",

        # FR/PZU
        "fr_strategy": "Frequency Regulation Strategy (Primary Business Case)",
        "pzu_strategy": "Energy Arbitrage Strategy (Alternative Business Case)",
        "fr_market": "FREQUENCY REGULATION MARKET (ROMANIA)",
        "pzu_market": "ENERGY ARBITRAGE MARKET (PZU)",

        # Notes
        "perfect_for": "Perfect for: JP Morgan, Goldman Sachs, Citi, Morgan Stanley presentations | Senior debt syndications | Institutional equity investors",
        "estimated": "estimated",
        "actual_data": "Actual historical data from simulators",
    },

    "ro": {
        # Excel Sheet Names
        "sheet_transaction": "1_Rezumat Tranzacție",
        "sheet_historical": "2_Date Istorice",
        "sheet_cashflow": "3_Flux Numerar 15A",
        "sheet_debt_coverage": "4_Acoperire Datorie",
        "sheet_returns": "5_Analiză Randamente",
        "sheet_sensitivity": "6_Sensibilitate",
        "sheet_benchmarks": "7_Repere Piață",
        "sheet_opex": "8_Detalii OPEX",
        "sheet_revenue": "9_Model Venituri",
        "sheet_risks": "10_Registru Riscuri",
        "sheet_macro": "11_Macro & Valutar",
        "sheet_comparables": "12_Comparabile",
        "sheet_debt_schedule": "13_Grafic Datorie",
        "sheet_technical": "14_Specificații Tehnice",
        "sheet_timeline": "15_Cronologie",

        # Common Terms
        "currency": "€",
        "project_name": "SISTEM DE STOCARE ENERGIE ÎN BATERII",
        "transaction_summary": "REZUMAT TRANZACȚIE",
        "project_overview": "PREZENTARE GENERALĂ PROIECT",
        "technology": "Tehnologie",
        "energy_capacity": "Capacitate Energetică",
        "power_rating": "Putere Nominală",
        "storage_duration": "Durată Stocare",
        "efficiency": "Eficiență Round-Trip",
        "lifetime": "Durată de Viață Estimată",
        "location": "Locație",
        "grid_connection": "Conexiune la Rețea",
        "target_cod": "Data Țintă Operare Comercială",

        # Sources & Uses
        "sources_uses": "SURSE ȘI UTILIZĂRI DE FONDURI",
        "uses": "UTILIZĂRI",
        "battery_system": "Sistem Baterii",
        "pcs": "Sistem Conversie Putere",
        "balance_plant": "Echipamente Auxiliare",
        "grid_connection_cost": "Conexiune la Rețea",
        "development": "Dezvoltare & Taxe",
        "contingency": "Rezervă Contingență",
        "total_uses": "Total Utilizări",
        "sources": "SURSE",
        "senior_debt": "Datorie Senior",
        "sponsor_equity": "Capital Sponsor",
        "total_sources": "Total Surse",

        # Debt Terms
        "debt_terms": "TERMENI DATORIE",
        "principal": "Sumă Principală",
        "interest_rate": "Rată Dobândă (Fixă)",
        "tenor": "Maturitate",
        "amortization": "Amortizare",
        "security": "Garanție",
        "years": "ani",
        "level_debt": "Serviciu datorie nivelat (anuitate)",
        "first_lien": "Primul gaj pe toate activele proiectului",

        # Key Assumptions
        "key_assumptions": "IPOTEZE CHEIE",
        "base_revenue": "Venituri Caz de Bază",
        "capacity_factor": "Factor Capacitate",
        "opex_escalation": "Escaladare OPEX",
        "revenue_escalation": "Escaladare Venituri",
        "battery_aug": "Augmentare Baterie",
        "tax_structure": "Structură Fiscală",

        # Financial Metrics
        "equity_irr": "IRR Capital",
        "min_dscr": "DSCR Minim",
        "moic": "MOIC",
        "payback": "Recuperare",
        "annual_revenue": "Venituri Anuale",
        "capacity_payments": "Plăți Capacitate",
        "activation_revenue": "Venituri Activare",
        "energy_costs": "Costuri Energie",
        "gross_margin": "Marjă Brută",
        "fixed_opex": "OPEX Fix",
        "ebitda": "EBITDA",
        "debt_service": "Serviciu Datorie",
        "free_cashflow": "Flux Numerar Liber",
        "net_profit": "Profit Net Anual",
        "annual_roi": "ROI Anual",

        # Business Plan Sections
        "executive_summary": "REZUMAT EXECUTIV",
        "investment_highlights": "Puncte Forte Investiție",
        "business_model": "Prezentare Model de Afaceri",
        "financial_summary": "Rezumat Financiar",
        "strategic_rationale": "Rațiune Strategică",
        "project_overview_section": "PREZENTARE GENERALĂ PROIECT",
        "market_analysis": "ANALIZĂ DE PIAȚĂ",
        "technical_specs": "SPECIFICAȚII TEHNICE",
        "financial_analysis": "ANALIZĂ FINANCIARĂ ȘI PROIECȚII",
        "risk_analysis": "ANALIZĂ ȘI MITIGARE RISCURI",
        "regulatory": "REGLEMENTARE ȘI CONFORMITATE",
        "timeline": "CRONOLOGIE IMPLEMENTARE",
        "management": "ECHIPĂ MANAGEMENT ȘI GUVERNANȚĂ",
        "conclusions": "CONCLUZII ȘI RECOMANDĂRI",

        # FR/PZU
        "fr_strategy": "Strategie Reglare Frecvență (Caz de Afaceri Principal)",
        "pzu_strategy": "Strategie Arbitraj Energetic (Caz de Afaceri Alternativ)",
        "fr_market": "PIAȚA REGLĂRII FRECVENȚEI (ROMÂNIA)",
        "pzu_market": "PIAȚA ARBITRAJULUI ENERGETIC (PZU)",

        # Notes
        "perfect_for": "Perfect pentru: JP Morgan, Goldman Sachs, Citi, Morgan Stanley | Sindicări datorie senior | Investitori instituționali",
        "estimated": "estimat",
        "actual_data": "Date istorice reale din simulatoare",
    }
}

def get_text(key: str, language: str = "en") -> str:
    """Get translated text for a given key"""
    return TRANSLATIONS.get(language, TRANSLATIONS["en"]).get(key, key)

def format_currency(value: float, language: str = "en") -> str:
    """Format currency with proper locale"""
    if language == "ro":
        # Romanian format: 1.234.567,89 EUR
        if value >= 0:
            return f"{value:,.0f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            return f"({abs(value):,.0f} EUR)".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        # English format: €1,234,567
        if value >= 0:
            return f"€{value:,.0f}"
        else:
            return f"(€{abs(value):,.0f})"

def get_language_name(code: str) -> str:
    """Get language display name"""
    names = {
        "en": "English",
        "ro": "Română"
    }
    return names.get(code, code)
