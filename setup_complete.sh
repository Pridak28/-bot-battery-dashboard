#!/bin/bash
# Complete Setup and Run Script for Battery Trading Bot
set -e

echo "=== Battery Trading Bot - Complete Setup and Data Collection ==="
echo

# Find Python command
PYTHON_CMD=""
for cmd in python3 python python3.11 python3.12; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON_CMD="$cmd"
        echo "Found Python: $PYTHON_CMD ($($cmd --version))"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Error: Python not found. Please install Python 3.11+ first:"
    echo "  - macOS: brew install python3 or download from python.org"
    echo "  - Ubuntu: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

# Step 1: Environment setup
echo "Step 1: Setting up Python environment..."
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    "$PYTHON_CMD" -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright browsers..."
python -m playwright install chromium

# Step 2: Automated data collection
echo
echo "Step 2: Downloading historical data (3 years)..."
chmod +x download_and_aggregate.sh
export RUN_PLAYWRIGHT=1
export YEARS=3
./download_and_aggregate.sh 4.97

# Step 3: Verify data files
echo
echo "Step 3: Verifying data files..."
if [ -f "data/pzu_history_3y.csv" ]; then
    pzu_rows=$(wc -l < data/pzu_history_3y.csv)
    echo "✓ PZU data: $pzu_rows rows in 3-year dataset"
else
    echo "✗ PZU 3-year data not found"
fi

if [ -f "data/imbalance_history_3y.csv" ]; then
    imb_rows=$(wc -l < data/imbalance_history_3y.csv)
    echo "✓ Imbalance data: $imb_rows rows in 3-year dataset"
else
    echo "✗ Imbalance 3-year data not found"
fi

# Step 4: Update config to use 3-year datasets
echo
echo "Step 4: Updating configuration for 3-year datasets..."
sed -i.bak 's/pzu_history_1y\.csv/pzu_history_3y.csv/' config.yaml
sed -i.bak 's/imbalance_history_1y\.csv/imbalance_history_3y.csv/' config.yaml
echo "✓ Config updated to use 3-year historical data"

# Step 5: Test the bot
echo
echo "Step 5: Testing bot with sample dates..."
test_dates=("2024-01-15" "2024-06-15" "2024-12-01")

for date in "${test_dates[@]}"; do
    echo "Testing date: $date"
    python -m src.main --mode dry-run --date "$date"
    echo
done

# Step 6: Run backtest on multiple dates
echo "Step 6: Running backtest on random sample of dates..."
if [ -f "data/pzu_history_3y.csv" ]; then
    echo "Running backtest on 10 random dates from the dataset..."
    cut -d, -f1 data/pzu_history_3y.csv | tail -n +2 | sort -u | shuf | head -10 | while read -r date; do
        echo "Backtesting: $date"
        python -m src.main --mode backtest --date "$date"
    done
fi

echo
echo "=== Setup Complete! ==="
echo "Your bot is ready with 3 years of historical data."
echo "Key files created:"
echo "- data/pzu_history_3y.csv (Day-ahead prices)"
echo "- data/imbalance_history_3y.csv (Imbalance prices + frequency)"
echo
echo "To run the bot:"
echo "- Single date: python -m src.main --mode dry-run --date YYYY-MM-DD"
echo "- Live mode: python -m src.main --mode live --date YYYY-MM-DD (after configuring real API endpoints)"