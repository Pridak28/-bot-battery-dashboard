#!/usr/bin/env python3
"""
Streamlit Cloud entry point for Battery Trading Bot Dashboard.
This file imports and runs the main application from src/web/app.py
"""

import sys
from pathlib import Path

# Add the project root (and src directory) to Python path
project_root = Path(__file__).resolve().parent
src_path = project_root / "src"
for path in (project_root, src_path):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

# Import and run the main application
if __name__ == "__main__":
    # Import the main app module
    from src.web import app
    
    # The app will run automatically when imported since it contains Streamlit code
    pass
