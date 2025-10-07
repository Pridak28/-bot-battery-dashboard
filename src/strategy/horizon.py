from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Constants for two-hour cycle length.
_BLOCK_HOURS = 2
_MIN_REQUIRED_HOURS = _BLOCK_HOURS * 2  # need at least 4 hourly prices per day


def load_pzu_daily_history(
    pzu_csv: Optional[str],
    capacity_mwh: float,
    round_trip_efficiency: float,
    min_hours_per_day: int = 24,
    *,
    power_mw: Optional[float] = None,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """Compatibility wrapper that supports the historic signature.

    Parameters
    ----------
    pzu_csv : optional str
        Path to CSV with columns date, hour, price.
    capacity_mwh : float
        Battery energy capacity.
    round_trip_efficiency : float
        Round-trip efficiency (0-1).
    min_hours_per_day : int, optional
        Minimum hours required per day, default 24.
    power_mw : optional float, keyword-only
        Battery power in MW. If omitted, defaults to capacity-based value so
        legacy callers still receive results similar to the previous logic.
    """

    if power_mw is None:
        # Legacy behaviour: assume the battery can move its full capacity in
        # the 2-hour block, which mirrors the prior net-spread calculation.
        power_mw = float(capacity_mwh)

    return _load_two_hour_history(
        pzu_csv=pzu_csv,
        capacity_mwh=capacity_mwh,
        power_mw=power_mw,
        round_trip_efficiency=round_trip_efficiency,
        min_hours_per_day=min_hours_per_day,
        start_date=start_date,
        end_date=end_date,
    )


def _load_two_hour_history(
    pzu_csv: Optional[str],
    capacity_mwh: float,
    power_mw: float,
    round_trip_efficiency: float,
    min_hours_per_day: int = 24,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """Return per-day profitability for a 2h charge + 2h discharge strategy."""
    base_columns = [
        "date",
        "hours_count",
        "min_price_eur_mwh",
        "max_price_eur_mwh",
        "daily_profit_eur",
        "daily_revenue_eur",
        "daily_cost_eur",
        "charge_energy_mwh",
        "discharge_energy_mwh",
        "buy_start_hour",
        "sell_start_hour",
        "buy_avg_price_eur_mwh",
        "sell_avg_price_eur_mwh",
        "volatility_eur_mwh",
    ]

    daily_price_lists = _prepare_daily_prices(
        pzu_csv,
        min_hours_per_day,
        start_date=start_date,
        end_date=end_date,
    )
    if not daily_price_lists:
        return pd.DataFrame(columns=base_columns)

    eta = max(float(round_trip_efficiency), 1e-6)
    power_mw = max(float(power_mw), 0.0)
    capacity_mwh = max(float(capacity_mwh), 0.0)

    if power_mw <= 0.0 or capacity_mwh <= 0.0:
        return pd.DataFrame(columns=base_columns)

    daily_rows: List[Dict[str, object]] = []

    for day, prices in daily_price_lists:
        best = _evaluate_two_by_two_cycle(prices, capacity_mwh, power_mw, eta)
        daily_rows.append(
            {
                "date": pd.Timestamp(day),
                "hours_count": int(len(prices)),
                "min_price_eur_mwh": float(np.min(prices)),
                "max_price_eur_mwh": float(np.max(prices)),
                "daily_profit_eur": float(best["profit_eur"]),
                "daily_revenue_eur": float(best["revenue_eur"]),
                "daily_cost_eur": float(best["cost_eur"]),
                "charge_energy_mwh": float(best["charge_energy_mwh"]),
                "discharge_energy_mwh": float(best["discharge_energy_mwh"]),
                "buy_start_hour": best["buy_start_hour"],
                "sell_start_hour": best["sell_start_hour"],
                "buy_avg_price_eur_mwh": best["buy_avg_price_eur_mwh"],
                "sell_avg_price_eur_mwh": best["sell_avg_price_eur_mwh"],
                "volatility_eur_mwh": float(np.std(prices)) if len(prices) > 1 else 0.0,
            }
        )

    if not daily_rows:
        return pd.DataFrame(columns=base_columns)

    daily_history = pd.DataFrame(daily_rows).sort_values("date").reset_index(drop=True)
    return daily_history


def compute_best_fixed_cycle(
    pzu_csv: Optional[str],
    capacity_mwh: float,
    power_mw: float,
    round_trip_efficiency: float,
    min_hours_per_day: int = 24,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
) -> Dict[str, object]:
    """Determine the single best 2h charge/2h discharge schedule across history.

    Returns a dictionary with the chosen schedule and a daily DataFrame under
    ``daily_history`` that can be fed into :func:`summarize_profit_windows`.
    """

    daily_price_lists = _prepare_daily_prices(
        pzu_csv,
        min_hours_per_day,
        start_date=start_date,
        end_date=end_date,
    )
    if not daily_price_lists:
        return {
            "buy_start_hour": None,
            "sell_start_hour": None,
            "charge_energy_mwh": 0.0,
            "discharge_energy_mwh": 0.0,
            "daily_history": pd.DataFrame(
                columns=[
                    "date",
                    "daily_profit_eur",
                    "daily_revenue_eur",
                    "daily_cost_eur",
                    "charge_energy_mwh",
                    "discharge_energy_mwh",
                ]
            ),
            "stats": {},
        }

    eta = max(float(round_trip_efficiency), 1e-6)
    power_mw = max(float(power_mw), 0.0)
    capacity_mwh = max(float(capacity_mwh), 0.0)

    if power_mw <= 0.0 or capacity_mwh <= 0.0:
        return {
            "buy_start_hour": None,
            "sell_start_hour": None,
            "charge_energy_mwh": 0.0,
            "discharge_energy_mwh": 0.0,
            "daily_history": pd.DataFrame(),
            "stats": {},
        }

    charge_energy = min(capacity_mwh, power_mw * _BLOCK_HOURS)
    discharge_energy = charge_energy * eta
    charge_power = charge_energy / _BLOCK_HOURS
    discharge_power = discharge_energy / _BLOCK_HOURS

    if discharge_power <= 0.0:
        return {
            "buy_start_hour": None,
            "sell_start_hour": None,
            "charge_energy_mwh": charge_energy,
            "discharge_energy_mwh": discharge_energy,
            "daily_history": pd.DataFrame(),
            "stats": {},
        }

    best_pair: Optional[Tuple[int, int]] = None
    best_total_profit: Optional[float] = None
    best_days = 0

    for buy_start in range(0, 24 - _BLOCK_HOURS):
        for sell_start in range(buy_start + _BLOCK_HOURS, 24 - _BLOCK_HOURS + 1):
            total_profit = 0.0
            days_count = 0
            for _, prices in daily_price_lists:
                if sell_start + _BLOCK_HOURS > len(prices):
                    continue
                cost = charge_power * sum(prices[buy_start : buy_start + _BLOCK_HOURS])
                revenue = discharge_power * sum(prices[sell_start : sell_start + _BLOCK_HOURS])
                total_profit += revenue - cost
                days_count += 1

            if days_count == 0:
                continue

            if best_total_profit is None or total_profit > best_total_profit:
                best_total_profit = total_profit
                best_pair = (buy_start, sell_start)
                best_days = days_count

    if best_pair is None:
        return {
            "buy_start_hour": None,
            "sell_start_hour": None,
            "charge_energy_mwh": charge_energy,
            "discharge_energy_mwh": discharge_energy,
            "daily_history": pd.DataFrame(),
            "stats": {},
        }

    buy_start, sell_start = best_pair
    daily_rows: List[Dict[str, object]] = []
    positive_days = 0
    negative_days = 0
    for day, prices in daily_price_lists:
        if sell_start + _BLOCK_HOURS > len(prices):
            continue
        buy_block = prices[buy_start : buy_start + _BLOCK_HOURS]
        sell_block = prices[sell_start : sell_start + _BLOCK_HOURS]
        cost = charge_power * sum(buy_block)
        revenue = discharge_power * sum(sell_block)
        profit = revenue - cost
        if profit > 0:
            positive_days += 1
        elif profit < 0:
            negative_days += 1
        daily_rows.append(
            {
                "date": pd.Timestamp(day),
                "daily_profit_eur": float(profit),
                "daily_revenue_eur": float(revenue),
                "daily_cost_eur": float(cost),
                "charge_energy_mwh": float(charge_energy),
                "discharge_energy_mwh": float(discharge_energy),
            }
        )

    daily_history = pd.DataFrame(daily_rows).sort_values("date").reset_index(drop=True)

    if daily_history.empty:
        total_profit = 0.0
        average_profit = 0.0
        total_revenue = 0.0
        total_cost = 0.0
        total_loss = 0.0
        total_charge_energy = 0.0
        total_discharge_energy = 0.0
        avg_buy_price = None
        avg_sell_price = None
        spread_price = None
    else:
        total_profit = float(daily_history["daily_profit_eur"].sum())
        average_profit = float(daily_history["daily_profit_eur"].mean())
        total_revenue = float(daily_history["daily_revenue_eur"].sum())
        total_cost = float(daily_history["daily_cost_eur"].sum())

        losing_mask = daily_history["daily_profit_eur"] < 0
        total_loss = float(-daily_history.loc[losing_mask, "daily_profit_eur"].sum())
        total_loss = abs(total_loss)

        total_charge_energy = float(daily_history["charge_energy_mwh"].sum()) if "charge_energy_mwh" in daily_history else 0.0
        total_discharge_energy = float(daily_history["discharge_energy_mwh"].sum()) if "discharge_energy_mwh" in daily_history else 0.0

        avg_buy_price = float(total_cost / total_charge_energy) if total_charge_energy > 0 else None
        avg_sell_price = float(total_revenue / total_discharge_energy) if total_discharge_energy > 0 else None
        spread_price = float(avg_sell_price - avg_buy_price) if avg_sell_price is not None and avg_buy_price is not None else None

    stats = {
        "total_profit_eur": total_profit,
        "average_profit_eur": average_profit,
        "total_revenue_eur": total_revenue,
        "total_cost_eur": total_cost,
        "total_loss_eur": total_loss,
        "total_charge_energy": total_charge_energy,
        "total_discharge_energy": total_discharge_energy,
        "avg_buy_price_eur_mwh": avg_buy_price,
        "avg_sell_price_eur_mwh": avg_sell_price,
        "spread_eur_mwh": spread_price,
        "positive_days": int(positive_days),
        "negative_days": int(negative_days),
        "total_days": int(best_days),
    }

    return {
        "buy_start_hour": buy_start,
        "sell_start_hour": sell_start,
        "charge_energy_mwh": float(charge_energy),
        "discharge_energy_mwh": float(discharge_energy),
        "daily_history": daily_history,
        "stats": stats,
    }


def _period_cutoff(last_date: pd.Timestamp, offset: object) -> pd.Timestamp:
    if last_date is pd.NaT:
        return last_date
    if isinstance(offset, pd.Timedelta):
        # Include the current day by adding one day before applying the cutoff.
        return last_date - offset + pd.Timedelta(days=1)
    if isinstance(offset, pd.DateOffset):
        return last_date - offset
    if isinstance(offset, (int, float)):
        return last_date - pd.Timedelta(days=float(offset))
    raise TypeError(f"Unsupported offset type: {type(offset).__name__}")


def summarize_profit_windows(daily_history: pd.DataFrame) -> List[Dict[str, object]]:
    """Summarise profitability across fixed rolling windows (30d → 3y)."""
    if daily_history.empty:
        return []

    history = daily_history.sort_values("date").reset_index(drop=True)
    profits = history["daily_profit_eur"]
    revenue = history.get("daily_revenue_eur")
    cost = history.get("daily_cost_eur")
    last_date = history["date"].iloc[-1]

    periods: List[Tuple[str, object]] = [
        ("1 day", pd.Timedelta(days=1)),
        ("30 days", pd.Timedelta(days=30)),
        ("60 days", pd.Timedelta(days=60)),
        ("90 days", pd.Timedelta(days=90)),
        ("6 months", pd.DateOffset(months=6)),
        ("12 months", pd.DateOffset(months=12)),
        ("2 years", pd.DateOffset(years=2)),
        ("3 years", pd.DateOffset(years=3)),
    ]

    results: List[Dict[str, object]] = []

    for label, offset in periods:
        try:
            cutoff = _period_cutoff(last_date, offset)
        except TypeError:
            continue

        if cutoff is pd.NaT:
            recent = history.copy()
        else:
            recent = history[history["date"] >= cutoff]

        recent_len = len(recent)
        if recent_len == 0:
            results.append(
                {
                    "period_label": label,
                    "recent_days": 0,
                    "expected_days": None,
                    "coverage_ratio": 0.0,
                    "recent_total_eur": 0.0,
                    "recent_avg_eur": 0.0,
                    "recent_success_rate": 0.0,
                    "recent_max_day_profit_eur": None,
                    "recent_min_day_profit_eur": None,
                    "best_window_total_eur": None,
                    "best_window_start": None,
                    "best_window_end": None,
                    "best_window_success_rate": None,
                    "worst_window_total_eur": None,
                    "worst_window_start": None,
                    "worst_window_end": None,
                    "worst_window_success_rate": None,
                    "window_size_days": 0,
                }
            )
            continue

        if cutoff is pd.NaT:
            expected_days = recent_len
        else:
            expected_days = max((last_date - cutoff).days + 1, 1)

        coverage_ratio = recent_len / expected_days if expected_days else 0.0
        recent_total = float(recent["daily_profit_eur"].sum())
        recent_avg = float(recent["daily_profit_eur"].mean())
        success_rate = float((recent["daily_profit_eur"] > 0).mean() * 100)
        max_day = float(recent["daily_profit_eur"].max())
        min_day = float(recent["daily_profit_eur"].min())
        losing_mask = recent["daily_profit_eur"] < 0
        recent_loss = float(-recent.loc[losing_mask, "daily_profit_eur"].sum())
        recent_loss = abs(recent_loss)

        window_size = recent_len
        best_total = best_start = best_end = best_success = None
        worst_total = worst_start = worst_end = worst_success = None

        if window_size > 0:
            rolling = profits.rolling(window_size).sum()
            valid = rolling.dropna()
            if not valid.empty:
                best_idx = int(valid.idxmax())
                best_total = float(rolling.iloc[best_idx])
                best_start_idx = max(best_idx - window_size + 1, 0)
                best_slice = history.iloc[best_start_idx : best_idx + 1]
                best_start = best_slice.iloc[0]["date"]
                best_end = best_slice.iloc[-1]["date"]
                best_success = float((best_slice["daily_profit_eur"] > 0).mean() * 100)

                worst_idx = int(valid.idxmin())
                worst_total = float(rolling.iloc[worst_idx])
                worst_start_idx = max(worst_idx - window_size + 1, 0)
                worst_slice = history.iloc[worst_start_idx : worst_idx + 1]
                worst_start = worst_slice.iloc[0]["date"]
                worst_end = worst_slice.iloc[-1]["date"]
                worst_success = float((worst_slice["daily_profit_eur"] > 0).mean() * 100)

        projection_multiplier = None
        if expected_days and recent_len > 0 and expected_days > recent_len:
            projection_multiplier = expected_days / recent_len

        summary = {
            "period_label": label,
            "recent_days": recent_len,
            "expected_days": expected_days,
            "coverage_ratio": coverage_ratio,
            "recent_total_eur": recent_total,
            "recent_avg_eur": recent_avg,
            "recent_success_rate": success_rate,
            "recent_max_day_profit_eur": max_day,
            "recent_min_day_profit_eur": min_day,
            "recent_loss_eur": recent_loss,
            "best_window_total_eur": best_total,
            "best_window_start": best_start,
            "best_window_end": best_end,
            "best_window_success_rate": best_success,
            "worst_window_total_eur": worst_total,
            "worst_window_start": worst_start,
            "worst_window_end": worst_end,
            "worst_window_success_rate": worst_success,
            "window_size_days": window_size,
        }

        if projection_multiplier and projection_multiplier > 1.0:
            summary["projected_total_eur"] = recent_total * projection_multiplier
            summary["projected_avg_eur"] = recent_avg
            summary["projected_loss_eur"] = recent_loss * projection_multiplier

        
        if revenue is not None:
            recent_revenue = float(revenue.iloc[-recent_len:].sum()) if recent_len else 0.0
            summary["recent_revenue_eur"] = recent_revenue
        else:
            recent_revenue = None
        if cost is not None:
            recent_cost = float(cost.iloc[-recent_len:].sum()) if recent_len else 0.0
            summary["recent_cost_eur"] = recent_cost
        else:
            recent_cost = None

        if (
            recent_revenue is not None
            and recent_cost is not None
            and "charge_energy_mwh" in recent
            and "discharge_energy_mwh" in recent
        ):
            total_charge = float(recent["charge_energy_mwh"].sum())
            total_discharge = float(recent["discharge_energy_mwh"].sum())
            avg_buy = float(recent_cost / total_charge) if total_charge > 0 else None
            avg_sell = float(recent_revenue / total_discharge) if total_discharge > 0 else None
            if avg_buy is not None:
                summary["recent_avg_buy_price_eur_mwh"] = avg_buy
            if avg_sell is not None:
                summary["recent_avg_sell_price_eur_mwh"] = avg_sell
            if avg_buy is not None and avg_sell is not None:
                spread = float(avg_sell - avg_buy)
                summary["recent_spread_eur_mwh"] = spread
                if projection_multiplier and projection_multiplier > 1.0:
                    summary["projected_avg_buy_price_eur_mwh"] = avg_buy
                    summary["projected_avg_sell_price_eur_mwh"] = avg_sell
                    summary["projected_spread_eur_mwh"] = spread

        if projection_multiplier and projection_multiplier > 1.0:
            if revenue is not None:
                summary["projected_revenue_eur"] = recent_revenue * projection_multiplier
            if cost is not None:
                summary["projected_cost_eur"] = recent_cost * projection_multiplier

        results.append(summary)

    return results


def _evaluate_two_by_two_cycle(
    prices: List[float],
    capacity_mwh: float,
    power_mw: float,
    eta: float,
) -> Dict[str, object]:
    n = len(prices)
    if n < _MIN_REQUIRED_HOURS:
        return _empty_cycle_result()

    charge_energy = min(capacity_mwh, power_mw * _BLOCK_HOURS)
    if charge_energy <= 0.0:
        return _empty_cycle_result()

    discharge_energy = charge_energy * eta
    charge_power = charge_energy / _BLOCK_HOURS
    discharge_power = discharge_energy / _BLOCK_HOURS
    if discharge_power <= 0.0:
        return _empty_cycle_result(charge_energy_mwh=charge_energy, discharge_energy_mwh=discharge_energy)

    best_profit = None
    best: Optional[Dict[str, object]] = None

    # Last buy start must leave room for a two-hour discharge afterwards.
    last_buy_start = n - (_BLOCK_HOURS + _BLOCK_HOURS)
    for buy_start in range(0, last_buy_start + 1):
        buy_block = prices[buy_start : buy_start + _BLOCK_HOURS]
        cost = charge_power * sum(buy_block)
        buy_avg = float(np.mean(buy_block))

        for sell_start in range(buy_start + _BLOCK_HOURS, n - _BLOCK_HOURS + 1):
            sell_block = prices[sell_start : sell_start + _BLOCK_HOURS]
            revenue = discharge_power * sum(sell_block)
            profit = revenue - cost

            if best_profit is None or profit > best_profit:
                best_profit = profit
                best = {
                    "profit_eur": float(profit),
                    "revenue_eur": float(revenue),
                    "cost_eur": float(cost),
                    "charge_energy_mwh": float(charge_energy),
                    "discharge_energy_mwh": float(discharge_energy),
                    "buy_start_hour": int(buy_start),
                    "sell_start_hour": int(sell_start),
                    "buy_avg_price_eur_mwh": float(buy_avg),
                    "sell_avg_price_eur_mwh": float(np.mean(sell_block)),
                }

    if best is None:
        return _empty_cycle_result(charge_energy_mwh=charge_energy, discharge_energy_mwh=discharge_energy)

    return best


def _empty_cycle_result(
    *,
    charge_energy_mwh: float = 0.0,
    discharge_energy_mwh: float = 0.0,
) -> Dict[str, object]:
    return {
        "profit_eur": 0.0,
        "revenue_eur": 0.0,
        "cost_eur": 0.0,
        "charge_energy_mwh": float(charge_energy_mwh),
        "discharge_energy_mwh": float(discharge_energy_mwh),
        "buy_start_hour": None,
        "sell_start_hour": None,
        "buy_avg_price_eur_mwh": None,
        "sell_avg_price_eur_mwh": None,
    }


def _prepare_daily_prices(
    pzu_csv: Optional[str],
    min_hours_per_day: int,
    *,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
) -> List[Tuple[pd.Timestamp, List[float]]]:
    if not pzu_csv or not Path(pzu_csv).exists():
        return []

    try:
        df = pd.read_csv(pzu_csv)
    except Exception:
        return []

    required_cols = {"date", "hour", "price"}
    if not required_cols.issubset(df.columns):
        return []

    df = df.dropna(subset=["date", "price"])
    if df.empty:
        return []

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return []

    if start_date is not None:
        df = df[df["date"] >= pd.Timestamp(start_date)]
        if df.empty:
            return []

    if end_date is not None:
        df = df[df["date"] <= pd.Timestamp(end_date)]
        if df.empty:
            return []

    day_lists: List[Tuple[pd.Timestamp, List[float]]] = []
    for day, day_df in df.groupby("date"):
        prices = day_df.sort_values("hour")["price"].dropna().to_list()
        if len(prices) < max(min_hours_per_day, _MIN_REQUIRED_HOURS):
            continue
        day_lists.append((pd.Timestamp(day), prices))

    return day_lists


__all__ = [
    "load_pzu_daily_history",
    "load_pzu_price_series",
    "compute_best_fixed_cycle",
    "summarize_profit_windows",
    "compute_best_hours_by_year",
    "compute_pzu_monthly_costs",
]


def compute_best_hours_by_year(
    pzu_csv: Optional[str],
    *,
    round_trip_efficiency: float,
    capacity_mwh: float,
    power_mw: float,
    years: Optional[List[int]] = None,
    min_hours_per_day: int = 24,
) -> pd.DataFrame:
    """Return best charge/discharge hour pairs and profits for each calendar year.

    The function runs the fixed two-hour cycle optimisation for each year separately and
    reports the resulting schedule, annual profit, revenue, cost, and average buy/sell
    prices. Years without sufficient data are omitted from the result.
    """

    if not pzu_csv or not Path(pzu_csv).exists():
        return pd.DataFrame(
            columns=[
                "year",
                "buy_hour",
                "sell_hour",
                "profit_eur",
                "revenue_eur",
                "cost_eur",
                "avg_buy_price_eur_mwh",
                "avg_sell_price_eur_mwh",
                "spread_eur_mwh",
            ]
        )

    try:
        df = pd.read_csv(pzu_csv)
    except Exception:
        return pd.DataFrame()

    required_cols = {"date", "hour", "price"}
    if not required_cols.issubset(df.columns):
        return pd.DataFrame()

    df = df.dropna(subset=["date", "price"])
    if df.empty:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return pd.DataFrame()

    df["year"] = df["date"].dt.year

    if years is None:
        years = sorted(df["year"].unique())
    else:
        years = sorted(set(years))

    results: List[Dict[str, object]] = []

    for year in years:
        year_df = df[df["year"] == year]
        if year_df.empty:
            continue

        year_start = pd.Timestamp(year=year, month=1, day=1)
        year_end = pd.Timestamp(year=year, month=12, day=31)

        cycle = compute_best_fixed_cycle(
            pzu_csv,
            capacity_mwh=capacity_mwh,
            power_mw=power_mw,
            round_trip_efficiency=round_trip_efficiency,
            min_hours_per_day=min_hours_per_day,
            start_date=year_start,
            end_date=year_end,
        )

        stats = cycle.get("stats", {})
        buy_hour = cycle.get("buy_start_hour")
        sell_hour = cycle.get("sell_start_hour")
        if buy_hour is None or sell_hour is None:
            continue

        results.append(
            {
                "year": int(year),
                "buy_hour": int(buy_hour),
                "sell_hour": int(sell_hour),
                "profit_eur": float(stats.get("total_profit_eur", 0.0)),
                "revenue_eur": float(stats.get("total_revenue_eur", 0.0)),
                "cost_eur": float(stats.get("total_cost_eur", 0.0)),
                "avg_buy_price_eur_mwh": stats.get("avg_buy_price_eur_mwh"),
                "avg_sell_price_eur_mwh": stats.get("avg_sell_price_eur_mwh"),
                "spread_eur_mwh": stats.get("spread_eur_mwh"),
            }
        )

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values("year").reset_index(drop=True)



def load_pzu_price_series(
    pzu_csv: Optional[str],
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """Return a daily average price series for charting."""
    if not pzu_csv or not Path(pzu_csv).exists():
        return pd.DataFrame(columns=["date", "avg_price_eur_mwh"])

    try:
        df = pd.read_csv(pzu_csv)
    except Exception:
        return pd.DataFrame(columns=["date", "avg_price_eur_mwh"])

    if "date" not in df.columns or "price" not in df.columns:
        return pd.DataFrame(columns=["date", "avg_price_eur_mwh"])

    df = df.dropna(subset=["date", "price"])
    if df.empty:
        return pd.DataFrame(columns=["date", "avg_price_eur_mwh"])

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return pd.DataFrame(columns=["date", "avg_price_eur_mwh"])

    if start_date is not None:
        df = df[df["date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        df = df[df["date"] <= pd.Timestamp(end_date)]
    if df.empty:
        return pd.DataFrame(columns=["date", "avg_price_eur_mwh"])

    series = (
        df.groupby(df["date"].dt.to_period("D"))["price"].mean().reset_index()
    )
    series["date"] = series["date"].dt.to_timestamp()
    series = series.rename(columns={"price": "avg_price_eur_mwh"})
    return series.sort_values("date").reset_index(drop=True)


def compute_pzu_monthly_costs(
    pzu_csv: Optional[str],
    *,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """Aggregate average OPCOM PZU prices by calendar month."""

    if not pzu_csv or not Path(pzu_csv).exists():
        return pd.DataFrame(columns=["month", "avg_price_eur_mwh", "min_price_eur_mwh", "max_price_eur_mwh"])

    try:
        df = pd.read_csv(pzu_csv)
    except Exception:
        return pd.DataFrame(columns=["month", "avg_price_eur_mwh", "min_price_eur_mwh", "max_price_eur_mwh"])

    required = {"date", "hour", "price"}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=["month", "avg_price_eur_mwh", "min_price_eur_mwh", "max_price_eur_mwh"])

    df = df.dropna(subset=["date", "price"])
    if df.empty:
        return pd.DataFrame(columns=["month", "avg_price_eur_mwh", "min_price_eur_mwh", "max_price_eur_mwh"])

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return pd.DataFrame(columns=["month", "avg_price_eur_mwh", "min_price_eur_mwh", "max_price_eur_mwh"])

    if start_date is not None:
        df = df[df["date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        df = df[df["date"] <= pd.Timestamp(end_date)]
    if df.empty:
        return pd.DataFrame(columns=["month", "avg_price_eur_mwh", "min_price_eur_mwh", "max_price_eur_mwh"])

    df["month"] = df["date"].dt.to_period("M")
    grouped = (
        df.groupby("month")["price"]
        .agg(["mean", "min", "max"])
        .reset_index()
        .rename(columns={"mean": "avg_price_eur_mwh", "min": "min_price_eur_mwh", "max": "max_price_eur_mwh"})
    )
    grouped["month"] = grouped["month"].astype(str)
    return grouped
