#!/bin/bash
# Download Guide and Auto-Aggregation Script for Romanian Power Market Data
# Run this after manually downloading files to the respective folders

set -e

echo "=== Romanian Power Market Data Collection Guide ==="
echo
echo "STEP 1: Manual Downloads Required"
echo "=================================="
echo
echo "A) OPCOM PZU Day-Ahead Prices:"
echo "   URL: https://www.opcom.ro/grafice-ip-raportPIP-si-volumTranzactionat/ro"
echo "   - Navigate to PZU (Day-Ahead Market) section"
echo "   - Download historical price data for last 1-3 years"
echo "   - Save all CSV/XLSX files to: ./downloads/opcom_pzu/"
echo "   - Files can be organized in subfolders (e.g., by year/month)"
echo
echo "B) Transelectrica Estimated Imbalance Prices:"
echo "   URL: https://newmarkets.transelectrica.ro/uu-webkit-maing02/00121011300000000000000000000100/estimatedImbalancePrices"
echo "   - Download estimated imbalance price data (includes frequency)"
echo "   - Get data for last 1-3 years"
echo "   - Save all CSV/XLSX files to: ./downloads/transelectrica_imbalance/"
echo
echo "STEP 2: Check Downloaded Files"
echo "============================="

# Check if directories exist and count files
if [ -d "./downloads/opcom_pzu" ]; then
    pzu_files=$(find ./downloads/opcom_pzu -name "*.csv" -o -name "*.xlsx" -o -name "*.xls" | wc -l)
    echo "OPCOM PZU files found: $pzu_files"
    if [ $pzu_files -gt 0 ]; then
        echo "✓ OPCOM PZU files ready for aggregation"
    else
        echo "✗ No OPCOM PZU files found - please download them first"
    fi
else
    echo "✗ ./downloads/opcom_pzu directory not found"
fi

if [ -d "./downloads/transelectrica_imbalance" ]; then
    imb_files=$(find ./downloads/transelectrica_imbalance -name "*.csv" -o -name "*.xlsx" -o -name "*.xls" | wc -l)
    echo "Transelectrica imbalance files found: $imb_files"
    if [ $imb_files -gt 0 ]; then
        echo "✓ Transelectrica files ready for aggregation"
    else
        echo "✗ No Transelectrica files found - please download them first"
    fi
else
    echo "✗ ./downloads/transelectrica_imbalance directory not found"
fi

# Check for imbalance Excel file in project root
if [ -f "./export-8.xlsx" ] || [ -f "./export-8.xls" ]; then
    echo "✓ Found imbalance Excel file: export-8"
    # Copy to downloads directory for aggregation
    mkdir -p ./downloads/transelectrica_imbalance/manual
    cp export-8.* ./downloads/transelectrica_imbalance/manual/ 2>/dev/null || true
    imb_files=$((imb_files + 1))
fi

echo
echo "STEP 3: Auto-Aggregation (run when files are ready)"
echo "=================================================="

