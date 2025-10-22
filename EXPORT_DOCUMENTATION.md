# Financial Export Documentation

## Overview

Professional financial reporting for banks, investors, and stakeholders.

## Export Features

### 📥 Excel Export (Comprehensive Report)

Generates a multi-sheet Excel workbook containing:

#### Sheet 1: Executive Summary
- Investment structure (total, equity, debt)
- Loan terms and interest rate
- FR business performance summary
- PZU business performance summary
- Business comparison and recommendation
- Annual ROI for both strategies

#### Sheet 2: FR Revenue Detail
- Month-by-month breakdown
- Capacity revenue vs Activation revenue
- Energy costs
- Activation energy volumes (MWh)
- Net margins
- **Total row** with aggregated figures

#### Sheet 3: PZU Monthly Summary
- Daily profits aggregated by month
- Total profit, average daily profit
- Number of trading days
- Total revenue and costs
- **Total row** with aggregated figures

#### Sheet 4: FR Cashflow Projection (10 Years)
- Year-by-year projection from 2025
- Annual revenue, operating costs, energy costs
- Debt service schedule
- Net cashflow per year
- Cumulative cashflow tracking
- Shows when project breaks even

#### Sheet 5: PZU Cashflow Projection (10 Years)
- Year-by-year projection from 2025
- Annual gross profit, operating costs
- Debt service schedule
- Net cashflow per year
- Cumulative cashflow tracking
- Shows when project breaks even

#### Sheet 6: Debt Amortization Schedule
- Month-by-month debt repayment
- Principal vs Interest breakdown
- Remaining balance after each payment
- Complete schedule for entire loan term
- Shows total interest paid over loan life

### 📄 CSV Export (Quick Summary)

Simple CSV file with executive summary metrics only:
- Investment overview
- Key financial metrics for FR and PZU
- Business recommendation

Perfect for quick sharing or importing into other tools.

## How to Use

1. **Navigate to Investment & Finance** section
2. Configure your investment parameters:
   - Total investment amount
   - Equity/debt split
   - Loan term and interest rate
   - Operating costs
3. **Run FR Simulator** and **PZU Horizons** first to populate data
4. Scroll to bottom of Investment & Finance page
5. Click **"Export to Excel"** or **"Export Summary CSV"**
6. Download button will appear
7. Click **"Download"** to save the report

## File Naming Convention

Files are automatically timestamped:
- Excel: `Battery_Financial_Analysis_YYYYMMDD_HHMMSS.xlsx`
- CSV: `Battery_Summary_YYYYMMDD_HHMMSS.csv`

## Use Cases

### For Banks
- Debt financing applications
- Credit risk assessment
- Collateral valuation
- Loan term negotiation

### For Investors
- ROI analysis and comparison
- Payback period evaluation
- Risk assessment (debt coverage ratios)
- Due diligence documentation

### For Project Development
- Business plan attachments
- Regulatory filings
- Partner presentations
- Grant applications

### For Internal Analysis
- Scenario comparison (FR vs PZU)
- Sensitivity analysis (change parameters and re-export)
- Monthly performance tracking
- Historical trend analysis

## Technical Details

### Data Sources
- **FR Revenue**: From FR Simulator historical data
- **PZU Profit**: From PZU Horizons analysis
- **Projections**: Based on annualized historical averages
- **Debt Schedule**: Calculated using standard loan amortization formula

### Calculations
- **Annualization**: Partial year data properly extrapolated to 12 months
- **Debt Service**: Equal monthly payments (amortizing loan)
- **ROI**: Net profit after debt / Total investment × 100
- **Payback Period**: Year when cumulative cashflow becomes positive

### Export Format
- **Excel**: OpenPyXML format (.xlsx)
- **CSV**: UTF-8 encoded
- **Currency**: Formatted as €X,XXX.XX
- **Dates**: ISO 8601 format (YYYY-MM-DD)

## Best Practices

1. **Always run simulators first**
   - FR Simulator with latest data
   - PZU Horizons for same period
   - Ensures export has complete data

2. **Select appropriate date ranges**
   - Use full years when possible
   - At least 12 months of data recommended
   - System automatically annualizes partial years

3. **Configure realistic parameters**
   - Operating costs based on actual estimates
   - Loan terms matching market conditions
   - Conservative projections for bank submissions

4. **Include multiple scenarios**
   - Export with different financing structures
   - Compare optimistic vs conservative forecasts
   - Show both FR and PZU options

5. **Keep audit trail**
   - Save timestamped exports
   - Document parameter changes
   - Track actual vs projected performance

## Troubleshooting

**Export button shows error:**
- Ensure FR Simulator and PZU Horizons ran successfully
- Check that session data is populated
- Try refreshing the page and running simulators again

**Missing data in sheets:**
- Some sheets may be empty if data unavailable
- Run both FR and PZU simulators for complete export
- Check date range selection includes data

**Numbers don't match simulator:**
- Export uses annualized averages for projections
- Partial year data is extrapolated to 12 months
- Review year selection filters in Investment section

## Future Enhancements

Potential additions:
- PDF executive summary with charts
- Sensitivity analysis tables
- Monte Carlo simulation exports
- Automated email delivery
- Integration with accounting systems
- Multi-currency support
