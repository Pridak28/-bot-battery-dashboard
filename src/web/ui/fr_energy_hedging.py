from __future__ import annotations

from typing import Dict

import pandas as pd
import streamlit as st

from src.data.data_provider import DataProvider
from src.web.utils.formatting import format_currency, format_price_per_mwh
from src.web.utils.styles import section_header, kpi_card, kpi_grid

try:
    from src.strategy.horizon import compute_best_hours_by_year, compute_pzu_monthly_costs
except ImportError:  # pragma: no cover - defensive fallback
    from src.strategy.horizon import compute_best_hours_by_year  # type: ignore

    def compute_pzu_monthly_costs(*_args, **_kwargs):  # type: ignore
        return pd.DataFrame(columns=["month", "avg_price_eur_mwh", "min_price_eur_mwh", "max_price_eur_mwh"])


def render_fr_energy_hedging(
    *,
    cfg: Dict,
    provider: DataProvider,
    capacity_mwh: float,
    power_mw: float,
    eta_rt: float,
    currency_decimals: int,
    thousands_sep: bool,
) -> None:
    """Render the FR energy hedging workbook using cached FR simulator outputs."""
    section_header(" FR Energy Hedging Workbook")
    st.caption(
        "Reuse the latest FR Simulator run and our stored PZU data to estimate the cost of hedging"
        " activation energy on OPCOM while earning FR revenue on Transelectrica."
    )

    fr_metrics = st.session_state.get("fr_market_metrics")
    if not isinstance(fr_metrics, dict) or not fr_metrics.get("months"):
        st.info("Run the FR Simulator first to populate activation data.")
        return

    fr_months_df = pd.DataFrame(fr_metrics["months"])
    if fr_months_df.empty or "month" not in fr_months_df.columns:
        st.info("No monthly activation data available; run the FR Simulator again.")
        return

    try:
        fr_months_df["month_period"] = pd.PeriodIndex(fr_months_df["month"], freq="M")
    except Exception:
        fr_months_df["month_period"] = pd.to_datetime(fr_months_df["month"], errors="coerce").dt.to_period("M")
    fr_months_df = fr_months_df.dropna(subset=["month_period"]).sort_values("month_period")
    fr_months_df["month"] = fr_months_df["month_period"].astype(str)

    for col in ["energy_cost_eur", "activation_revenue_eur", "activation_energy_mwh"]:
        if col in fr_months_df.columns:
            fr_months_df[col] = pd.to_numeric(fr_months_df[col], errors="coerce")

    cost_mask = fr_months_df.get("energy_cost_eur", pd.Series(dtype=float)).fillna(0.0) > 0.0
    if cost_mask.any():
        avg_cost = fr_months_df.loc[cost_mask, "energy_cost_eur"].mean()
        fr_months_df.loc[~cost_mask, "energy_cost_eur"] = avg_cost

    act_mask = fr_months_df.get("activation_revenue_eur", pd.Series(dtype=float)).fillna(0.0) > 0.0
    if act_mask.any():
        avg_act = fr_months_df.loc[act_mask, "activation_revenue_eur"].mean()
        fr_months_df.loc[~act_mask, "activation_revenue_eur"] = avg_act

    energy_mask = fr_months_df.get("activation_energy_mwh", pd.Series(dtype=float)).fillna(0.0) > 0.0
    if energy_mask.any():
        avg_energy = fr_months_df.loc[energy_mask, "activation_energy_mwh"].mean()
        fr_months_df.loc[~energy_mask, "activation_energy_mwh"] = avg_energy

    if {"capacity_revenue_eur", "activation_revenue_eur"}.issubset(fr_months_df.columns):
        fr_months_df["total_revenue_eur"] = (
            fr_months_df["capacity_revenue_eur"].fillna(0.0)
            + fr_months_df["activation_revenue_eur"].fillna(0.0)
        )

    hedging_window = st.slider(
        "Hedging window (months)",
        min_value=1,
        max_value=len(fr_months_df),
        value=min(12, len(fr_months_df)),
        step=1,
    )

    fr_window = fr_months_df.tail(hedging_window).reset_index(drop=True)
    activation_mwh = float(fr_window.get("activation_energy_mwh", 0.0).sum())
    activation_revenue = float(fr_window.get("total_revenue_eur", 0.0).sum())

    pzu_start = fr_window["month_period"].min().to_timestamp() if not fr_window.empty else None
    pzu_end = fr_window["month_period"].max().to_timestamp() if not fr_window.empty else None

    pzu_monthly = compute_pzu_monthly_costs(
        provider.pzu_csv,
        start_date=pzu_start,
        end_date=pzu_end,
    )

    if pzu_monthly.empty:
        st.warning("No OPCOM PZU data available for the same window.")
        reference_price = 0.0
    else:
        section_header("OPCOM PZU Monthly Prices")
        pzu_display = pzu_monthly.rename(
            columns={
                "month": "Month",
                "avg_price_eur_mwh": "Avg €/MWh",
                "min_price_eur_mwh": "Min €/MWh",
                "max_price_eur_mwh": "Max €/MWh",
            }
        )
        for col in ["Avg €/MWh", "Min €/MWh", "Max €/MWh"]:
            pzu_display[col] = pzu_display[col].apply(
                lambda v: format_price_per_mwh(v, decimals=max(currency_decimals, 2))
            )
        st.dataframe(pzu_display, width="stretch")

        reference_price = float(
            pzu_monthly["avg_price_eur_mwh"].astype(float).mean()
            if not pzu_monthly.empty
            else 0.0
        )

    section_header("FR vs OPCOM Hedging Summary")
    summary_cols = st.columns(4)
    summary_cols[0].metric(
        "Activation energy (MWh)",
        f"{activation_mwh:.2f}",
        help="Energy delivered or absorbed in FR activations.",
    )
    summary_cols[1].metric(
        "FR revenue (window)",
        format_currency(activation_revenue, decimals=currency_decimals, thousands=thousands_sep),
    )

    hedging_cost = activation_mwh * reference_price if reference_price else 0.0
    summary_cols[2].metric(
        "PZU hedging cost",
        format_currency(hedging_cost, decimals=currency_decimals, thousands=thousands_sep),
        help="Energy cost = activation MWh × average OPCOM price over the same months.",
    )

    summary_cols[3].metric(
        "Net margin",
        format_currency(activation_revenue - hedging_cost, decimals=currency_decimals, thousands=thousands_sep),
    )

    section_header("Detailed Hedging Breakdown")
    hedging_rows = []
    for _, row in fr_window.iterrows():
        month_label = str(row.get("month"))
        energy_mwh = float(row.get("activation_energy_mwh", 0.0))
        pzu_row = pzu_monthly[pzu_monthly["month"] == month_label]
        pzu_price = float(pzu_row["avg_price_eur_mwh"].iloc[0]) if not pzu_row.empty else reference_price
        row_cost = energy_mwh * pzu_price
        hedging_rows.append(
            {
                "Month": month_label,
                "Activation MWh": f"{energy_mwh:.2f}",
                "Hedge price €/MWh": format_price_per_mwh(pzu_price, decimals=max(currency_decimals, 2)),
                "Hedging cost €": format_currency(row_cost, decimals=currency_decimals, thousands=thousands_sep),
                "FR revenue €": format_currency(
                    float(row.get("total_revenue_eur", 0.0)), decimals=currency_decimals, thousands=thousands_sep
                ),
                "FR energy cost €": format_currency(
                    float(row.get("energy_cost_eur", 0.0)), decimals=currency_decimals, thousands=thousands_sep
                ),
            }
        )

    if hedging_rows:
        hedging_df = pd.DataFrame(hedging_rows)
        st.dataframe(hedging_df, width="stretch")
    else:
        st.info("No FR activation rows available for the selected window.")

    best_years_df = compute_best_hours_by_year(
        provider.pzu_csv,
        round_trip_efficiency=eta_rt,
        capacity_mwh=capacity_mwh,
        power_mw=power_mw,
        years=[2022, 2023, 2024, 2025],
    )

    if not best_years_df.empty:
        section_header(" Best Buy/Sell Hours Per Year (PZU)")
        st.caption(
            "Optimal 2-hour charge/discharge schedule computed separately for each calendar year,"
            " with annual profit at those hours."
        )

        display_years = []
        for _, row in best_years_df.iterrows():
            buy = int(row["buy_hour"])
            sell = int(row["sell_hour"])
            buy_end = min(buy + 2, 24)
            sell_end = min(sell + 2, 24)
            display_years.append(
                {
                    "Year": str(int(row["year"])),
                    "Charge window": f"{buy:02d}:00–{buy_end:02d}:00",
                    "Discharge window": f"{sell:02d}:00–{sell_end:02d}:00",
                    "Profit €": format_currency(row.get("profit_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                    "Revenue €": format_currency(row.get("revenue_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                    "Cost €": format_currency(row.get("cost_eur", 0.0), decimals=currency_decimals, thousands=thousands_sep),
                    "Avg buy €/MWh": format_price_per_mwh(
                        row.get("avg_buy_price_eur_mwh"), decimals=max(currency_decimals, 2)
                    ),
                    "Avg sell €/MWh": format_price_per_mwh(
                        row.get("avg_sell_price_eur_mwh"), decimals=max(currency_decimals, 2)
                    ),
                    "Spread €/MWh": format_price_per_mwh(
                        row.get("spread_eur_mwh"), decimals=max(currency_decimals, 2)
                    ),
                }
            )

        year_df = pd.DataFrame(display_years)
        preferred_order = [
            "Year",
            "Charge window",
            "Discharge window",
            "Profit €",
            "Revenue €",
            "Cost €",
            "Avg buy €/MWh",
            "Avg sell €/MWh",
            "Spread €/MWh",
        ]
        year_df = year_df[[col for col in preferred_order if col in year_df.columns]]
        st.dataframe(year_df, width="stretch")
