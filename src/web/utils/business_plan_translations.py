"""
Romanian translations for Business Plan Word document

Complete translation dictionary for all business plan content
"""

BP_TRANSLATIONS = {
    "en": {
        # Document title and headers
        "doc_title": "BATTERY ENERGY STORAGE SYSTEM",
        "doc_subtitle": "Comprehensive Business Plan",
        "confidential": "CONFIDENTIAL - For Investment Review Only",

        # Section 1: Executive Summary
        "section_1": "1. Executive Summary",
        "section_1_1": "1.1 Project Overview",
        "section_1_2": "1.2 Investment Highlights",
        "section_1_3": "1.3 Financial Overview",
        "section_1_4": "1.4 Strategic Rationale",

        # 1.1 Project Overview
        "overview_intro": "This business plan presents a comprehensive analysis of a {capacity_mwh:.0f} MWh / {power_mw:.0f} MW lithium-ion Battery Energy Storage System (BESS) project in Romania. The project leverages the growing need for grid flexibility services as Romania transitions toward renewable energy in compliance with EU climate directives.",
        "overview_tech": "The system will provide frequency regulation services (aFRR) to Transelectrica, Romania's transmission system operator (TSO), and engage in energy arbitrage through the day-ahead market (PZU). This dual-revenue strategy provides downside protection while maximizing returns in a rapidly evolving energy market.",
        "overview_location": "Location: Romania (specific site TBD based on grid connection availability)",
        "overview_technology": "Technology: Lithium-Ion Battery Energy Storage System (NMC or LFP chemistry)",
        "overview_capacity": "Energy Capacity: {capacity_mwh:.1f} MWh (AC, usable capacity)",
        "overview_power": "Power Rating: {power_mw:.1f} MW (continuous charge/discharge)",
        "overview_duration": "Storage Duration: {duration:.1f} hours at full power",
        "overview_efficiency": "Round-Trip Efficiency: 90% (AC-to-AC, all losses included)",
        "overview_lifetime": "Project Lifetime: 15 years operational + augmentation in Year 6",
        "overview_cod": "Target Commercial Operations Date (COD): Q4 2026 (16 months from financial close)",

        # 1.2 Investment Highlights
        "highlight_proven": "Proven Technology with Tier 1 Suppliers",
        "highlight_proven_desc": "Lithium-ion BESS technology is mature and bankable. Tier 1 suppliers (CATL, BYD, Samsung SDI, LG) offer 15-year warranties and performance guarantees. Over 10 GW of similar systems are operational globally.",
        "highlight_dual": "Dual Revenue Streams",
        "highlight_dual_desc": "Primary revenue from frequency regulation (aFRR) provides stable, capacity-based income with 98% availability requirements. Secondary revenue from energy arbitrage (PZU) capitalizes on price volatility and offers upside potential.",
        "highlight_growth": "High-Growth Market",
        "highlight_growth_desc": "Romania's renewable energy capacity is mandated to reach 35% by 2030 (EU directive). Wind and solar additions create frequency instability, driving demand for fast-responding battery systems. TSO prices for aFRR have remained stable at €6-8/MW/h.",
        "highlight_regulatory": "Supportive Regulatory Framework",
        "highlight_regulatory_desc": "ANRE (Romanian energy regulator) has established clear market rules for battery participation in ancillary services. EU Network Code compliance ensures long-term regulatory stability. No discriminatory treatment between battery and conventional generators.",
        "highlight_bankable": "Bankable Project Structure",
        "highlight_bankable_desc": "Fixed-price EPC contract with performance guarantees. Take-or-pay O&M contract with experienced provider. First lien security on all assets. Comprehensive insurance package (property, business interruption, warranty).",

        # 1.3 Financial Overview
        "financial_overview_title": "Financial Overview and Returns Analysis",
        "financial_investment": "Total Project Investment:",
        "financial_sources": "Sources of Funds:",
        "financial_equity": "Sponsor Equity ({equity_pct:.0f}%):",
        "financial_debt": "Senior Debt ({debt_pct:.0f}%):",
        "financial_debt_terms": "Debt Terms:",
        "financial_debt_amount": "Principal Amount:",
        "financial_debt_rate": "Interest Rate (Fixed):",
        "financial_debt_term": "Tenor:",
        "financial_debt_structure": "Amortization:",
        "financial_debt_structure_val": "{loan_term_years}-year level debt service (annuity)",
        "financial_debt_annual": "Annual Debt Service:",

        # Primary Revenue Strategy
        "revenue_primary": "Primary Revenue Strategy - Frequency Regulation (aFRR):",
        "revenue_primary_desc": "The project will contract {power_mw:.0f} MW of aFRR capacity with Transelectrica. This provides:",
        "revenue_capacity": "Capacity Revenue:",
        "revenue_capacity_val": "€{capacity_rev:,.0f}/year (contracted MW × capacity price × 8760 hours × availability)",
        "revenue_activation": "Activation Revenue:",
        "revenue_activation_val": "€{activation_rev:,.0f}/year (dispatched energy at wholesale prices)",
        "revenue_total": "Total Annual Revenue:",
        "revenue_opex": "Annual Operating Costs:",
        "revenue_debt": "Annual Debt Service:",
        "revenue_net": "Net Annual Profit:",
        "revenue_roi": "Annual ROI:",

        # Alternative Strategy
        "alt_strategy": "Energy Arbitrage Strategy (Alternative Business Case):",
        "alt_profit": "Annual Gross Profit:",
        "alt_profit_est": "Annual Gross Profit: €{revenue:,.0f} (estimated: {cycles} cycles/day, €{spread}/MWh spread)",
        "alt_opex": "Annual Operating Costs:",
        "alt_debt": "Annual Debt Service:",
        "alt_net": "Net Annual Profit:",
        "alt_roi": "Annual ROI:",
        "alt_note": "Note: PZU figures are conservative estimates based on historical Romanian day-ahead market spreads (€{spread}/MWh average spread, {cycles} cycles/day, {days} active trading days/year). Calculation uses {power} MW power rating for daily energy throughput with {eff:.0f}% round-trip efficiency. Actual performance will be determined by real-time market conditions and trading strategy execution. Run PZU Horizons simulator for detailed historical analysis.",

        # 1.4 Strategic Rationale
        "rationale_title": "Strategic Rationale",
        "rationale_intro": "The Romanian energy market is undergoing a fundamental transformation driven by three key trends:",
        "rationale_1": "Renewable Energy Expansion",
        "rationale_1_desc": "Romania has committed to achieving 35% renewable energy by 2030 under EU directives. As of 2024, wind and solar capacity is expanding rapidly, with over 2 GW of new projects in the pipeline. This creates grid instability that requires fast-responding flexibility resources.",
        "rationale_2": "Coal Plant Retirements",
        "rationale_2_desc": "Romania's coal-fired power plants are being phased out between 2025-2032 due to EU carbon regulations. These plants historically provided frequency regulation services. Their retirement creates a supply gap that battery systems are uniquely positioned to fill.",
        "rationale_3": "Market Liberalization",
        "rationale_3_desc": "ANRE has progressively opened ancillary services markets to new technologies. Battery systems can now participate on equal footing with conventional generators. Cross-border balancing integration with neighboring TSOs (Ukraine, Moldova, Hungary) will increase market liquidity and revenue opportunities from 2026 onward.",

        "rationale_why_bess": "Why Battery Energy Storage?",
        "rationale_why_1": "Response Speed: Batteries can deliver full power in <100 milliseconds, far faster than gas turbines (10-30 seconds) or hydro (5-15 seconds). This makes them ideal for frequency containment and restoration.",
        "rationale_why_2": "Operational Flexibility: Unlike thermal plants, batteries have zero minimum runtime, unlimited start/stop cycles, and no fuel costs. They can switch between charging and discharging modes seamlessly.",
        "rationale_why_3": "Revenue Stacking: Batteries can provide multiple services simultaneously (frequency regulation + reactive power + black start), whereas conventional generators are limited to single-use cases.",
        "rationale_why_4": "Environmental Benefits: Zero emissions, no air permits required, minimal land use (~1 hectare for 15 MW), and exemption from environmental taxes create a competitive cost advantage.",

        # Section 2
        "section_2": "2. Technology and Technical Specifications",
        "section_2_1": "2.1 System Overview",
        "section_2_2": "2.2 Battery Technology",
        "section_2_3": "2.3 Power Conversion System (PCS)",
        "section_2_4": "2.4 Balance of Plant",
        "section_2_5": "2.5 Safety and Fire Protection",
        "section_2_6": "2.6 Grid Connection",

        # Section 3
        "section_3": "3. Market Analysis",
        "section_3_1": "3.1 Frequency Regulation Market (aFRR)",
        "section_3_2": "3.2 Energy Arbitrage Market (PZU)",
        "section_3_3": "3.3 Competitive Landscape",
        "section_3_4": "3.4 Market Risks and Mitigations",

        # Section 4
        "section_4": "4. Revenue Model and Financial Projections",
        "section_4_1": "4.1 Base Case Assumptions",
        "section_4_2": "4.2 Revenue Breakdown",
        "section_4_3": "4.3 Operating Costs",
        "section_4_4": "4.4 15-Year Financial Projections",

        # Section 5
        "section_5": "5. Financing Structure",
        "section_5_1": "5.1 Sources and Uses of Funds",
        "section_5_2": "5.2 Debt Terms and Conditions",
        "section_5_3": "5.3 Debt Service Coverage",
        "section_5_4": "5.4 Equity Returns Analysis",

        # Section 6
        "section_6": "6. Risk Analysis",
        "section_6_1": "6.1 Technical Risks",
        "section_6_2": "6.2 Market and Revenue Risks",
        "section_6_3": "6.3 Regulatory and Political Risks",
        "section_6_4": "6.4 Financial Risks",
        "section_6_5": "6.5 Development and Construction Risks",
        "section_6_6": "6.6 Risk Mitigation Summary",

        # Section 7
        "section_7": "7. Ownership and Management",
        "section_7_1": "7.1 Project Structure",
        "section_7_2": "7.2 Management Team",
        "section_7_3": "7.3 Key Contracts",
        "section_7_4": "7.4 Insurance and Warranties",

        # Section 8
        "section_8": "8. Regulatory and Legal Framework",
        "section_8_1": "8.1 Energy Market Regulations",
        "section_8_2": "8.2 Grid Connection Requirements",
        "section_8_3": "8.3 Permitting and Licensing",
        "section_8_4": "8.4 Environmental Compliance",

        # Section 9
        "section_9": "9. Development Timeline",
        "section_9_1": "9.1 Overall Timeline (16 Months to COD)",
        "section_9_2": "9.2 Phase 1: Development and Permitting (Months 0-6)",
        "section_9_3": "9.3 Phase 2: Equipment Procurement (Months 3-7)",
        "section_9_4": "9.4 Phase 3: Construction and Installation (Months 7-12)",
        "section_9_5": "9.5 Phase 4: Testing and Commissioning (Months 12-14)",
        "section_9_6": "9.6 Phase 5: TSO Prequalification (Months 14-16)",
        "section_9_7": "9.7 Commercial Operations (Month 16+)",

        # Section 10
        "section_10": "10. Conclusions and Investment Recommendation",
        "conclusion_title": "Investment Recommendation",
    },

    "ro": {
        # Document title and headers
        "doc_title": "SISTEM DE STOCARE A ENERGIEI ÎN BATERII",
        "doc_subtitle": "Plan de Afaceri Complet",
        "confidential": "CONFIDENȚIAL - Doar pentru Analiza Investițiilor",

        # Section 1: Executive Summary
        "section_1": "1. Rezumat Executiv",
        "section_1_1": "1.1 Prezentare Generală a Proiectului",
        "section_1_2": "1.2 Puncte Forte ale Investiției",
        "section_1_3": "1.3 Prezentare Financiară",
        "section_1_4": "1.4 Rațiunea Strategică",

        # 1.1 Project Overview
        "overview_intro": "Acest plan de afaceri prezintă o analiză cuprinzătoare a unui proiect de Sistem de Stocare a Energiei în Baterii (BESS) cu capacitate de {capacity_mwh:.0f} MWh / {power_mw:.0f} MW cu litiu-ion în România. Proiectul valorifică nevoia crescândă de servicii de flexibilitate a rețelei pe măsură ce România trece la energie regenerabilă în conformitate cu directivele climatice ale UE.",
        "overview_tech": "Sistemul va furniza servicii de reglare a frecvenței (aFRR) către Transelectrica, operatorul de sistem de transport (TSO) al României, și se va angaja în arbitrajul energetic prin piața zilei următoare (PZU). Această strategie de venituri duale oferă protecție împotriva riscurilor, maximizând în același timp profiturile într-o piață energetică în rapidă evoluție.",
        "overview_location": "Locație: România (amplasament specific TBD în funcție de disponibilitatea conexiunii la rețea)",
        "overview_technology": "Tehnologie: Sistem de Stocare a Energiei în Baterii cu Litiu-Ion (chimie NMC sau LFP)",
        "overview_capacity": "Capacitate Energetică: {capacity_mwh:.1f} MWh (CA, capacitate utilizabilă)",
        "overview_power": "Putere Nominală: {power_mw:.1f} MW (încărcare/descărcare continuă)",
        "overview_duration": "Durată de Stocare: {duration:.1f} ore la putere maximă",
        "overview_efficiency": "Eficiență Ciclu Complet: 90% (CA-to-CA, toate pierderile incluse)",
        "overview_lifetime": "Durata de Viață a Proiectului: 15 ani operaționale + extindere în Anul 6",
        "overview_cod": "Data Țintă de Operare Comercială (COD): T4 2026 (16 luni de la închiderea financiară)",

        # 1.2 Investment Highlights
        "highlight_proven": "Tehnologie Dovedită cu Furnizori de Rang 1",
        "highlight_proven_desc": "Tehnologia BESS cu litiu-ion este matură și finanțabilă. Furnizorii de rang 1 (CATL, BYD, Samsung SDI, LG) oferă garanții de 15 ani și garanții de performanță. Peste 10 GW de sisteme similare sunt operaționale la nivel global.",
        "highlight_dual": "Fluxuri Duale de Venituri",
        "highlight_dual_desc": "Veniturile principale din reglarea frecvenței (aFRR) oferă venituri stabile, bazate pe capacitate, cu cerințe de disponibilitate de 98%. Veniturile secundare din arbitrajul energetic (PZU) capitalizează volatilitatea prețurilor și oferă potențial de creștere.",
        "highlight_growth": "Piață în Creștere Rapidă",
        "highlight_growth_desc": "Capacitatea de energie regenerabilă a României este obligată să atingă 35% până în 2030 (directivă UE). Adăugarea de energie eoliană și solară creează instabilitate a frecvenței, stimulând cererea pentru sisteme de baterii cu răspuns rapid. Prețurile TSO pentru aFRR au rămas stabile la €6-8/MW/h.",
        "highlight_regulatory": "Cadru Reglementar Favorabil",
        "highlight_regulatory_desc": "ANRE (regulatorul energetic român) a stabilit reguli clare de piață pentru participarea bateriilor la serviciile auxiliare. Conformitatea cu Codul de Rețea al UE asigură stabilitate regulamentară pe termen lung. Nicio tratare discriminatorie între baterii și generatoare convenționale.",
        "highlight_bankable": "Structură de Proiect Finanțabilă",
        "highlight_bankable_desc": "Contract EPC la preț fix cu garanții de performanță. Contract O&M take-or-pay cu furnizor experimentat. Garanție de primul rang pe toate activele. Pachet complet de asigurări (proprietate, întrerupere de afaceri, garanție).",

        # 1.3 Financial Overview
        "financial_overview_title": "Prezentare Financiară și Analiza Rentabilității",
        "financial_investment": "Investiție Totală în Proiect:",
        "financial_sources": "Surse de Fonduri:",
        "financial_equity": "Capital Sponsor ({equity_pct:.0f}%):",
        "financial_debt": "Datorie Senior ({debt_pct:.0f}%):",
        "financial_debt_terms": "Termeni Datorie:",
        "financial_debt_amount": "Suma Principală:",
        "financial_debt_rate": "Rată Dobândă (Fixă):",
        "financial_debt_term": "Termen:",
        "financial_debt_structure": "Amortizare:",
        "financial_debt_structure_val": "Serviciu datorie nivelat pe {loan_term_years} ani (anuitate)",
        "financial_debt_annual": "Serviciu Datorie Anual:",

        # Primary Revenue Strategy
        "revenue_primary": "Strategie Principală de Venituri - Reglare Frecvență (aFRR):",
        "revenue_primary_desc": "Proiectul va contracta {power_mw:.0f} MW capacitate aFRR cu Transelectrica. Aceasta oferă:",
        "revenue_capacity": "Venituri din Capacitate:",
        "revenue_capacity_val": "€{capacity_rev:,.0f}/an (MW contractat × preț capacitate × 8760 ore × disponibilitate)",
        "revenue_activation": "Venituri din Activare:",
        "revenue_activation_val": "€{activation_rev:,.0f}/an (energie expediată la prețuri en-gros)",
        "revenue_total": "Venituri Anuale Totale:",
        "revenue_opex": "Costuri Operaționale Anuale:",
        "revenue_debt": "Serviciu Datorie Anual:",
        "revenue_net": "Profit Net Anual:",
        "revenue_roi": "ROI Anual:",

        # Alternative Strategy
        "alt_strategy": "Strategie Arbitraj Energetic (Caz de Afaceri Alternativ):",
        "alt_profit": "Profit Brut Anual:",
        "alt_profit_est": "Profit Brut Anual: €{revenue:,.0f} (estimat: {cycles} cicluri/zi, spread €{spread}/MWh)",
        "alt_opex": "Costuri Operaționale Anuale:",
        "alt_debt": "Serviciu Datorie Anual:",
        "alt_net": "Profit Net Anual:",
        "alt_roi": "ROI Anual:",
        "alt_note": "Notă: Cifrele PZU sunt estimări conservatoare bazate pe spread-urile istorice ale pieței zilei următoare din România (spread mediu €{spread}/MWh, {cycles} cicluri/zi, {days} zile active de tranzacționare/an). Calculul folosește puterea nominală de {power} MW pentru volumul zilnic de energie cu eficiență ciclu complet de {eff:.0f}%. Performanța reală va fi determinată de condițiile pieței în timp real și execuția strategiei de tranzacționare. Rulați simulatorul PZU Horizons pentru analiză istorică detaliată.",

        # 1.4 Strategic Rationale
        "rationale_title": "Rațiunea Strategică",
        "rationale_intro": "Piața energetică din România suferă o transformare fundamentală determinată de trei tendințe cheie:",
        "rationale_1": "Expansiunea Energiei Regenerabile",
        "rationale_1_desc": "România s-a angajat să atingă 35% energie regenerabilă până în 2030 conform directivelor UE. Începând cu 2024, capacitatea eoliană și solară se extinde rapid, cu peste 2 GW de proiecte noi în curs de dezvoltare. Acest lucru creează instabilitate a rețelei care necesită resurse de flexibilitate cu răspuns rapid.",
        "rationale_2": "Retragerea Centralelor pe Cărbune",
        "rationale_2_desc": "Centralele electrice pe cărbune din România sunt eliminate treptat între 2025-2032 din cauza reglementărilor UE privind carbonul. Aceste centrale furnizau istoric servicii de reglare a frecvenței. Retragerea lor creează un deficit de ofertă pe care sistemele de baterii sunt poziționat unic să îl acopere.",
        "rationale_3": "Liberalizarea Pieței",
        "rationale_3_desc": "ANRE a deschis progresiv piețele serviciilor auxiliare pentru tehnologii noi. Sistemele de baterii pot participa acum în condiții de egalitate cu generatoarele convenționale. Integrarea echilibrării transfrontaliere cu TSO-urile vecine (Ucraina, Moldova, Ungaria) va crește lichiditatea pieței și oportunitățile de venituri începând cu 2026.",

        "rationale_why_bess": "De ce Stocare în Baterii?",
        "rationale_why_1": "Viteză de Răspuns: Bateriile pot furniza putere maximă în <100 milisecunde, mult mai rapid decât turbinele cu gaz (10-30 secunde) sau hidro (5-15 secunde). Acest lucru le face ideale pentru conținerea și restaurarea frecvenței.",
        "rationale_why_2": "Flexibilitate Operațională: Spre deosebire de centralele termice, bateriile au zero timp minim de funcționare, cicluri nelimitate de pornire/oprire și fără costuri de combustibil. Pot comuta între modurile de încărcare și descărcare fără probleme.",
        "rationale_why_3": "Stivuire de Venituri: Bateriile pot furniza simultan mai multe servicii (reglare frecvență + putere reactivă + pornire la negru), în timp ce generatoarele convenționale sunt limitate la cazuri de utilizare unică.",
        "rationale_why_4": "Beneficii de Mediu: Zero emisii, fără permise de aer necesare, utilizare minimă de teren (~1 hectar pentru 15 MW) și scutire de taxe de mediu creează un avantaj competitiv de cost.",

        # Section 2
        "section_2": "2. Tehnologie și Specificații Tehnice",
        "section_2_1": "2.1 Prezentare Generală Sistem",
        "section_2_2": "2.2 Tehnologia Bateriei",
        "section_2_3": "2.3 Sistem de Conversie a Puterii (PCS)",
        "section_2_4": "2.4 Echilibrul Instalației",
        "section_2_5": "2.5 Siguranță și Protecție Împotriva Incendiilor",
        "section_2_6": "2.6 Conexiune la Rețea",

        # Section 3
        "section_3": "3. Analiza Pieței",
        "section_3_1": "3.1 Piața Reglării Frecvenței (aFRR)",
        "section_3_2": "3.2 Piața Arbitrajului Energetic (PZU)",
        "section_3_3": "3.3 Peisajul Competitiv",
        "section_3_4": "3.4 Riscuri de Piață și Atenuări",

        # Section 4
        "section_4": "4. Model de Venituri și Proiecții Financiare",
        "section_4_1": "4.1 Ipoteze Caz de Bază",
        "section_4_2": "4.2 Defalcare Venituri",
        "section_4_3": "4.3 Costuri Operaționale",
        "section_4_4": "4.4 Proiecții Financiare pe 15 Ani",

        # Section 5
        "section_5": "5. Structura de Finanțare",
        "section_5_1": "5.1 Surse și Utilizări de Fonduri",
        "section_5_2": "5.2 Termeni și Condiții Datorie",
        "section_5_3": "5.3 Acoperirea Serviciului Datoriei",
        "section_5_4": "5.4 Analiza Rentabilității Capitalului",

        # Section 6
        "section_6": "6. Analiza Riscurilor",
        "section_6_1": "6.1 Riscuri Tehnice",
        "section_6_2": "6.2 Riscuri de Piață și Venituri",
        "section_6_3": "6.3 Riscuri Reglementare și Politice",
        "section_6_4": "6.4 Riscuri Financiare",
        "section_6_5": "6.5 Riscuri de Dezvoltare și Construcție",
        "section_6_6": "6.6 Rezumat Atenuare Riscuri",

        # Section 7
        "section_7": "7. Proprietate și Management",
        "section_7_1": "7.1 Structura Proiectului",
        "section_7_2": "7.2 Echipa de Management",
        "section_7_3": "7.3 Contracte Cheie",
        "section_7_4": "7.4 Asigurări și Garanții",

        # Section 8
        "section_8": "8. Cadrul Reglementar și Legal",
        "section_8_1": "8.1 Reglementări ale Pieței Energiei",
        "section_8_2": "8.2 Cerințe de Conexiune la Rețea",
        "section_8_3": "8.3 Autorizare și Licențiere",
        "section_8_4": "8.4 Conformitate de Mediu",

        # Section 9
        "section_9": "9. Calendar de Dezvoltare",
        "section_9_1": "9.1 Calendar General (16 Luni până la COD)",
        "section_9_2": "9.2 Faza 1: Dezvoltare și Autorizare (Lunile 0-6)",
        "section_9_3": "9.3 Faza 2: Achiziția Echipamentelor (Lunile 3-7)",
        "section_9_4": "9.4 Faza 3: Construcție și Instalare (Lunile 7-12)",
        "section_9_5": "9.5 Faza 4: Testare și Punere în Funcțiune (Lunile 12-14)",
        "section_9_6": "9.6 Faza 5: Precalificare TSO (Lunile 14-16)",
        "section_9_7": "9.7 Operațiuni Comerciale (Luna 16+)",

        # Section 10
        "section_10": "10. Concluzii și Recomandare de Investiție",
        "conclusion_title": "Recomandare de Investiție",
    }
}

def get_bp_text(key: str, language: str = "en", **kwargs) -> str:
    """Get translated text for business plan with format parameters"""
    text = BP_TRANSLATIONS.get(language, BP_TRANSLATIONS["en"]).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
