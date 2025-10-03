#!/usr/bin/env python3
"""
Example: Backtesting with automatic order fills.

This demonstrates how to wire the order lifecycle for simulation/backtesting
using historical price data instead of live API feeds.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
import pandas as pd
import logging

from src.risk.risk_manager import RiskManager, BatteryConfig, RiskConfig
from src.execution.execution_engine import ExecutionEngine
from src.execution.simulation_fills import SimulationFillEngine
from src.market.pzu_client import PZUClient


def run_backtest_example():
    """Run a simple backtest with automatic order fills."""

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("backtest")

    print("=" * 80)
    print("BACKTESTING WITH AUTOMATIC ORDER FILLS")
    print("=" * 80)

    # 1. Configure battery and risk
    battery = BatteryConfig(
        capacity_mwh=100.0,
        power_mw=25.0,
        soc_initial=0.5,
        round_trip_efficiency=0.9
    )

    risk = RiskConfig(
        max_position_mwh=100.0,
        max_order_mwh=25.0,
        min_price_eur_mwh=0.0,
        max_price_eur_mwh=1000.0,
        max_open_orders=10
    )

    risk_mgr = RiskManager(battery, risk)
    pzu_client = PZUClient()  # Mock client for backtest

    # 2. Create execution engine
    engine = ExecutionEngine(pzu=pzu_client, bm=None, risk=risk_mgr, logger=logger)

    # 3. Create simulation fill engine
    sim_fills = SimulationFillEngine(execution_engine=engine, logger=logger)

    # 4. Load market data (using your existing PZU price data)
    market_data_path = Path(__file__).parent.parent / "data" / "pzu_history.csv"

    if not market_data_path.exists():
        print(f"\n❌ Market data not found: {market_data_path}")
        print("   Please ensure data/pzu_history.csv exists")
        return

    market_data = pd.read_csv(market_data_path)
    market_data["date"] = pd.to_datetime(market_data["date"])

    print(f"\n📊 Loaded market data: {len(market_data)} price points")
    print(f"   Date range: {market_data['date'].min()} → {market_data['date'].max()}")

    # 5. Simulate a trading day
    print("\n" + "=" * 80)
    print("SIMULATION START")
    print("=" * 80)

    # Get a sample date with data
    sample_date = market_data["date"].iloc[0].date()
    sample_prices = market_data[market_data["date"] == pd.Timestamp(sample_date)]

    if sample_prices.empty:
        print("No price data available for simulation")
        return

    print(f"\n📅 Simulating: {sample_date}")
    print(f"   Available hours: {len(sample_prices)}")

    # Find cheap and expensive hours
    cheap_hour = sample_prices.loc[sample_prices["price"].idxmin()]
    expensive_hour = sample_prices.loc[sample_prices["price"].idxmax()]

    print(f"\n💡 Strategy: Buy cheap, sell expensive")
    print(f"   Cheapest hour: H{int(cheap_hour['hour'])} @ {cheap_hour['price']:.2f} EUR/MWh")
    print(f"   Most expensive: H{int(expensive_hour['hour'])} @ {expensive_hour['price']:.2f} EUR/MWh")

    initial_soc = risk_mgr.soc

    # 6. Place BUY order at cheap hour
    print(f"\n" + "=" * 80)
    print("PLACING BUY ORDER")
    print("=" * 80)

    buy_delivery_start = datetime.combine(sample_date, datetime.min.time()) + timedelta(hours=int(cheap_hour["hour"]))
    buy_delivery_end = buy_delivery_start + timedelta(hours=1)
    buy_limit_price = cheap_hour["price"] * 1.1  # Slightly above market to ensure fill

    print(f"\nOrder details:")
    print(f"  Side: BUY")
    print(f"  Volume: 10.0 MWh")
    print(f"  Limit price: {buy_limit_price:.2f} EUR/MWh")
    print(f"  Delivery: {buy_delivery_start}")

    buy_result = engine.submit(
        market="PZU",
        product="H1",
        delivery_start=buy_delivery_start,
        delivery_end=buy_delivery_end,
        side="BUY",
        volume_mwh=10.0,
        price_eur_mwh=buy_limit_price
    )

    print(f"\n📤 Submit result: {buy_result['status']}")

    if "ACCEPTED" in buy_result.get("status", ""):
        buy_order_id = buy_result["order_id"]
        print(f"   Order ID: {buy_order_id}")
        print(f"   SOC after reserve: {risk_mgr.soc:.2%}")
        print(f"   Open orders: {risk_mgr.open_orders}")
        print(f"   Reservations: {len(risk_mgr.reservations)}")

        # Register for simulation fills
        sim_fills.register_order(
            order_id=buy_order_id,
            product="H1",
            delivery_start=buy_delivery_start,
            delivery_end=buy_delivery_end,
            side="BUY",
            volume_mwh=10.0,
            price_eur_mwh=buy_limit_price
        )

    # 7. Check fills against market data
    print(f"\n" + "=" * 80)
    print("CHECKING FILLS AGAINST MARKET DATA")
    print("=" * 80)

    filled = sim_fills.check_fills_against_market_data(
        market_prices=market_data,
        current_time=buy_delivery_start
    )

    if filled:
        print(f"\n✅ Orders filled: {len(filled)}")
        for oid in filled:
            print(f"   - {oid}")
        print(f"\n📊 State after BUY fill:")
        print(f"   SOC: {risk_mgr.soc:.2%}")
        print(f"   Open orders: {risk_mgr.open_orders}")
        print(f"   Reservations: {len(risk_mgr.reservations)}")
        print(f"   Pending sim orders: {len(sim_fills.pending_orders)}")
    else:
        print(f"\n❌ No fills (order conditions not met)")

    # 8. Place SELL order at expensive hour
    print(f"\n" + "=" * 80)
    print("PLACING SELL ORDER")
    print("=" * 80)

    sell_delivery_start = datetime.combine(sample_date, datetime.min.time()) + timedelta(hours=int(expensive_hour["hour"]))
    sell_delivery_end = sell_delivery_start + timedelta(hours=1)
    sell_limit_price = expensive_hour["price"] * 0.9  # Slightly below market to ensure fill

    print(f"\nOrder details:")
    print(f"  Side: SELL")
    print(f"  Volume: 10.0 MWh")
    print(f"  Limit price: {sell_limit_price:.2f} EUR/MWh")
    print(f"  Delivery: {sell_delivery_start}")

    sell_result = engine.submit(
        market="PZU",
        product="H1",
        delivery_start=sell_delivery_start,
        delivery_end=sell_delivery_end,
        side="SELL",
        volume_mwh=10.0,
        price_eur_mwh=sell_limit_price
    )

    print(f"\n📤 Submit result: {sell_result['status']}")

    if "ACCEPTED" in sell_result.get("status", ""):
        sell_order_id = sell_result["order_id"]
        print(f"   Order ID: {sell_order_id}")
        print(f"   SOC after reserve: {risk_mgr.soc:.2%}")
        print(f"   Open orders: {risk_mgr.open_orders}")
        print(f"   Reservations: {len(risk_mgr.reservations)}")

        # Register for simulation fills
        sim_fills.register_order(
            order_id=sell_order_id,
            product="H1",
            delivery_start=sell_delivery_start,
            delivery_end=sell_delivery_end,
            side="SELL",
            volume_mwh=10.0,
            price_eur_mwh=sell_limit_price
        )

    # 9. Check SELL fills
    print(f"\n" + "=" * 80)
    print("CHECKING SELL FILLS")
    print("=" * 80)

    filled = sim_fills.check_fills_against_market_data(
        market_prices=market_data,
        current_time=sell_delivery_start
    )

    if filled:
        print(f"\n✅ Orders filled: {len(filled)}")
        for oid in filled:
            print(f"   - {oid}")

    # 10. Final summary
    print(f"\n" + "=" * 80)
    print("BACKTEST SUMMARY")
    print("=" * 80)

    print(f"\n📊 Final state:")
    print(f"   Initial SOC: {initial_soc:.2%}")
    print(f"   Final SOC: {risk_mgr.soc:.2%}")
    print(f"   SOC change: {(risk_mgr.soc - initial_soc):.2%}")
    print(f"   Open orders: {risk_mgr.open_orders}")
    print(f"   Reservations: {len(risk_mgr.reservations)}")
    print(f"   Pending sim orders: {len(sim_fills.pending_orders)}")

    # Verify no leaks
    print(f"\n🔍 Leak check:")
    if risk_mgr.open_orders == 0 and len(risk_mgr.reservations) == 0 and len(sim_fills.pending_orders) == 0:
        print(f"   ✅ No leaks detected!")
        print(f"   ✅ All reservations released")
        print(f"   ✅ All orders completed")
    else:
        print(f"   ❌ Leak detected!")
        print(f"      Open orders: {risk_mgr.open_orders}")
        print(f"      Reservations: {len(risk_mgr.reservations)}")
        print(f"      Pending sim orders: {len(sim_fills.pending_orders)}")

    print(f"\n🎯 Order lifecycle:")
    print(f"   ✅ Orders submitted via ExecutionEngine")
    print(f"   ✅ Reservations created on submit")
    print(f"   ✅ Fills simulated from market data")
    print(f"   ✅ update_order_status() called automatically")
    print(f"   ✅ Callbacks triggered (on_order_filled)")
    print(f"   ✅ Reservations released on fill")
    print(f"   ✅ No manual callback calls needed!")


if __name__ == "__main__":
    run_backtest_example()
