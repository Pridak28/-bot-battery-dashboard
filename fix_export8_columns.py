#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

def fix_export8_columns():
    """Fix column names in export-8-sample.xlsx to match parser expectations"""
    file_path = Path('/Users/seversilaghi/Documents/BOT BATTERY/data/export-8-sample.xlsx')
    
    print('🔧 Fixing export-8-sample.xlsx column names...')
    
    try:
        # Read existing comprehensive data
        df = pd.read_excel(file_path, sheet_name='export8')
        stats_df = pd.read_excel(file_path, sheet_name='normalized_reference')
        
        print(f'📊 Current columns: {list(df.columns)}')
        print(f'�� Data size: {len(df)} rows')
        
        # Fix column names to match parser expectations
        df_fixed = df.copy()
        # Keep only the first three columns (date, time, price)
        if df_fixed.shape[1] > 3:
            df_fixed = df_fixed.iloc[:, :3]
        df_fixed.columns = ['date', 'time', 'price ron/mwh']
        
        # Ensure proper date format
        df_fixed['date'] = pd.to_datetime(df_fixed['date']).dt.strftime('%Y-%m-%d')
        
        print(f'✅ Fixed columns: {list(df_fixed.columns)}')
        print(f'�� Date range: {df_fixed["date"].min()} to {df_fixed["date"].max()}')
        
        # Save with corrected names
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df_fixed.to_excel(writer, sheet_name='export8', index=False)
            stats_df.to_excel(writer, sheet_name='normalized_reference', index=False)
        
        print('🎉 SUCCESS! Fixed export-8-sample.xlsx column names')
        return True
        
    except Exception as e:
        print(f'❌ Error: {e}')
        return False

if __name__ == "__main__":
    fix_export8_columns()
