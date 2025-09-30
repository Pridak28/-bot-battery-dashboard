#!/usr/bin/env python3
"""
Generate a more comprehensive export-8-sample.xlsx file for FR Simulator
with multiple months of realistic Romanian imbalance price data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

def generate_comprehensive_export8_sample():
    """Generate comprehensive sample data for FR Simulator with multiple months"""
    
    # Generate 6 months of data (Jan-Jun 2024)
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 6, 30)
    
    data_rows = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Generate 96 15-minute slots per day (24h * 4 slots/h)
        for slot in range(96):
            hour = slot // 4
            minute = (slot % 4) * 15
            time_str = f"{hour:02d}:{minute:02d}"
            
            # Generate realistic imbalance prices in RON/MWh
            # Base price varies by hour of day (higher during peak hours)
            if 6 <= hour <= 9 or 17 <= hour <= 21:  # Peak hours
                base_price = np.random.normal(150, 80)
            elif 22 <= hour <= 23 or 0 <= hour <= 5:  # Night hours
                base_price = np.random.normal(50, 40)
            else:  # Mid-day hours
                base_price = np.random.normal(100, 60)
            
            # Add some seasonal variation
            month_factor = 1.0
            if current_date.month in [1, 2, 12]:  # Winter
                month_factor = 1.2
            elif current_date.month in [6, 7, 8]:  # Summer
                month_factor = 0.9
            
            # Add day-of-week variation
            if current_date.weekday() >= 5:  # Weekend
                month_factor *= 0.8
            
            # Final price with some randomness
            price_ron = base_price * month_factor + np.random.normal(0, 20)
            
            # Occasionally add extreme price spikes (system stress)
            if np.random.random() < 0.02:  # 2% chance
                price_ron *= np.random.choice([3, -2])  # Big spike or dip
            
            # Round to 2 decimals
            price_ron = round(price_ron, 2)
            
            data_rows.append({
                'Date': date_str,
                'Time': time_str,
                'Slot': slot,
                'Price_RON_MWh': price_ron,
                'System_Status': 'Normal' if abs(price_ron) < 200 else 'Stressed'
            })
        
        current_date += timedelta(days=1)
    
    # Create DataFrame
    df = pd.DataFrame(data_rows)
    
    # Create summary statistics for normalized_reference sheet
    monthly_stats = []
    for month in range(1, 7):
        month_data = df[pd.to_datetime(df['Date']).dt.month == month]
        monthly_stats.append({
            'Month': f"2024-{month:02d}",
            'Days': len(month_data['Date'].unique()),
            'Avg_Price_RON': month_data['Price_RON_MWh'].mean(),
            'Min_Price_RON': month_data['Price_RON_MWh'].min(),
            'Max_Price_RON': month_data['Price_RON_MWh'].max(),
            'Std_Price_RON': month_data['Price_RON_MWh'].std(),
            'Extreme_Events': len(month_data[abs(month_data['Price_RON_MWh']) > 200])
        })
    
    stats_df = pd.DataFrame(monthly_stats)
    
    # Save to Excel with two sheets
    output_path = Path('/Users/seversilaghi/Documents/BOT BATTERY/data/export-8-sample.xlsx')
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='export8', index=False)
        stats_df.to_excel(writer, sheet_name='normalized_reference', index=False)
    
    print(f"✅ Generated comprehensive export-8-sample.xlsx with:")
    print(f"   • {len(df)} data points ({len(df['Date'].unique())} days)")
    print(f"   • 6 months of data (Jan-Jun 2024)")
    print(f"   • Realistic Romanian imbalance prices")
    print(f"   • Two sheets: 'export8' (main data) and 'normalized_reference' (stats)")
    
    return df, stats_df

if __name__ == "__main__":
    generate_comprehensive_export8_sample()