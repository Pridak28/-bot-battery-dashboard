from __future__ import annotations

import sys
from pathlib import Path

# Base paths ---------------------------------------------------------------
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent

# Backwards-compatible aliases for existing code
current_dir = CURRENT_DIR
project_root = PROJECT_ROOT

# Ensure project root is available for absolute imports when running Streamlit
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Shared configuration defaults -------------------------------------------
DEFAULT_TIMEZONE = "Europe/Bucharest"
DEFAULT_CURRENCY_SYMBOL = "€"

__all__ = [
    "CURRENT_DIR",
    "PROJECT_ROOT",
    "current_dir",
    "project_root",
    "DEFAULT_TIMEZONE",
    "DEFAULT_CURRENCY_SYMBOL",
]
