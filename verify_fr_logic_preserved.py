#!/usr/bin/env python3
"""
Verify that the FR Simulator logic was preserved during refactoring.
Compares key sections between original app.py.backup and new fr_simulator.py.
"""

import re
from pathlib import Path
from difflib import unified_diff

def extract_function_body(file_path, function_name):
    """Extract a function's body from a Python file."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Find function definition
    pattern = rf'def {re.escape(function_name)}\([^)]*\)[^:]*:'
    match = re.search(pattern, content)
    if not match:
        return None

    start = match.start()

    # Find function end (next function at same or lower indentation)
    lines = content[start:].split('\n')
    func_lines = [lines[0]]
    base_indent = len(lines[1]) - len(lines[1].lstrip()) if len(lines) > 1 else 4

    for i, line in enumerate(lines[1:], 1):
        if line.strip() and not line.startswith(' ' * base_indent):
            break
        func_lines.append(line)

    return '\n'.join(func_lines)

def compare_key_logic_sections():
    """Compare key logic sections between old and new implementations."""

    print("🔍 Verifying FR Simulator Logic Preservation\n")
    print("=" * 70)

    original_file = Path('src/web/app.py.backup')
    new_file = Path('src/web/ui/fr_simulator.py')

    # Check that critical strings/logic patterns exist in both
    critical_patterns = [
        # Revenue calculation logic
        (r'capacity_revenue_eur', 'Capacity revenue calculation'),
        (r'activation_revenue_eur', 'Activation revenue calculation'),
        (r'total_revenue_eur', 'Total revenue calculation'),

        # Product configuration
        (r'FCR.*enabled', 'FCR product configuration'),
        (r'aFRR.*enabled', 'aFRR product configuration'),
        (r'mFRR.*enabled', 'mFRR product configuration'),

        # Data loading
        (r'load_transelectrica_imbalance_from_excel', 'Transelectrica data loading'),
        (r'export-8', 'Export-8 file handling'),

        # Simulation call
        (r'simulate_frequency_regulation_revenue_multi', 'Main simulation function call'),

        # Key UI elements
        (r'Combined Monthly Revenue', 'Combined monthly revenue display'),
        (r'Per-Product Monthly', 'Per-product revenue display'),

        # Currency/formatting
        (r'currency_decimals', 'Currency formatting'),
        (r'styled_table', 'Table styling'),

        # Hedge pricing
        (r'build_hedge_price_curve', 'Hedge price curve'),

        # Data completeness check
        (r'Data completeness', 'Data quality validation'),
        (r'<96 slots', 'Incomplete day detection'),
    ]

    original_content = original_file.read_text()
    new_content = new_file.read_text()

    all_present = True

    print("\n📋 CHECKING CRITICAL LOGIC PATTERNS:\n")

    for pattern, description in critical_patterns:
        in_original = bool(re.search(pattern, original_content))
        in_new = bool(re.search(pattern, new_content))

        if not in_original:
            status = "⚠️  N/A"
            note = "(not in original)"
        elif in_new:
            status = "✅ OK"
            note = ""
        else:
            status = "❌ MISSING"
            note = "(PRESENT IN ORIGINAL, MISSING IN NEW!)"
            all_present = False

        print(f"  {status} {description:40s} {note}")

    print("\n" + "=" * 70)

    # Check line counts (should be similar order of magnitude)
    original_lines = len(original_content.split('\n'))
    new_lines = len(new_content.split('\n'))

    # Original has entire file, new is just the function
    # Extract just the function from original for fair comparison
    func_match = re.search(r'def render_frequency_regulation_simulator.*?(?=\ndef [a-z_]|\Z)',
                          original_content, re.DOTALL)
    if func_match:
        original_func_lines = len(func_match.group(0).split('\n'))
        print(f"\n📊 LINE COUNT COMPARISON:")
        print(f"  Original function: ~{original_func_lines} lines")
        print(f"  New module: ~{new_lines} lines")

        ratio = new_lines / original_func_lines if original_func_lines > 0 else 0
        if 0.8 <= ratio <= 1.2:
            print(f"  ✅ Size ratio: {ratio:.2f}x (reasonable - similar size)")
        elif ratio < 0.8:
            print(f"  ⚠️  Size ratio: {ratio:.2f}x (new is smaller - may be missing logic)")
            all_present = False
        else:
            print(f"  ℹ️  Size ratio: {ratio:.2f}x (new is larger - may have additions)")

    # Check imports are complete
    print(f"\n📦 IMPORT VERIFICATION:")
    required_imports = [
        'styled_table',
        'format_currency',
        'simulate_frequency_regulation_revenue_multi',
        'load_transelectrica_imbalance_from_excel',
        'build_hedge_price_curve',
        'compute_activation_factor_series',
    ]

    for imp in required_imports:
        if f'import {imp}' in new_content or f'from .* import.*{imp}' in new_content:
            print(f"  ✅ {imp}")
        else:
            print(f"  ❌ {imp} (MISSING)")
            all_present = False

    print("\n" + "=" * 70)

    if all_present:
        print("\n✅ SUCCESS: All critical logic patterns preserved!")
        return 0
    else:
        print("\n❌ FAILURE: Some critical logic may be missing!")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(compare_key_logic_sections())
