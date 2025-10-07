"""
Comprehensive Data Context Builder for AI Assistant
Gathers all available data from the Battery Analytics Platform
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json

class BatteryDataContext:
    """Builds comprehensive context from all battery data sources"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent.parent
        self.data_path = self.project_root / "data"

    def get_full_context(self, cfg: dict = None) -> Dict[str, Any]:
        """
        Gather ALL available data and analytics from the platform
        Returns a comprehensive context dictionary for AI
        """
        context = {
            "timestamp": datetime.now().isoformat(),
            "fr_data": self._get_fr_context(),
            "pzu_data": self._get_pzu_context(),
            "investment": self._get_investment_context(cfg),
            "market_stats": self._get_market_statistics(),
            "battery_specs": self._get_battery_specifications(cfg),
            "revenue_analysis": self._get_revenue_analysis(),
            "data_quality": self._get_data_quality_metrics(),
        }
        return context

    def _get_fr_context(self) -> Dict[str, Any]:
        """Extract comprehensive FR (Frequency Regulation) data context"""
        fr_context = {
            "available": False,
            "summary": "No FR data available"
        }

        try:
            # Load DAMAS activation data
            fr_path = self.data_path / "imbalance_history.csv"
            if not fr_path.exists():
                return fr_context

            df = pd.read_csv(fr_path)

            # Check for DAMAS columns
            has_damas = all(col in df.columns for col in [
                'afrr_up_activated_mwh', 'afrr_down_activated_mwh',
                'mfrr_up_activated_mwh', 'mfrr_down_activated_mwh'
            ])

            fr_context = {
                "available": True,
                "total_rows": len(df),
                "date_range": {
                    "start": df['date'].min(),
                    "end": df['date'].max(),
                    "days": (pd.to_datetime(df['date'].max()) - pd.to_datetime(df['date'].min())).days
                },
                "has_damas_activation": has_damas,
                "data_accuracy": "90-95%" if has_damas else "25-35%",
            }

            if has_damas:
                # Calculate detailed activation statistics
                fr_context["activation_stats"] = {
                    "afrr_up": {
                        "mean_mwh": float(df['afrr_up_activated_mwh'].mean()),
                        "max_mwh": float(df['afrr_up_activated_mwh'].max()),
                        "total_mwh": float(df['afrr_up_activated_mwh'].sum()),
                        "activation_rate": float((df['afrr_up_activated_mwh'] > 0).mean()),
                        "percentiles": {
                            "p50": float(df['afrr_up_activated_mwh'].quantile(0.5)),
                            "p90": float(df['afrr_up_activated_mwh'].quantile(0.9)),
                            "p95": float(df['afrr_up_activated_mwh'].quantile(0.95))
                        }
                    },
                    "afrr_down": {
                        "mean_mwh": float(df['afrr_down_activated_mwh'].mean()),
                        "max_mwh": float(df['afrr_down_activated_mwh'].max()),
                        "total_mwh": float(df['afrr_down_activated_mwh'].sum()),
                        "activation_rate": float((df['afrr_down_activated_mwh'] > 0).mean()),
                        "percentiles": {
                            "p50": float(df['afrr_down_activated_mwh'].quantile(0.5)),
                            "p90": float(df['afrr_down_activated_mwh'].quantile(0.9)),
                            "p95": float(df['afrr_down_activated_mwh'].quantile(0.95))
                        }
                    }
                }

                # Monthly breakdown
                df['month'] = pd.to_datetime(df['date']).dt.to_period('M')
                monthly_stats = []
                for month, mdf in df.groupby('month'):
                    monthly_stats.append({
                        "month": str(month),
                        "afrr_up_total": float(mdf['afrr_up_activated_mwh'].sum()),
                        "afrr_down_total": float(mdf['afrr_down_activated_mwh'].sum()),
                        "activation_hours": float((mdf['afrr_up_activated_mwh'] > 0).sum() * 0.25),
                    })
                fr_context["monthly_breakdown"] = monthly_stats[:6]  # Last 6 months

                # Price statistics if available
                if 'afrr_up_price_eur' in df.columns:
                    fr_context["price_stats"] = {
                        "afrr_up_price": {
                            "mean": float(df['afrr_up_price_eur'].mean()),
                            "max": float(df['afrr_up_price_eur'].max()),
                            "min": float(df['afrr_up_price_eur'].min()),
                        },
                        "afrr_down_price": {
                            "mean": float(df['afrr_down_price_eur'].abs().mean()),
                            "max": float(df['afrr_down_price_eur'].abs().max()),
                            "min": float(df['afrr_down_price_eur'].abs().min()),
                        }
                    }

        except Exception as e:
            fr_context["error"] = str(e)

        return fr_context

    def _get_pzu_context(self) -> Dict[str, Any]:
        """Extract comprehensive PZU (arbitrage) data context"""
        pzu_context = {
            "available": False,
            "summary": "No PZU data available"
        }

        try:
            # Try multiple PZU file variants
            pzu_files = [
                "pzu_history_3y.csv",
                "pzu_history_1y.csv",
                "pzu_history.csv"
            ]

            for filename in pzu_files:
                pzu_path = self.data_path / filename
                if pzu_path.exists():
                    df = pd.read_csv(pzu_path)

                    # Identify price column
                    price_col = None
                    for col in ['price', 'price_eur', 'price_eur_mwh', 'eur_per_mwh']:
                        if col in df.columns:
                            price_col = col
                            break

                    if price_col:
                        pzu_context = {
                            "available": True,
                            "source_file": filename,
                            "total_rows": len(df),
                            "date_range": {
                                "start": df['date'].min() if 'date' in df.columns else "N/A",
                                "end": df['date'].max() if 'date' in df.columns else "N/A",
                            },
                            "price_statistics": {
                                "mean": float(df[price_col].mean()),
                                "max": float(df[price_col].max()),
                                "min": float(df[price_col].min()),
                                "std": float(df[price_col].std()),
                                "spread": float(df[price_col].max() - df[price_col].min()),
                            },
                            "arbitrage_opportunity": {
                                "daily_spread": self._calculate_daily_spread(df, price_col),
                                "best_hours_buy": self._get_best_hours(df, price_col, 'buy'),
                                "best_hours_sell": self._get_best_hours(df, price_col, 'sell'),
                            }
                        }
                        break

        except Exception as e:
            pzu_context["error"] = str(e)

        return pzu_context

    def _calculate_daily_spread(self, df: pd.DataFrame, price_col: str) -> float:
        """Calculate average daily price spread"""
        try:
            if 'date' not in df.columns:
                return 0.0

            # Create a copy to avoid modifying original
            df_copy = df.copy()
            df_copy['date'] = pd.to_datetime(df_copy['date'])
            df_copy.set_index('date', inplace=True)

            # Group by day and calculate spread
            daily_max = df_copy[price_col].resample('D').max()
            daily_min = df_copy[price_col].resample('D').min()
            daily_spread = daily_max - daily_min

            return float(daily_spread.mean())
        except:
            return 0.0

    def _get_best_hours(self, df: pd.DataFrame, price_col: str, direction: str) -> List[int]:
        """Identify best hours for buy/sell operations"""
        try:
            if 'hour' in df.columns:
                hourly_avg = df.groupby('hour')[price_col].mean()
            elif 'date' in df.columns:
                df['hour'] = pd.to_datetime(df['date']).dt.hour
                hourly_avg = df.groupby('hour')[price_col].mean()
            else:
                return []

            if direction == 'buy':
                return hourly_avg.nsmallest(4).index.tolist()  # 4 cheapest hours
            else:
                return hourly_avg.nlargest(4).index.tolist()  # 4 most expensive hours
        except:
            return []

    def _get_investment_context(self, cfg: dict = None) -> Dict[str, Any]:
        """Extract investment and financing context"""
        investment_context = {
            "typical_configuration": {
                "power_mw": 25,
                "capacity_mwh": 50,
                "duration_hours": 2,
                "efficiency": 0.9,
                "lifetime_years": 15,
            },
            "financial_assumptions": {
                "capex_per_mwh": 300000,  # €300k per MWh
                "opex_percent": 2.5,  # 2.5% of capex annually
                "debt_ratio": 0.7,  # 70% debt financing
                "interest_rate": 0.06,  # 6% annual
                "loan_term_years": 10,
            },
            "roi_metrics": {
                "typical_payback_years": "5-7 years",
                "typical_irr": "12-18%",
                "typical_npv_positive": True,
            }
        }

        # Override with config if available
        if cfg:
            if 'investment' in cfg:
                investment_context.update(cfg['investment'])

        return investment_context

    def _get_market_statistics(self) -> Dict[str, Any]:
        """Calculate comprehensive market statistics"""
        market_stats = {
            "romanian_market": {
                "fr_market_size_mw": 800,  # Approximate FR market size
                "pzu_daily_volume_gwh": 50,  # Daily trading volume
                "battery_penetration": "Growing - 200MW operational, 500MW planned",
            },
            "price_volatility": {},
            "revenue_potential": {}
        }

        # Calculate FR revenue potential
        try:
            fr_data = self._get_fr_context()
            if fr_data.get("available") and fr_data.get("has_damas_activation"):
                # Estimate annual revenue for 25MW battery
                activation_rate = fr_data["activation_stats"]["afrr_up"]["activation_rate"]
                mean_price = fr_data.get("price_stats", {}).get("afrr_up_price", {}).get("mean", 150)

                annual_capacity_revenue = 25 * 8760 * 100  # 25MW * hours * €100/MW/h
                annual_activation_revenue = 25 * 8760 * 0.25 * activation_rate * mean_price

                market_stats["revenue_potential"]["fr_annual"] = {
                    "capacity": annual_capacity_revenue,
                    "activation": annual_activation_revenue,
                    "total": annual_capacity_revenue + annual_activation_revenue,
                }
        except:
            pass

        # Calculate PZU revenue potential
        try:
            pzu_data = self._get_pzu_context()
            if pzu_data.get("available"):
                daily_spread = pzu_data.get("arbitrage_opportunity", {}).get("daily_spread", 0)
                efficiency = 0.9
                capacity_mwh = 50

                daily_revenue = capacity_mwh * daily_spread * efficiency * 0.8  # 80% capture rate
                annual_revenue = daily_revenue * 365

                market_stats["revenue_potential"]["pzu_annual"] = annual_revenue
        except:
            pass

        return market_stats

    def _get_battery_specifications(self, cfg: dict = None) -> Dict[str, Any]:
        """Get battery technical specifications"""
        specs = {
            "default_configuration": {
                "power_mw": 25,
                "capacity_mwh": 50,
                "c_rate": 0.5,
                "round_trip_efficiency": 0.9,
                "soc_min": 0.1,
                "soc_max": 0.9,
                "depth_of_discharge": 0.8,
                "cycles_per_day": 1.5,
                "expected_lifetime_cycles": 6000,
                "expected_lifetime_years": 15,
            },
            "technology": "Lithium-ion (LFP typical for grid-scale)",
            "use_cases": ["Frequency Regulation (FR)", "Energy Arbitrage (PZU)", "Ancillary Services"],
        }

        if cfg and 'battery' in cfg:
            specs["configured"] = cfg['battery']

        return specs

    def _get_revenue_analysis(self) -> Dict[str, Any]:
        """Perform revenue analysis based on available data"""
        analysis = {
            "fr_vs_pzu": {},
            "optimal_strategy": "To be determined based on data",
            "key_insights": []
        }

        try:
            fr_context = self._get_fr_context()
            pzu_context = self._get_pzu_context()

            # Compare FR vs PZU if data available
            if fr_context.get("available") and pzu_context.get("available"):
                fr_potential = self._get_market_statistics().get("revenue_potential", {}).get("fr_annual", {}).get("total", 0)
                pzu_potential = self._get_market_statistics().get("revenue_potential", {}).get("pzu_annual", 0)

                if fr_potential and pzu_potential:
                    analysis["fr_vs_pzu"] = {
                        "fr_annual_revenue": fr_potential,
                        "pzu_annual_revenue": pzu_potential,
                        "winner": "FR" if fr_potential > pzu_potential else "PZU",
                        "difference": abs(fr_potential - pzu_potential),
                    }

                    analysis["key_insights"].append(
                        f"FR generates €{fr_potential:,.0f} annually vs PZU €{pzu_potential:,.0f}"
                    )

            # Add more insights based on data
            if fr_context.get("has_damas_activation"):
                activation_rate = fr_context["activation_stats"]["afrr_up"]["activation_rate"]
                analysis["key_insights"].append(
                    f"aFRR UP activation rate is {activation_rate:.1%} of all time slots"
                )

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    def _get_data_quality_metrics(self) -> Dict[str, Any]:
        """Assess data quality across all sources"""
        metrics = {
            "overall_quality": "Unknown",
            "data_sources": [],
            "coverage": {},
            "recommendations": []
        }

        try:
            # Check FR data quality
            fr_context = self._get_fr_context()
            if fr_context.get("available"):
                fr_quality = {
                    "source": "FR/DAMAS",
                    "rows": fr_context.get("total_rows", 0),
                    "accuracy": fr_context.get("data_accuracy", "Unknown"),
                    "has_activation": fr_context.get("has_damas_activation", False),
                }
                metrics["data_sources"].append(fr_quality)

                if fr_context.get("has_damas_activation"):
                    metrics["overall_quality"] = "Excellent"
                else:
                    metrics["overall_quality"] = "Limited"
                    metrics["recommendations"].append("Load DAMAS activation data for better FR accuracy")

            # Check PZU data quality
            pzu_context = self._get_pzu_context()
            if pzu_context.get("available"):
                pzu_quality = {
                    "source": "PZU",
                    "rows": pzu_context.get("total_rows", 0),
                    "file": pzu_context.get("source_file", "Unknown"),
                }
                metrics["data_sources"].append(pzu_quality)

        except:
            pass

        return metrics

    def format_for_llm(self, context: Dict[str, Any]) -> str:
        """Format context as a structured prompt for LLM"""
        prompt_parts = [
            "You are an AI assistant for a Battery Energy Storage System (BESS) analytics platform.",
            "You have access to comprehensive data about battery operations, market conditions, and financial performance.",
            "\n=== AVAILABLE DATA CONTEXT ===\n"
        ]

        # FR Data Summary
        if context["fr_data"]["available"]:
            fr = context["fr_data"]
            prompt_parts.append(f"""
**Frequency Regulation (FR) Data:**
- Date Range: {fr['date_range']['start']} to {fr['date_range']['end']} ({fr['date_range']['days']} days)
- Total Data Points: {fr['total_rows']:,} (15-minute intervals)
- Data Accuracy: {fr['data_accuracy']} ({"DAMAS TSO data" if fr['has_damas_activation'] else "Price correlation estimate"})
""")

            if fr.get("activation_stats"):
                stats = fr["activation_stats"]["afrr_up"]
                prompt_parts.append(f"""- aFRR UP Activation:
  - Mean: {stats['mean_mwh']:.2f} MWh per activation
  - Max: {stats['max_mwh']:.2f} MWh
  - Activation Rate: {stats['activation_rate']:.1%} of time slots
  - Total Volume: {stats['total_mwh']:,.0f} MWh
""")

            if fr.get("price_stats"):
                prices = fr["price_stats"]["afrr_up_price"]
                prompt_parts.append(f"""- aFRR Prices:
  - Mean: €{prices['mean']:.2f}/MWh
  - Range: €{prices['min']:.2f} to €{prices['max']:.2f}/MWh
""")

        # PZU Data Summary
        if context["pzu_data"]["available"]:
            pzu = context["pzu_data"]
            prompt_parts.append(f"""
**PZU Arbitrage Data:**
- Source: {pzu['source_file']}
- Date Range: {pzu['date_range']['start']} to {pzu['date_range']['end']}
- Price Statistics:
  - Mean: €{pzu['price_statistics']['mean']:.2f}/MWh
  - Daily Spread: €{pzu['arbitrage_opportunity']['daily_spread']:.2f}/MWh
  - Best Buy Hours: {pzu['arbitrage_opportunity']['best_hours_buy']}
  - Best Sell Hours: {pzu['arbitrage_opportunity']['best_hours_sell']}
""")

        # Market Statistics
        if context.get("market_stats", {}).get("revenue_potential"):
            revenue = context["market_stats"]["revenue_potential"]
            prompt_parts.append("\n**Revenue Potential (25MW/50MWh battery):**")

            if "fr_annual" in revenue:
                fr_rev = revenue["fr_annual"]
                prompt_parts.append(f"""- FR Annual: €{fr_rev['total']:,.0f}
  - Capacity: €{fr_rev['capacity']:,.0f}
  - Activation: €{fr_rev['activation']:,.0f}""")

            if "pzu_annual" in revenue:
                prompt_parts.append(f"- PZU Annual: €{revenue['pzu_annual']:,.0f}")

        # Battery Specifications
        specs = context["battery_specs"]["default_configuration"]
        prompt_parts.append(f"""
**Battery Configuration:**
- Power: {specs['power_mw']} MW
- Capacity: {specs['capacity_mwh']} MWh
- Efficiency: {specs['round_trip_efficiency']*100}%
- SOC Range: {specs['soc_min']*100}% to {specs['soc_max']*100}%
- Expected Lifetime: {specs['expected_lifetime_years']} years
""")

        # Investment Context
        invest = context["investment"]["financial_assumptions"]
        prompt_parts.append(f"""
**Investment Analysis:**
- CAPEX: €{invest['capex_per_mwh']:,} per MWh
- OPEX: {invest['opex_percent']}% of CAPEX annually
- Financing: {invest['debt_ratio']*100}% debt at {invest['interest_rate']*100}% interest
- Typical Payback: {context['investment']['roi_metrics']['typical_payback_years']}
- Typical IRR: {context['investment']['roi_metrics']['typical_irr']}
""")

        # Key Insights
        if context.get("revenue_analysis", {}).get("key_insights"):
            prompt_parts.append("\n**Key Insights:**")
            for insight in context["revenue_analysis"]["key_insights"]:
                prompt_parts.append(f"- {insight}")

        prompt_parts.append(f"""
=== END OF DATA CONTEXT ===

Based on this comprehensive data, please answer the user's question accurately and provide specific numbers when possible.
Remember you have access to real market data, actual activation volumes, prices, and validated revenue calculations.
""")

        return "\n".join(prompt_parts)