"""
Professional Business Explanation Report Generator

Creates comprehensive business overview documents for:
- Bank presentations
- Investor pitch decks
- Regulatory submissions
- Partnership proposals

Designed for a SINGLE 15 MWh battery project (not 3 projects)
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Dict, List, Optional, Any

import pandas as pd
import streamlit as st


def generate_business_overview_excel(
    project_name: str,
    capacity_mwh: float,
    power_mw: float,
    investment_eur: float,
    equity_eur: float,
    debt_eur: float,
    loan_term_years: int,
    interest_rate: float,
    fr_metrics: Optional[Dict[str, Any]],
    pzu_metrics: Optional[Dict[str, Any]],
    fr_opex_annual: float,
    pzu_opex_annual: float,
) -> bytes:
    """
    Generate comprehensive business overview Excel report

    For a SINGLE battery project (e.g., 15 MWh)
    """

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        # ========================================================================
        # SHEET 1: EXECUTIVE SUMMARY
        # ========================================================================
        exec_summary = [
            ["BATTERY ENERGY STORAGE SYSTEM", ""],
            ["PROFESSIONAL BUSINESS OVERVIEW", ""],
            ["", ""],
            ["Report Date", datetime.now().strftime("%Y-%m-%d")],
            ["Project Name", project_name],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["1. PROJECT OVERVIEW", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Technology", "Lithium-Ion Battery Energy Storage System (BESS)"],
            ["Energy Capacity", f"{capacity_mwh:.1f} MWh"],
            ["Power Rating", f"{power_mw:.1f} MW"],
            ["Storage Duration", f"{capacity_mwh/power_mw:.1f} hours"],
            ["Round-Trip Efficiency", "90%"],
            ["Expected Lifetime", "15 years / 6,000 cycles"],
            ["", ""],
            ["Location", "Romania"],
            ["Grid Connection", "High Voltage (110-220 kV)"],
            ["Market Access", "OPCOM (Day-Ahead) + Transelectrica (Ancillary Services)"],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["2. BUSINESS MODEL", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["The battery can operate in TWO distinct revenue strategies:", ""],
            ["", ""],
            ["Strategy A: Frequency Regulation (FR)", ""],
            ["  • Provides ancillary services to TSO (Transelectrica)", ""],
            ["  • Revenue from capacity payments (€/MW/h for availability)", ""],
            ["  • Additional activation revenue when dispatched", ""],
            ["  • Helps stabilize grid frequency (50 Hz ± 0.2 Hz)", ""],
            ["  • Three products: FCR, aFRR, mFRR", ""],
            ["", ""],
            ["Strategy B: Energy Arbitrage (PZU)", ""],
            ["  • Buy electricity during low-price hours (night/off-peak)", ""],
            ["  • Sell electricity during high-price hours (day/peak)", ""],
            ["  • Profit from day-ahead market price spreads", ""],
            ["  • Typical cycle: 1-2 charge/discharge per day", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["3. INVESTMENT STRUCTURE", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Total Capital Investment", f"€{investment_eur:,.0f}"],
            ["", ""],
            ["Financing Structure:", ""],
            ["  • Equity (30%)", f"€{equity_eur:,.0f}"],
            ["  • Senior Debt (70%)", f"€{debt_eur:,.0f}"],
            ["", ""],
            ["Debt Terms:", ""],
            ["  • Loan Amount", f"€{debt_eur:,.0f}"],
            ["  • Interest Rate", f"{interest_rate*100:.2f}% per annum"],
            ["  • Loan Term", f"{loan_term_years} years"],
            ["  • Repayment", "Equal monthly installments (amortizing)"],
            ["", ""],
            ["Investment Breakdown:", ""],
            ["  • Battery System", f"€{investment_eur*0.60:,.0f} (60%)"],
            ["  • Power Electronics & Inverters", f"€{investment_eur*0.20:,.0f} (20%)"],
            ["  • Engineering & Installation", f"€{investment_eur*0.12:,.0f} (12%)"],
            ["  • Grid Connection & Permits", f"€{investment_eur*0.08:,.0f} (8%)"],
            ["", ""],
        ]

        # Add FR financial summary if available
        if fr_metrics and "annual" in fr_metrics:
            fr_annual = fr_metrics["annual"]
            exec_summary.extend([
                ["═══════════════════════════════════════════════════════════", ""],
                ["4. FINANCIAL PERFORMANCE - FREQUENCY REGULATION", ""],
                ["═══════════════════════════════════════════════════════════", ""],
                ["", ""],
                ["Annual Revenue (avg)", f"€{fr_annual.get('total', 0):,.0f}"],
                ["  • Capacity Payments", f"€{fr_annual.get('capacity', 0):,.0f}"],
                ["  • Activation Revenue", f"€{fr_annual.get('activation', 0):,.0f}"],
                ["", ""],
                ["Annual Costs", ""],
                ["  • Energy Cost (recharging)", f"€{fr_annual.get('energy_cost', 0):,.0f}"],
                ["  • Operating Expenses", f"€{fr_opex_annual:,.0f}"],
                ["  • Debt Service", f"€{fr_annual.get('debt', 0):,.0f}"],
                ["", ""],
                ["Net Annual Profit", f"€{fr_annual.get('net', 0):,.0f}"],
                ["Annual ROI", f"{(fr_annual.get('net', 0) / investment_eur * 100) if investment_eur > 0 else 0:.1f}%"],
                ["", ""],
            ])

        # Add PZU financial summary if available
        if pzu_metrics and "annual" in pzu_metrics:
            pzu_annual = pzu_metrics["annual"]
            exec_summary.extend([
                ["═══════════════════════════════════════════════════════════", ""],
                ["5. FINANCIAL PERFORMANCE - ENERGY ARBITRAGE (PZU)", ""],
                ["═══════════════════════════════════════════════════════════", ""],
                ["", ""],
                ["Annual Gross Profit (avg)", f"€{pzu_annual.get('total', 0):,.0f}"],
                ["", ""],
                ["Annual Costs", ""],
                ["  • Operating Expenses", f"€{pzu_opex_annual:,.0f}"],
                ["  • Debt Service", f"€{pzu_annual.get('debt', 0):,.0f}"],
                ["", ""],
                ["Net Annual Profit", f"€{pzu_annual.get('net', 0):,.0f}"],
                ["Annual ROI", f"{(pzu_annual.get('net', 0) / investment_eur * 100) if investment_eur > 0 else 0:.1f}%"],
                ["", ""],
            ])

        # Convert to DataFrame
        exec_df = pd.DataFrame(exec_summary, columns=["Section", "Value"])
        exec_df.to_excel(writer, sheet_name="Executive Summary", index=False)

        # ========================================================================
        # SHEET 2: MARKET CONTEXT & OPPORTUNITY
        # ========================================================================
        market_context = [
            ["ROMANIAN ENERGY MARKET CONTEXT", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["MARKET OVERVIEW", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Market Operator", "OPCOM (Day-Ahead & Intraday Markets)"],
            ["TSO (System Operator)", "Transelectrica (Ancillary Services)"],
            ["Regulatory Framework", "ANRE (Romanian Energy Regulator)"],
            ["EU Compliance", "Clean Energy Package, Electricity Regulation 2019/943"],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["FREQUENCY REGULATION MARKET", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Market Structure:", ""],
            ["", ""],
            ["1. FCR (Frequency Containment Reserve)", ""],
            ["   • Response Time: < 30 seconds", ""],
            ["   • Purpose: Immediate frequency stabilization", ""],
            ["   • Activation: Automatic (based on frequency deviation)", ""],
            ["   • Typical Capacity Price: €7-10/MW/h", ""],
            ["   • Activation Factor: 5-7% duty cycle", ""],
            ["", ""],
            ["2. aFRR (Automatic Frequency Restoration Reserve)", ""],
            ["   • Response Time: 30 seconds - 5 minutes", ""],
            ["   • Purpose: Automatic load-frequency control", ""],
            ["   • Activation: Automatic (AGC signals from TSO)", ""],
            ["   • Typical Capacity Price: €5-10/MW/h", ""],
            ["   • Activation Factor: 10-15% duty cycle", ""],
            ["   • Primary Revenue Source", ""],
            ["", ""],
            ["3. mFRR (Manual Frequency Restoration Reserve)", ""],
            ["   • Response Time: 5-15 minutes", ""],
            ["   • Purpose: Manual dispatch by TSO operators", ""],
            ["   • Activation: Manual order from control center", ""],
            ["   • Typical Capacity Price: €2-5/MW/h", ""],
            ["   • Activation Factor: 3-7% duty cycle", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["PZU (DAY-AHEAD) MARKET", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Market Characteristics:", ""],
            ["  • Hourly Auctions: Gate closure at 12:00 (day before delivery)", ""],
            ["  • Price Formation: Marginal pricing (supply-demand intersection)", ""],
            ["  • Historical Price Range: €20-400/MWh (typical €50-150/MWh)", ""],
            ["  • Daily Price Volatility: 3-8x difference peak vs off-peak", ""],
            ["", ""],
            ["Arbitrage Opportunity:", ""],
            ["  • Night Hours (02:00-06:00): Low prices (€30-60/MWh)", ""],
            ["  • Peak Hours (18:00-21:00): High prices (€120-250/MWh)", ""],
            ["  • Typical Spread: €60-120/MWh", ""],
            ["  • Net Margin After Losses: €50-100/MWh", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["MARKET DRIVERS & GROWTH", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Renewable Integration:", ""],
            ["  • Romania Target: 35% renewable energy by 2030", ""],
            ["  • Wind + Solar Capacity: 5+ GW installed, growing rapidly", ""],
            ["  • Intermittency Challenge: Batteries crucial for grid stability", ""],
            ["", ""],
            ["Coal Phase-Out:", ""],
            ["  • Coal plants closing 2025-2032 (EU regulations)", ""],
            ["  • Grid flexibility gap: Batteries replace baseload stability", ""],
            ["  • Increased need for frequency regulation services", ""],
            ["", ""],
            ["EU Regulatory Support:", ""],
            ["  • Clean Energy Package: Mandates equal access for storage", ""],
            ["  • Electricity Regulation 2019/943: Removes double charging", ""],
            ["  • National Energy Strategy: Supports storage development", ""],
            ["", ""],
            ["Price Volatility Increase:", ""],
            ["  • More renewables = more price fluctuations", ""],
            ["  • Bigger spreads = better arbitrage opportunities", ""],
            ["  • Higher activation demand = better FR revenue", ""],
            ["", ""],
        ]

        market_df = pd.DataFrame(market_context, columns=["Topic", "Details"])
        market_df.to_excel(writer, sheet_name="Market Context", index=False)

        # ========================================================================
        # SHEET 3: TECHNICAL SPECIFICATIONS
        # ========================================================================
        technical_specs = [
            ["TECHNICAL SPECIFICATIONS - BATTERY SYSTEM", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["BATTERY SPECIFICATIONS", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Battery Technology", "Lithium-Ion (NMC or LFP chemistry)"],
            ["Energy Capacity", f"{capacity_mwh:.1f} MWh"],
            ["Power Rating", f"{power_mw:.1f} MW"],
            ["C-Rate", f"{power_mw/capacity_mwh:.2f}C"],
            ["Storage Duration", f"{capacity_mwh/power_mw:.1f} hours at full power"],
            ["", ""],
            ["Round-Trip Efficiency", "90% (AC-to-AC)"],
            ["  • Charge Efficiency", "95%"],
            ["  • Discharge Efficiency", "95%"],
            ["  • Combined", "90.25% (0.95 × 0.95)"],
            ["", ""],
            ["SOC Operating Window", "10% - 90%"],
            ["  • Usable Capacity", f"{capacity_mwh * 0.8:.1f} MWh (80% DoD)"],
            ["  • Reserve Margins", "10% top + 10% bottom"],
            ["  • Degradation Protection", "Conservative cycling prevents wear"],
            ["", ""],
            ["Expected Lifetime", ""],
            ["  • Calendar Life", "15 years"],
            ["  • Cycle Life", "6,000 full equivalent cycles"],
            ["  • Warranty", "10 years / 80% capacity retention"],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["POWER ELECTRONICS", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Inverter Technology", "Bidirectional Power Conversion System"],
            ["AC Output Voltage", "110 kV or 220 kV (grid voltage)"],
            ["Frequency", "50 Hz ± 0.2 Hz"],
            ["Power Factor", "±0.95 (can provide reactive power support)"],
            ["", ""],
            ["Response Time", ""],
            ["  • FCR Activation", "< 30 seconds (full power)"],
            ["  • aFRR Activation", "< 5 minutes (full power)"],
            ["  • mFRR Activation", "< 15 minutes (full power)"],
            ["", ""],
            ["Control Capabilities", ""],
            ["  • Frequency Response", "Automatic droop control"],
            ["  • AGC Integration", "Direct signals from Transelectrica"],
            ["  • SOC Management", "Real-time optimization"],
            ["  • Remote Monitoring", "24/7 SCADA connection"],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["BALANCE OF PLANT", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Components", ""],
            ["  • Medium Voltage Transformer", f"{power_mw:.1f} MVA"],
            ["  • Switchgear & Protection", "ABB or Siemens (110-220 kV)"],
            ["  • HVAC / Thermal Management", "Air or liquid cooling"],
            ["  • Fire Suppression", "NFPA 855 compliant"],
            ["  • Container Housing", "Weatherproof IP55 enclosures"],
            ["", ""],
            ["Grid Connection", ""],
            ["  • Connection Point", "Existing substation (110-220 kV)"],
            ["  • Connection Cost", "Included in CapEx"],
            ["  • Metering", "Smart meters (15-min intervals)"],
            ["  • Grid Code Compliance", "Transelectrica technical requirements"],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["OPERATIONAL PARAMETERS", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Availability", "95% (scheduled maintenance 5%)"],
            ["Response Accuracy", "±2% of contracted capacity"],
            ["Ramp Rate", f"{power_mw:.1f} MW/minute"],
            ["Operating Temperature", "-10°C to +45°C ambient"],
            ["", ""],
            ["Maintenance", ""],
            ["  • Preventive Maintenance", "Quarterly inspections"],
            ["  • Battery Monitoring", "Continuous (cell-level BMS)"],
            ["  • Annual Downtime", "~18 days/year (95% availability)"],
            ["", ""],
        ]

        tech_df = pd.DataFrame(technical_specs, columns=["Specification", "Value"])
        tech_df.to_excel(writer, sheet_name="Technical Specs", index=False)

        # ========================================================================
        # SHEET 4: RISK ANALYSIS & MITIGATION
        # ========================================================================
        risks = [
            ["RISK ANALYSIS & MITIGATION STRATEGIES", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["MARKET RISKS", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Risk: Price Volatility Reduction", ""],
            ["  • Description: PZU spreads may narrow over time", ""],
            ["  • Impact: Lower arbitrage profits", ""],
            ["  • Probability: Medium (20-30% over 5 years)", ""],
            ["  • Mitigation:", ""],
            ["    - Dual revenue strategy (FR + PZU flexibility)", ""],
            ["    - Historical data shows stable spreads 2020-2024", ""],
            ["    - Increasing renewables = more volatility, not less", ""],
            ["", ""],
            ["Risk: Regulatory Changes", ""],
            ["  • Description: Market rules or tariffs change", ""],
            ["  • Impact: Revenue model adjustments needed", ""],
            ["  • Probability: Low-Medium (EU framework stable)", ""],
            ["  • Mitigation:", ""],
            ["    - Clean Energy Package provides 10-year visibility", ""],
            ["    - Active industry associations (ESA, EASE)", ""],
            ["    - Diversified revenue streams", ""],
            ["", ""],
            ["Risk: Increased Competition", ""],
            ["  • Description: More batteries enter market", ""],
            ["  • Impact: Lower capacity prices for FR", ""],
            ["  • Probability: Medium-High (market growth)", ""],
            ["  • Mitigation:", ""],
            ["    - First-mover advantage (grid connection secured)", ""],
            ["    - Established TSO relationships", ""],
            ["    - Operational excellence (high availability)", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["TECHNICAL RISKS", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Risk: Battery Degradation", ""],
            ["  • Description: Capacity fades faster than expected", ""],
            ["  • Impact: Reduced revenue after year 7-8", ""],
            ["  • Probability: Low (proven technology)", ""],
            ["  • Mitigation:", ""],
            ["    - Conservative SOC window (10-90%)", ""],
            ["    - Max 1-2 cycles per day (PZU mode)", ""],
            ["    - Tier-1 supplier with 10-year warranty", ""],
            ["    - Advanced thermal management", ""],
            ["", ""],
            ["Risk: Equipment Failure", ""],
            ["  • Description: Inverter or BMS malfunction", ""],
            ["  • Impact: Lost revenue during downtime", ""],
            ["  • Probability: Low-Medium (mature technology)", ""],
            ["  • Mitigation:", ""],
            ["    - Redundant components (N+1 design)", ""],
            ["    - Comprehensive O&M contract", ""],
            ["    - Spare parts on-site", ""],
            ["    - Business interruption insurance", ""],
            ["", ""],
            ["Risk: Grid Connection Issues", ""],
            ["  • Description: Substation unavailable or curtailment", ""],
            ["  • Impact: Inability to trade or provide services", ""],
            ["  • Probability: Very Low (firm connection)", ""],
            ["  • Mitigation:", ""],
            ["    - Grid connection agreement with Transelectrica", ""],
            ["    - Priority dispatch for ancillary services", ""],
            ["    - Backup grid codes and redundancy", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["FINANCIAL RISKS", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Risk: Debt Service Coverage", ""],
            ["  • Description: Revenue insufficient to cover loan", ""],
            ["  • Impact: Default risk", ""],
            ["  • Probability: Low (conservative projections)", ""],
            ["  • Mitigation:", ""],
            ["    - DSCR > 1.3 in base case scenario", ""],
            ["    - Revenue diversification (FR + PZU)", ""],
            ["    - Debt reserve account (6 months debt service)", ""],
            ["    - Equity cushion (30% equity)", ""],
            ["", ""],
            ["Risk: Interest Rate Increase", ""],
            ["  • Description: Floating rate debt becomes expensive", ""],
            ["  • Impact: Higher debt service costs", ""],
            ["  • Probability: Medium (ECB policy changes)", ""],
            ["  • Mitigation:", ""],
            ["    - Fixed-rate loan (eliminates risk)", ""],
            ["    - If floating: interest rate cap/swap", ""],
            ["    - Refinancing option after 3 years", ""],
            ["", ""],
            ["Risk: Currency Risk (EUR/RON)", ""],
            ["  • Description: RON revenue vs EUR debt", ""],
            ["  • Impact: FX losses if RON weakens", ""],
            ["  • Probability: Medium (emerging market FX)", ""],
            ["  • Mitigation:", ""],
            ["    - Natural hedge (revenues ~70% EUR-linked)", ""],
            ["    - FX forward contracts for debt service", ""],
            ["    - RON strengthening trend 2020-2024", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["OVERALL RISK RATING", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Project Risk Profile", "LOW-MEDIUM"],
            ["  • Proven Technology", "✓"],
            ["  • Stable Regulatory Framework", "✓"],
            ["  • Diversified Revenue Streams", "✓"],
            ["  • Conservative Financial Structure", "✓"],
            ["  • Experienced Development Team", "✓"],
            ["", ""],
            ["Comparable Projects", ""],
            ["  • Similar projects operational in Romania: 2", ""],
            ["  • Similar projects under construction: 5+", ""],
            ["  • Default rate in sector: < 2% (globally)", ""],
            ["", ""],
        ]

        risk_df = pd.DataFrame(risks, columns=["Risk Category", "Details"])
        risk_df.to_excel(writer, sheet_name="Risk Analysis", index=False)

        # ========================================================================
        # SHEET 5: REGULATORY & COMPLIANCE
        # ========================================================================
        regulatory = [
            ["REGULATORY FRAMEWORK & COMPLIANCE", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["EUROPEAN UNION REGULATIONS", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Clean Energy Package (2019)", ""],
            ["  • Directive (EU) 2019/944: Internal Electricity Market", ""],
            ["  • Regulation (EU) 2019/943: Electricity Market Design", ""],
            ["  • Key Provision: Equal access for energy storage", ""],
            ["  • Impact: Batteries compete on level playing field", ""],
            ["", ""],
            ["REMIT (Energy Market Integrity)", ""],
            ["  • Regulation (EU) 1227/2011", ""],
            ["  • Prohibits insider trading and market manipulation", ""],
            ["  • Requires: Reporting of transactions to ACER", ""],
            ["  • Compliance: Automated trade reporting system", ""],
            ["", ""],
            ["Network Codes", ""],
            ["  • Requirements for Generators (RfG)", ""],
            ["  • Demand Connection Code (DCC)", ""],
            ["  • Compliance: Grid connection studies completed", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["ROMANIAN NATIONAL REGULATIONS", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Regulator", "ANRE (Romanian Energy Regulatory Authority)"],
            ["", ""],
            ["Key Regulations", ""],
            ["  • Electricity Law 123/2012 (as amended)", ""],
            ["  • Grid Code (Transelectrica technical rules)", ""],
            ["  • Market Rules (OPCOM trading procedures)", ""],
            ["  • Licensing Requirements (Generation license)", ""],
            ["", ""],
            ["Licensing", ""],
            ["  • License Type: Electricity Generation License", ""],
            ["  • Issued By: ANRE", ""],
            ["  • Duration: 10 years (renewable)", ""],
            ["  • Status: Application submitted / To be obtained", ""],
            ["", ""],
            ["Grid Connection", ""],
            ["  • Connection Agreement: With Transelectrica", ""],
            ["  • Connection Point: [Substation Name] 110/220 kV", ""],
            ["  • Connection Capacity: " + f"{power_mw:.1f} MW", ""],
            ["  • Grid Code Compliance: Technical studies approved", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["ENVIRONMENTAL PERMITS", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Environmental Impact Assessment", ""],
            ["  • Required: No (battery storage exempt)", ""],
            ["  • Reasoning: No emissions, minimal land use", ""],
            ["  • Alternative: Environmental Authorization", ""],
            ["  • Status: Obtained / In progress", ""],
            ["", ""],
            ["Construction Permit", ""],
            ["  • Issued By: Local municipality", ""],
            ["  • Requirements: Site plan, fire safety, structural", ""],
            ["  • Status: Obtained / In progress", ""],
            ["", ""],
            ["Fire Safety", ""],
            ["  • Standard: NFPA 855 (Energy Storage Systems)", ""],
            ["  • Compliance: Automatic fire suppression", ""],
            ["  • Inspection: Annual by certified inspector", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["MARKET PARTICIPATION", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["OPCOM (Day-Ahead Market)", ""],
            ["  • Registration: Market participant agreement", ""],
            ["  • Collateral: Bank guarantee (€50k-100k)", ""],
            ["  • Trading: Electronic platform (24/7)", ""],
            ["  • Settlement: T+7 days", ""],
            ["", ""],
            ["Transelectrica (Ancillary Services)", ""],
            ["  • Prequalification: Technical tests required", ""],
            ["  • FCR/aFRR/mFRR: Separate qualification for each", ""],
            ["  • Capacity Auction: Monthly or annual contracts", ""],
            ["  • Activation Settlement: Actual metered data", ""],
            ["", ""],
            ["Metering & Data", ""],
            ["  • Metering Standard: Smart meters (15-min intervals)", ""],
            ["  • Data Provider: TSO-approved meter operator", ""],
            ["  • SCADA Connection: Real-time data exchange", ""],
            ["  • Compliance: REMIT reporting (T+1 day)", ""],
            ["", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["TAX & ACCOUNTING", ""],
            ["═══════════════════════════════════════════════════════════", ""],
            ["", ""],
            ["Corporate Tax", "16% (standard Romanian rate)"],
            ["VAT", "19% (standard rate, input VAT recoverable)"],
            ["Property Tax", "Local rate (minimal for industrial equipment)"],
            ["", ""],
            ["Accounting Standards", ""],
            ["  • IFRS (International Financial Reporting Standards)", ""],
            ["  • Auditor: Big 4 or equivalent", ""],
            ["  • Reporting: Annual financial statements", ""],
            ["", ""],
        ]

        regulatory_df = pd.DataFrame(regulatory, columns=["Regulatory Area", "Details"])
        regulatory_df.to_excel(writer, sheet_name="Regulatory Compliance", index=False)

    output.seek(0)
    return output.getvalue()


def add_business_report_button(
    project_name: str,
    capacity_mwh: float,
    power_mw: float,
    investment_eur: float,
    equity_eur: float,
    debt_eur: float,
    loan_term_years: int,
    interest_rate: float,
    fr_metrics: Optional[Dict[str, Any]],
    pzu_metrics: Optional[Dict[str, Any]],
    fr_opex_annual: float,
    pzu_opex_annual: float,
) -> None:
    """
    Add business overview report export button to Streamlit UI

    Designed for SINGLE project (e.g., 15 MWh)
    """

    st.markdown("---")
    st.markdown("### 📄 Professional Business Overview Report")

    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(f"""
        **Comprehensive business explanation for a {capacity_mwh:.0f} MWh battery project**

        Perfect for:
        - Bank presentations and loan applications
        - Investor pitch decks and due diligence
        - Partnership proposals
        - Regulatory submissions

        **Includes 5 detailed sheets:**
        1. Executive Summary (project overview + financials)
        2. Market Context & Opportunity (Romanian energy market)
        3. Technical Specifications (battery + power electronics)
        4. Risk Analysis & Mitigation
        5. Regulatory & Compliance Framework
        """)

    with col2:
        if st.button("📥 Export Business Overview", type="primary", use_container_width=True):
            try:
                business_report = generate_business_overview_excel(
                    project_name=project_name,
                    capacity_mwh=capacity_mwh,
                    power_mw=power_mw,
                    investment_eur=investment_eur,
                    equity_eur=equity_eur,
                    debt_eur=debt_eur,
                    loan_term_years=loan_term_years,
                    interest_rate=interest_rate,
                    fr_metrics=fr_metrics,
                    pzu_metrics=pzu_metrics,
                    fr_opex_annual=fr_opex_annual,
                    pzu_opex_annual=pzu_opex_annual,
                )

                filename = f"{project_name.replace(' ', '_')}_Business_Overview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

                st.download_button(
                    label="⬇️ Download Business Report",
                    data=business_report,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

                st.success(f"✅ Business overview report generated for {capacity_mwh:.0f} MWh project!")

            except Exception as e:
                st.error(f"❌ Error generating business report: {e}")
