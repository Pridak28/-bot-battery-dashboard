#!/usr/bin/env python3
"""
Comprehensive verification that all mentioned components are in place and working.
"""

import sys
from pathlib import Path

def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists."""
    exists = Path(path).exists()
    status = "✅" if exists else "❌"
    print(f"  {status} {description}: {path}")
    return exists

def check_damas_data():
    """Verify DAMAS data is present and populated."""
    print("\n📊 DAMAS DATA VERIFICATION")
    print("=" * 70)

    import pandas as pd

    # Check imbalance_history.csv
    csv_path = "data/imbalance_history.csv"
    if not check_file_exists(csv_path, "DAMAS CSV file"):
        return False

    df = pd.read_csv(csv_path)
    print(f"\n  Data Statistics:")
    print(f"    Rows: {len(df):,}")
    print(f"    Date range: {df['date'].min()} to {df['date'].max()}")

    # Check DAMAS columns
    damas_cols = [
        'afrr_up_activated_mwh', 'afrr_down_activated_mwh',
        'afrr_up_price_eur', 'afrr_down_price_eur',
        'mfrr_up_activated_mwh', 'mfrr_down_activated_mwh',
        'mfrr_up_scheduled_price_eur', 'mfrr_down_scheduled_price_eur'
    ]

    print(f"\n  DAMAS Columns:")
    all_present = True
    for col in damas_cols:
        if col in df.columns:
            non_zero = (df[col].fillna(0) != 0).sum()
            pct = non_zero / len(df) * 100
            print(f"    ✅ {col}: {non_zero:,} activations ({pct:.1f}%)")
        else:
            print(f"    ❌ {col}: MISSING")
            all_present = False

    return all_present

def check_order_lifecycle():
    """Verify order lifecycle components."""
    print("\n🔄 ORDER LIFECYCLE VERIFICATION")
    print("=" * 70)

    try:
        from src.execution.order_monitor import OrderMonitor, OrderStatus, OrderInfo
        print("  ✅ OrderMonitor class imported")

        from src.risk.risk_manager import RiskManager, BatteryConfig, RiskConfig
        print("  ✅ RiskManager class imported")

        from src.execution.execution_engine import ExecutionEngine
        print("  ✅ ExecutionEngine class imported")

        # Test that reservation methods exist
        import inspect

        # Check RiskManager methods
        rm_methods = [m for m in dir(RiskManager) if not m.startswith('_')]
        required_rm_methods = ['reserve_for_order', 'release_order', 'execute_order']
        for method in required_rm_methods:
            if method in rm_methods:
                print(f"  ✅ RiskManager.{method}() exists")
            else:
                print(f"  ❌ RiskManager.{method}() MISSING")
                return False

        # Check OrderMonitor methods
        om_methods = [m for m in dir(OrderMonitor) if not m.startswith('_')]
        required_om_methods = ['track_order', 'update_order_status']
        for method in required_om_methods:
            if method in om_methods:
                print(f"  ✅ OrderMonitor.{method}() exists")
            else:
                print(f"  ❌ OrderMonitor.{method}() MISSING")
                return False

        # Check OrderStatus enum
        required_statuses = ['PENDING', 'ACCEPTED', 'FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED']
        for status in required_statuses:
            if hasattr(OrderStatus, status):
                print(f"  ✅ OrderStatus.{status} exists")
            else:
                print(f"  ❌ OrderStatus.{status} MISSING")
                return False

        return True

    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False

def check_fr_simulation():
    """Verify FR simulation components."""
    print("\n⚡ FR SIMULATION VERIFICATION")
    print("=" * 70)

    try:
        from src.web.simulation.frequency_regulation import simulate_frequency_regulation_revenue_multi
        print("  ✅ Main simulation function imported")

        from src.web.ui.fr_simulator import render_frequency_regulation_simulator
        print("  ✅ FR Simulator UI imported")

        from src.web.data.loaders import load_transelectrica_imbalance_from_excel
        print("  ✅ Data loader imported")

        # Test CSV loading
        df = load_transelectrica_imbalance_from_excel('data/imbalance_history.csv')
        if 'afrr_up_activated_mwh' in df.columns:
            print("  ✅ CSV loader preserves DAMAS columns")
        else:
            print("  ❌ CSV loader does NOT preserve DAMAS columns")
            return False

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def check_config():
    """Verify config files."""
    print("\n⚙️  CONFIG FILES VERIFICATION")
    print("=" * 70)

    all_good = True
    all_good &= check_file_exists("config.yaml", "Main config")

    try:
        from src.web.data import load_config
        cfg = load_config("config.yaml")

        # Check key sections
        required_sections = ['battery', 'data', 'risk', 'fr_products']
        for section in required_sections:
            if section in cfg:
                print(f"  ✅ Config section '{section}' present")
            else:
                print(f"  ❌ Config section '{section}' MISSING")
                all_good = False

        # Check data paths
        if 'data' in cfg:
            pzu_csv = cfg['data'].get('pzu_forecast_csv')
            bm_csv = cfg['data'].get('bm_forecast_csv')
            print(f"\n  Data paths:")
            print(f"    PZU CSV: {pzu_csv}")
            print(f"    BM CSV: {bm_csv}")

            # Check if paths exist
            if bm_csv:
                if Path(bm_csv).exists():
                    print(f"    ✅ BM CSV exists")
                else:
                    print(f"    ⚠️  BM CSV not found (may need to adjust path)")

    except Exception as e:
        print(f"  ❌ Config loading failed: {e}")
        all_good = False

    return all_good

def main():
    """Run all verifications."""
    print("🔍 SYSTEM STATE VERIFICATION")
    print("=" * 70)
    print()

    results = {
        "DAMAS Data": check_damas_data(),
        "Order Lifecycle": check_order_lifecycle(),
        "FR Simulation": check_fr_simulation(),
        "Config Files": check_config(),
    }

    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)

    for component, status in results.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {component}")

    all_pass = all(results.values())

    if all_pass:
        print("\n✅ ALL SYSTEMS OPERATIONAL")
        return 0
    else:
        print("\n❌ SOME ISSUES FOUND - Review output above")
        return 1

if __name__ == '__main__':
    sys.exit(main())