# Only proceed with aggregation if files exist
if [ $pzu_files -gt 0 ] || [ $imb_files -gt 0 ]; then
    echo "Proceeding with data aggregation..."
    
    # Find Python command (same logic as setup script)
    PYTHON_CMD=""
    for cmd in python3 python python3.11 python3.12; do
        if command -v "$cmd" >/dev/null 2>&1; then
            PYTHON_CMD="$cmd"
            break
        fi
    done
    
    if [ -z "$PYTHON_CMD" ]; then
        echo "❌ Error: Python not found for aggregation"
        exit 1
    fi
    
    # Activate virtual environment if it exists
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
    
    # Create data directory
    mkdir -p data
    
    # Set FX rate (RON per 1 EUR - adjust as needed)
    FX_RATE=${1:-4.97}
    echo "Using FX rate: $FX_RATE RON/EUR with Python: $PYTHON_CMD"
    
    # Aggregate PZU data if files exist
    if [ $pzu_files -gt 0 ]; then
        echo
        echo "Aggregating OPCOM PZU data..."
        "$PYTHON_CMD" -m src.tools.aggregate_pzu_manual \
            --inputs "./downloads/opcom_pzu" \
            --output data/pzu_history.csv \
            --currency-in RON \
            --target-currency EUR \
            --fx-rate $FX_RATE \
            --split-years
        echo "✓ Created: data/pzu_history.csv + 1y/2y/3y splits"
    fi
    
    # Aggregate imbalance data if files exist
    if [ $imb_files -gt 0 ]; then
        echo
        echo "Aggregating Transelectrica imbalance data..."
        "$PYTHON_CMD" -m src.tools.aggregate_imbalance_manual \
            --inputs "./downloads/transelectrica_imbalance" \
            --output data/imbalance_history.csv \
            --currency-in RON \
            --target-currency EUR \
            --fx-rate $FX_RATE \
            --split-years
        echo "✓ Created: data/imbalance_history.csv + 1y/2y/3y splits"
    fi
    
    echo
    echo "STEP 4: Update Configuration"
    echo "==========================="
    echo "Edit config.yaml to point to your preferred dataset:"
    echo "  data:"
    echo "    pzu_forecast_csv: ./data/pzu_history_1y.csv     # or _2y/_3y"
    echo "    bm_forecast_csv: ./data/imbalance_history_1y.csv # or _2y/_3y"
    
    echo
    echo "STEP 5: Test the Bot"
    echo "==================="
    echo "# Test single date:"
    echo "python -m src.main --mode dry-run --date 2024-01-15"
    echo
    echo "# Test multiple dates (if pzu_history_1y.csv exists):"
    if [ -f "data/pzu_history_1y.csv" ]; then
        echo "for d in \$(cut -d, -f1 data/pzu_history_1y.csv | tail -n +2 | sort -u | head -10); do"
        echo "  python -m src.main --mode dry-run --date \"\$d\""
        echo "done"
    else
        echo "# (Will be available after PZU aggregation)"
    fi
    
else
    echo
    echo "⚠️  Please download files first, then run this script again"
    echo
    echo "Quick download tips:"
    echo "1. Open the URLs in your browser"
    echo "2. Look for 'Export' or 'Download' buttons"
    echo "3. Select date ranges (last 1-3 years)"
    echo "4. Download as CSV or Excel format"
    echo "5. Save to the respective ./downloads/ folders"
fi

echo
echo "STEP 0 (optional): Automated fetch with Playwright"
echo "=================================================="
echo "Set RUN_PLAYWRIGHT=1 to enable. Optionally set YEARS=1|2|3 (default 1) and FX rate as first arg."
YEARS_ENV=${YEARS:-1}
if [ "${RUN_PLAYWRIGHT}" = "1" ]; then
  echo "Running Playwright downloads for ${YEARS_ENV} year(s)..."
  # Ensure browsers are installed
  python -c "import sys" && python -m playwright install chromium || { echo "Playwright install failed"; exit 1; }
  
  echo "Starting OPCOM PZU download (this may take a while)..."
  python -m src.tools.download_opcom_pzu_playwright --years ${YEARS_ENV} --out-dir downloads/opcom_pzu/auto || {
    echo "OPCOM download failed - trying headful mode for debugging..."
    python -m src.tools.download_opcom_pzu_playwright --years 1 --out-dir downloads/opcom_pzu/auto --headful || true
  }
  
  echo "Starting Transelectrica imbalance download..."
  python -m src.tools.download_transelectrica_imbalance_playwright --years ${YEARS_ENV} --out-dir downloads/transelectrica_imbalance/auto || {
    echo "Transelectrica download failed - trying headful mode for debugging..."  
    python -m src.tools.download_transelectrica_imbalance_playwright --years 1 --out-dir downloads/transelectrica_imbalance/auto --headful || true
  }
  
  echo "Playwright downloads completed. Check downloads/*/auto/ for results."
fi

echo
echo "=== End of Guide ==="