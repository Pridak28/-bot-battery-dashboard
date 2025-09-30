#!/usr/bin/env python3
"""
Generate comprehensive multi-year export-8-sample.xlsx file for FR Simulator
with realistic Romanian imbalance price data spanning multiple years.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

def generate_multi_year_export8_sample():
    """Generate comprehensive multi-year sample data for FR Simulator"""
    
    # Generate 3+ years of data (2022-2025)
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2025, 6, 30)
    
    print(f'🚀 Generating comprehensive FR sample data...')
    print(f'📅 Date range: {start_date.date()} to {end_date.date()}')
    
    data_rows = []
    current_date = start_date
    day_count = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Generate 96 15-minute slots per day (24h * 4 slots/h)
        for slot in range(96):
            hour = slot // 4
            minute = (slot % 4) * 15
            time_str = f'{hour:02d}:{minute:02d}'
            
            # Generate realistic imbalance prices in RON/MWh
            # Base price varies by hour of day (higher during peak hours)
            if 6 <= hour <= 9 or 17 <= hour <= 21:  # Peak hours
                base_price = np.random.normal(180, 120)
            elif 22 <= hour <= 23 or 0 <= hour <= 5:  # Night hours  
                base_price = np.random.normal(60, 50)
            else:  # Mid-day hours
                base_price = np.random.normal(120, 80)
            
            # Add seasonal variation (winter higher, summer lower)
            month_factor = 1.0
            if current_date.month in [1, 2, 12]:  # Winter
                month_factor = 1.3
            elif current_date.month in [6, 7, 8]:  # Summer
                month_factor = 0.85
            elif current_date.month in [3, 4, 11]:  # Transition
                month_factor = 1.1
            
            # Add day-of-week variation (weekends lower)
            if current_date.weekday() >= 5:  # Weekend
                month_factor *= 0.7
            
            # Add yearly trend (prices generally increasing)
            year_factor = 1.0
            if current_date.year == 2023:
                year_factor = 1.15  # Energy crisis impact
            elif current_date.year == 2024:
                year_factor = 1.25
            elif current_date.year >= 2025:
                year_factor = 1.35
            
            # Final price with some randomness
            price_ron = base_price * month_factor * year_factor + np.random.normal(0, 30)
            
            # Occasionally add extreme price spikes (system stress events)
            if np.random.random() < 0.015:  # 1.5% chance
                spike_factor = np.random.choice([4, -3, 5, -2.5])  # Various spike types
                price_ron *= spike_factor
            
            # Add some correlated price movements (grid stability issues)
            if slot > 0 and abs(data_rows[-1]['Price_RON_MWh']) > 300:
                if np.random.random() < 0.3:  # 30% chance of continuation
                    price_ron *= 0.8 * np.sign(data_rows[-1]['Price_RON_MWh'])
            
            # Round to 2 decimals
            price_ron = round(price_ron, 2)
            
            data_rows.append({
                'Date': date_str,
                'Time': time_str, 
                'Slot': slot,
                'Price_RON_MWh': price_ron,
                'System_Status': 'Stressed' if abs(price_ron) > 400 else ('High' if abs(price_ron) > 200 else 'Normal')
            })
        
        day_count += 1
        if day_count % 100 == 0:
            print(f'📊 Generated {day_count} days ({len(data_rows):,} data points)...')
        
        current_date += timedelta(days=1)
    
    print(f'✅ Generated {len(data_rows):,} data points')
    print(f'📊 Creating summary statistics...')
    
    # Create DataFrame
    df = pd.DataFrame(data_rows)
    
    # Create comprehensive summary statistics
    monthly_stats = []
    df['DateTime'] = pd.to_datetime(df['Date'])
    df['YearMonth'] = df['DateTime'].dt.to_period('M')
    
    for year_month in sorted(df['YearMonth'].unique()):
        month_data = df[df['YearMonth'] == year_month]
        monthly_stats.append({
            'Month': str(year_month),
            'Days': len(month_data['Date'].unique()),
            'Data_Points': len(month_data),
            'Avg_Price_RON': round(month_data['Price_RON_MWh'].mean(), 2),
            'Min_Price_RON': round(month_data['Price_RON_MWh'].min(), 2),
            'Max_Price_RON': round(month_data['Price_RON_MWh'].max(), 2),
            'Std_Price_RON': round(month_data['Price_RON_MWh'].std(), 2),
            'P10_Price_RON': round(month_data['Price_RON_MWh'].quantile(0.1), 2),
            'P90_Price_RON': round(month_data['Price_RON_MWh'].quantile(0.9), 2),
            'Positive_Prices': len(month_data[month_data['Price_RON_MWh'] > 0]),
            'Negative_Prices': len(month_data[month_data['Price_RON_MWh'] < 0]),
            'Extreme_Events': len(month_data[abs(month_data['Price_RON_MWh']) > 400]),
            'High_Volatility_Periods': len(month_data[abs(month_data['Price_RON_MWh']) > 200])
        })
    
    stats_df = pd.DataFrame(monthly_stats)
    
    print(f'💾 Saving to data/export-8-sample.xlsx...')
    
    # Save to Excel with two sheets
    output_path = Path('data/export-8-sample.xlsx')
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Main data sheet (compatible with existing parser)
        df_export = df[['Date', 'Time', 'Price_RON_MWh']].copy()
        df_export.to_excel(writer, sheet_name='export8', index=False)
        
        # Summary statistics sheet
        stats_df.to_excel(writer, sheet_name='normalized_reference', index=False)
    
    print(f'🎉 Successfully generated comprehensive export-8-sample.xlsx!')
    print(f'📈 Dataset includes:')
    print(f'   • {len(df):,} total data points')
    print(f'   • {len(df["Date"].unique())} unique days')
    print(f'   • {len(stats_df)} months of data')
    print(f'   • Date range: {df["Date"].min()} to {df["Date"].max()}')
    print(f'   • Price range: {df["Price_RON_MWh"].min():.2f} to {df["Price_RON_MWh"].max():.2f} RON/MWh')
    print(f'   • Two Excel sheets: "export8" (main data) and "normalized_reference" (stats)')
    
    return df, stats_df

if __name__ == "__main__":
    generate_multi_year_export8_sample()