#!/usr/bin/env python3
"""
Comprehensive import verification for fr_simulator.py after refactoring.
Checks all function calls against available imports and identifies missing ones.
"""

import ast
import sys
from pathlib import Path

def extract_function_calls(file_path):
    """Extract all function calls from a Python file."""
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                # For method calls like st.button, we care about the method name
                calls.add(node.func.attr)

    return calls

def extract_imports(file_path):
    """Extract all imported names from a Python file."""
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.asname if alias.asname else alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.asname if alias.asname else alias.name)

    return imports

def get_builtins_and_stdlib():
    """Get common builtins and stdlib names to exclude from missing."""
    return {
        # Builtins
        'abs', 'all', 'any', 'bool', 'dict', 'float', 'int', 'len', 'list',
        'max', 'min', 'print', 'range', 'sorted', 'str', 'sum', 'type',
        # Common methods that don't need imports
        'append', 'get', 'items', 'keys', 'values', 'pop', 'strip', 'upper',
        'lower', 'join', 'split', 'replace', 'format', 'count', 'index',
        # Pandas/numpy methods
        'astype', 'dropna', 'groupby', 'isna', 'notna', 'merge', 'mean',
        'quantile', 'unique', 'to_datetime', 'read_csv', 'normalize',
        # Streamlit methods
        'button', 'checkbox', 'caption', 'columns', 'dataframe', 'error',
        'expander', 'file_uploader', 'info', 'markdown', 'metric', 'number_input',
        'selectbox', 'subheader', 'success', 'table', 'text_input', 'warning',
        'write',
        # Common classes
        'DataFrame', 'Path',
        # Other
        'json', 'exists',
    }

def main():
    fr_sim_path = Path('src/web/ui/fr_simulator.py')

    print("🔍 Analyzing fr_simulator.py imports...\n")

    # Get function calls and imports
    calls = extract_function_calls(fr_sim_path)
    imports = extract_imports(fr_sim_path)
    exclude = get_builtins_and_stdlib()

    # Find potentially missing imports
    potentially_missing = calls - imports - exclude

    print(f"Total function calls found: {len(calls)}")
    print(f"Total imports found: {len(imports)}")
    print(f"Excluded (builtins/stdlib/methods): {len(exclude)}")
    print(f"Potentially missing: {len(potentially_missing)}\n")

    if potentially_missing:
        print("⚠️  POTENTIALLY MISSING IMPORTS:")
        for name in sorted(potentially_missing):
            print(f"  - {name}")
        print()

    # Check specific known functions from the refactoring
    known_functions = {
        'styled_table': 'src.web.utils.formatting',
        'compute_activation_factor_series': 'src.web.analysis',
        'simulate_frequency_regulation_revenue_multi': 'src.web.simulation',
        'build_hedge_price_curve': 'src.web.data',
        'format_currency': 'src.web.utils.formatting',
    }

    print("✅ CHECKING KNOWN REQUIRED FUNCTIONS:")
    for func, expected_module in known_functions.items():
        if func in imports:
            print(f"  ✓ {func} (imported)")
        elif func in potentially_missing:
            print(f"  ✗ {func} (MISSING - should import from {expected_module})")
        else:
            print(f"  ? {func} (unclear)")
    print()

    # Try to actually import the module to catch runtime errors
    print("🧪 ATTEMPTING RUNTIME IMPORT TEST:")
    try:
        sys.path.insert(0, str(Path.cwd()))
        # We can't fully import because it has streamlit code, but we can check syntax
        import py_compile
        py_compile.compile(str(fr_sim_path), doraise=True)
        print("  ✓ File compiles successfully (syntax OK)")
    except SyntaxError as e:
        print(f"  ✗ Syntax error: {e}")
        return 1

    if potentially_missing:
        print("\n⚠️  WARNING: Found potentially missing imports. Review needed.")
        return 1
    else:
        print("\n✅ All imports appear to be in order!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
