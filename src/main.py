from __future__ import annotations

import argparse
from pathlib import Path
import yaml

import matplotlib.pyplot as plt
import pandas as pd

from .strategy.horizon import (
    compute_best_fixed_cycle,
    load_pzu_daily_history,
    summarize_profit_windows,
)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _format_currency(value: float) -> str:
    return f"€{value:,.0f}" if value is not None else "—"


def main() -> None:
    parser = argparse.ArgumentParser(description="PZU multi-horizon profitability summary")
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file")
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Save a chart showing daily and cumulative profits",
    )
    parser.add_argument(
        "--plot-file",
        default=None,
        help="Destination for the optional chart (defaults to out/pzu_horizons.png)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)

    battery_cfg = cfg.get("battery", {})
    pzu_csv = cfg.get("data", {}).get("pzu_forecast_csv")
    capacity_mwh = float(battery_cfg.get("capacity_mwh", 0.0))
    power_mw = float(battery_cfg.get("power_mw", 0.0))
    eta_rt = float(battery_cfg.get("round_trip_efficiency", 1.0))

    daily_history = load_pzu_daily_history(
        pzu_csv,
        capacity_mwh,
        eta_rt,
        power_mw=power_mw,
        start_date=None,
    )
    if daily_history.empty:
        path_display = pzu_csv or "<missing path>"
        print(f"No historical PZU data found at {path_display}. Nothing to summarise.")
        return

    summaries = summarize_profit_windows(daily_history)

    fixed_cycle = compute_best_fixed_cycle(
        pzu_csv,
        capacity_mwh,
        power_mw,
        eta_rt,
    )
    fixed_history = fixed_cycle.get("daily_history", pd.DataFrame())
    fixed_summaries = summarize_profit_windows(fixed_history) if isinstance(fixed_history, pd.DataFrame) and not fixed_history.empty else []

    start_date = daily_history["date"].min().date()
    end_date = daily_history["date"].max().date()
    print(f"History coverage: {start_date} → {end_date} ({len(daily_history)} full days)\n")

    header = f"{'Period':<15}{'Days':>6}{'Cov%':>8}{'Recent€':>14}{'Avg€/day':>14}{'Win%':>8}{'Best€':>14}{'Worst€':>14}"
    print(header)
    print("-" * len(header))

    for summary in summaries:
        days = summary["recent_days"]
        if days == 0:
            print(f"{summary['period_label']:<15}{0:>6}{'—':>8}{'—':>14}{'—':>14}{'—':>8}{'—':>14}{'—':>14}")
            continue

        coverage = summary.get("coverage_ratio")
        coverage_str = f"{coverage * 100:7.1f}%" if coverage is not None else "       —"
        win_rate = summary.get("recent_success_rate")
        win_str = f"{win_rate:7.1f}%" if win_rate is not None else "       —"
        best_total = summary.get("best_window_total_eur")
        worst_total = summary.get("worst_window_total_eur")
        best_str = f"{best_total:14.0f}" if best_total is not None else f"{'—':>14}"
        worst_str = f"{worst_total:14.0f}" if worst_total is not None else f"{'—':>14}"

        print(
            f"{summary['period_label']:<15}"
            f"{days:>6}"
            f"{coverage_str}"
            f"{summary['recent_total_eur']:>14.0f}"
            f"{summary['recent_avg_eur']:>14.0f}"
            f"{win_str}"
            f"{best_str}"
            f"{worst_str}"
        )

    print()

    buy_start = fixed_cycle.get("buy_start_hour")
    sell_start = fixed_cycle.get("sell_start_hour")
    if buy_start is not None and sell_start is not None:
        buy_end = min(buy_start + 2, 24)
        sell_end = min(sell_start + 2, 24)
        print("Best fixed 2h cycle across history")
        print(f"  Charge window : {buy_start:02d}:00–{buy_end:02d}:00")
        print(f"  Discharge window: {sell_start:02d}:00–{sell_end:02d}:00")
        stats = fixed_cycle.get("stats", {})
        print(
            f"  Total profit : {_format_currency(stats.get('total_profit_eur', 0.0))}"
            f" (avg {_format_currency(stats.get('average_profit_eur', 0.0))}/day)"
        )
        total_days = stats.get("total_days", 0)
        pos_days = stats.get("positive_days", 0)
        print(f"  Winning days : {pos_days}/{total_days}")

        if fixed_summaries:
            print()
            print("Fixed-cycle horizons:")
            header = f"{'Period':<15}{'Days':>6}{'Cov%':>8}{'Recent€':>14}{'Avg€/day':>14}{'Win%':>8}{'Best€':>14}{'Worst€':>14}"
            print(header)
            print("-" * len(header))
            for summary in fixed_summaries:
                days = summary["recent_days"]
                coverage = summary.get("coverage_ratio")
                coverage_str = f"{coverage * 100:7.1f}%" if coverage is not None else "       —"
                win_rate = summary.get("recent_success_rate")
                win_str = f"{win_rate:7.1f}%" if win_rate is not None else "       —"
                best_total = summary.get("best_window_total_eur")
                worst_total = summary.get("worst_window_total_eur")
                best_str = f"{best_total:14.0f}" if best_total is not None else f"{'—':>14}"
                worst_str = f"{worst_total:14.0f}" if worst_total is not None else f"{'—':>14}"
                print(
                    f"{summary['period_label']:<15}"
                    f"{days:>6}"
                    f"{coverage_str}"
                    f"{summary['recent_total_eur']:>14.0f}"
                    f"{summary['recent_avg_eur']:>14.0f}"
                    f"{win_str}"
                    f"{best_str}"
                    f"{worst_str}"
                )


    if args.plot:
        history_sorted = daily_history.sort_values("date")
        dates = history_sorted["date"].dt.to_pydatetime()
        profits = history_sorted["daily_profit_eur"]
        cumulative = profits.cumsum()

        fig, ax1 = plt.subplots(figsize=(12, 5))
        ax1.bar(dates, profits, color="tab:blue", alpha=0.55, label="Daily profit")
        ax1.set_ylabel("Daily profit (EUR)")
        ax1.set_xlabel("Date")
        ax1.grid(True, alpha=0.3)

        ax2 = ax1.twinx()
        ax2.plot(dates, cumulative, color="tab:orange", label="Cumulative")
        ax2.set_ylabel("Cumulative profit (EUR)")

        # Combine legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

        fig.autofmt_xdate()
        plt.title("PZU Daily & Cumulative Profitability")

        out_path = Path(args.plot_file or "out/pzu_horizons.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(out_path, dpi=150)
        plt.close()
        print(f"Saved horizon chart to {out_path}")


if __name__ == "__main__":
    main()
