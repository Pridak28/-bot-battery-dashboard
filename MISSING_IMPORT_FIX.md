# Missing Import Fix - compute_activation_factor_series

## Issue
```
NameError: name 'compute_activation_factor_series' is not defined
```

**Location**: `src/web/ui/fr_simulator.py` line 348

---

## Root Cause

During the web app refactoring:

1. ✅ `compute_activation_factor_series()` was moved from `app.py` → `src/web/analysis/balancing.py`
2. ✅ Function is properly defined in the analysis package
3. ❌ `fr_simulator.py` still calls it but **never imported it**

### Before Refactoring
```python
# Everything in app.py
def compute_activation_factor_series(...):
    # function code

def render_frequency_regulation_simulator(...):
    series = compute_activation_factor_series(...)  # ✅ Works
```

### After Refactoring (Broken)
```python
# src/web/analysis/balancing.py
def compute_activation_factor_series(...):
    # function code

# src/web/ui/fr_simulator.py
# Missing import!
def render_frequency_regulation_simulator(...):
    series = compute_activation_factor_series(...)  # ❌ NameError!
```

---

## The Fix

Added missing import to `src/web/ui/fr_simulator.py`:

```python
from src.web.analysis import compute_activation_factor_series
```

### Complete Import Section (Fixed)
```python
from src.web.config import project_root
from src.web.analysis import compute_activation_factor_series  # ← Added
from src.web.data import (
    build_hedge_price_curve,
    find_in_data_dir,
    # ... other imports
)
from src.web.simulation import simulate_frequency_regulation_revenue_multi
from src.web.utils import sanitize_session_value, safe_session_state_update
from src.web.utils.formatting import format_currency
```

---

## Files Modified

| File | Change |
|------|--------|
| src/web/ui/fr_simulator.py | Added `from src.web.analysis import compute_activation_factor_series` |

---

## Testing

```bash
cd "/Users/seversilaghi/Documents/BOT BATTERY"
python3 test_app_startup.py
```

**Result**: ✅ Pass
```
✅ app.py imports successfully!
✅ Ready to run: streamlit run src/web/app.py
```

---

## Complete List of Refactoring Import Fixes

| Module | Missing Import | Status |
|--------|---------------|--------|
| src/web/analysis/finance.py | `import streamlit as st` | ✅ Fixed |
| src/web/simulation/frequency_regulation.py | `from pathlib import Path` | ✅ Fixed |
| src/web/simulation/frequency_regulation.py | `from datetime import date, datetime` | ✅ Fixed |
| src/web/simulation/frequency_regulation.py | `from src.web.config import project_root` | ✅ Fixed |
| src/web/simulation/frequency_regulation.py | `from src.web.data import load_config` | ✅ Fixed |
| src/web/simulation/frequency_regulation.py | `from src.data.data_provider import DataProvider` | ✅ Fixed |
| src/web/ui/fr_simulator.py | `from src.web.analysis import compute_activation_factor_series` | ✅ Fixed |

**Total**: 7 missing imports fixed

---

## How to Prevent This

### During Refactoring

1. **Search for function calls** before moving:
   ```bash
   grep -r "compute_activation_factor_series" src/web/
   ```

2. **Update all imports** where the function is used

3. **Run import tests** after refactoring:
   ```bash
   python3 -c "from src.web.ui import *"
   ```

4. **Check the app starts**:
   ```bash
   python3 test_app_startup.py
   ```

### Automated Checks

Add to CI/CD or pre-commit:

```bash
#!/bin/bash
# Check all modules can be imported
python3 -c "from src.web.ui import *" || exit 1
python3 -c "from src.web.analysis import *" || exit 1
python3 -c "from src.web.simulation import *" || exit 1
python3 -c "from src.web.data import *" || exit 1
python3 test_app_startup.py || exit 1
echo "✅ All imports OK"
```

---

## Status

✅ **Fixed** - All missing imports resolved

**Next**: Run the app and test the FR Simulator view to ensure it works end-to-end.

```bash
streamlit run src/web/app.py
```

Then navigate to "FR Simulator" view and verify it loads without errors.
