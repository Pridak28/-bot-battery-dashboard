# Romanian Battery Trading Bot - Strategy Rules Documentation

## Overview

This document explains the trading rules implemented in the battery strategy for Romania's PZU (day-ahead) and Balancing Markets.

## Market Structure

- **PZU (Day-Ahead Market)**: Hourly auctions for next-day delivery, gate closure at noon CET
- **Balancing Market**: 15-minute real-time settlements for system balancing
- **Timezone**: Europe/Bucharest (EET/EEST with DST support)
- **Battery**: 55 MWh capacity, 20 MW power, 90% round-trip efficiency

## PZU Day-Ahead Strategy Rules

### 1. Price Thresholds

- **Buy Threshold**: 25th percentile of daily prices (cheapest quartile)
- **Sell Threshold**: 75th percentile of daily prices (most expensive quartile)
- **Min Spread**: 15.0 EUR/MWh between effective buy cost and sell price (configurable)

### 2. SOC (State of Charge) Management

- **Initial SOC**: 50% (27.5 MWh)
- **SOC Feasibility**: Tracks energy through the day to prevent over-scheduling
- **End-of-Day Target**: Return to starting SOC ± tolerance (configurable)
- **Energy Accounting**: Considers 90% round-trip efficiency in cost calculations

### 3. Cycle Limits

- **Daily Cycles Target**: 1 full cycle per day (configurable)
- **Hours per Cycle**: ≈ round(55 MWh / 20 MW) = 3 hours charge + 3 hours discharge
- **Vendor Limit**: Maximum 2 cycles per day; strategy clamps to ≤2 cycles/day
- **Max Orders**: Limited by cycle target and available energy/headroom

### 4. DST (Daylight Saving Time) Handling

- **Tolerant Mode**: Accept 23/24/25 hour days (enabled by default)
- **23-hour days**: Reduce cycle hours proportionally
- **25-hour days**: Allow extra hour if profitable

### 5. Spread Enforcement

- **Effective Cost Tracking**: Weighted average of buy prices divided by efficiency
- **Spread Check**: Only sell if (sell_price - effective_buy_cost) ≥ min_spread
- **Break-even Protection**: Accounts for round-trip losses and trading fees

## Configuration Parameters

### PZU Rules (config.yaml)

```yaml
strategy:
  pzu:
    daily_cycles_target: 1 # Number of full charge/discharge cycles per day
    min_spread_eur_mwh: 15.0 # Minimum profit spread required (EUR/MWh)
    enforce_soc_end_equal_start: true # Return to starting SOC at day end
    dst_tolerant: true # Handle 23/24/25 hour days
```

### Balancing Rules (Placeholder for Future Implementation)

```yaml
strategy:
  balancing:
    enable: false # Enable real-time balancing adjustments
    charge_threshold_delta_eur: 20.0 # BM price below DA ref to trigger charging
    discharge_threshold_delta_eur: 20.0 # BM price above DA ref to trigger discharging
    reserve_up: 0.15 # SOC headroom for high BM prices (15%)
    reserve_down: 0.15 # SOC footroom for negative BM prices (15%)
    max_deviation_fraction: 1.0 # Max deviation from DA schedule per interval
```

## Strategy Logic Flow

### 1. Day-Ahead Planning (11:00 AM daily)

1. Load 24-hour price forecast for next day
2. Calculate price thresholds (25th/75th percentiles)
3. Determine max buy/sell hours from cycle target
4. Simulate through each hour:
   - Prefer SELL if price ≥ high threshold AND sufficient energy AND spread OK
   - Otherwise BUY if price ≤ low threshold AND sufficient headroom
   - Track SOC and effective cost basis
5. Trim orders to achieve SOC neutrality if configured
6. Submit orders to OPCOM PZU market

### 2. Real-Time Balancing (Every 15 minutes) - Future

1. Monitor actual BM prices vs DA reference
2. Check deviation thresholds and SOC reserves
3. Opportunistically deviate from DA schedule if profitable
4. Maintain feasibility for end-of-day SOC target

## Risk Management Integration

### Battery Constraints

- **Power Limit**: 20 MW per hour (hard constraint)
- **Energy Limit**: 0-55 MWh SOC range (hard constraint)
- **Round-trip Efficiency**: 90% (energy loss on charge/discharge cycle)

### Risk Limits

- **Max Order Size**: 20 MWh per order (= 1 hour at max power)
- **Price Bounds**: -100 to 500 EUR/MWh (sanity checks)
- **Max Open Orders**: 100 (operational limit)

## Example Trading Day

**Sample Prices**: [50, 40, 30, 25, 20, 35, 60, 80, 90, 85, 75, 70, 65, 70, 75, 80, 90, 100, 110, 95, 80, 60, 45, 35] EUR/MWh

**Thresholds**: Low = 35 EUR/MWh (25th percentile), High = 80 EUR/MWh (75th percentile)

**Generated Orders**:

- BUY hours 3,4 (25, 20 EUR/MWh) - cheapest hours
- BUY hour 23 (35 EUR/MWh) - at threshold
- SELL hours 17,18,19 (100, 110, 95 EUR/MWh) - most expensive hours

**SOC Evolution**: 50% → 70% → 90% → 90% → 70% → 50% → 50% (returns to start)

**Spread Check**: Effective buy cost = (25/0.9 + 20/0.9 + 35/0.9)/3 = 29.6 EUR/MWh
Sell prices (100, 110, 95) all exceed 29.6 + 15 = 44.6 EUR/MWh ✓

## Performance Monitoring

### Key Metrics

- **Daily P&L**: (Sell Revenue - Buy Cost) accounting for efficiency losses
- **Arbitrage Spread**: Average sell price - effective buy cost
- **Cycle Efficiency**: Actual vs theoretical round-trip efficiency
- **SOC Tracking**: End-of-day vs target SOC deviation
- **Order Fill Rate**: Percentage of submitted orders that execute

### Alerts

- Spread below minimum threshold
- SOC deviation exceeding tolerance
- Consecutive days without profitable cycles
- Risk limit breaches

## Market Integration

### OPCOM PZU Interface

- **Gate Closure**: 12:00 CET for next day
- **Order Types**: Simple energy bids (MW for 1-hour blocks)
- **Settlement**: Marginal pricing at market clearing price
- **Nomination Updates**: Limited modification windows

### Transelectrica Balancing Interface (Future)

- **Real-time Signals**: 15-minute intervals
- **Deviation Settlement**: Imbalance price × energy deviation
- **Frequency Response**: Optional participation in automatic reserves

This rule-based approach ensures profitable, risk-controlled battery trading while adapting to Romania's specific market structures and regulations.
