#!/usr/bin/env python3
"""Debug script to examine data files and test aggregation"""

import pandas as pd
from pathlib import Path
import sys

def examine_file(path: Path):
    print(f"\n=== Examining {path} ===")
    try:
        if path.suffix.lower() in ('.xlsx', '.xls'):
            df = pd.read_excel(path, nrows=10)
        else:
            # Try multiple encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(path, nrows=10, encoding=encoding)
                    print(f"Successfully read with encoding: {encoding}")
                    break
                except:
                    continue
            else:
                print("Failed to read with any encoding")
                return
        
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print("\nFirst few rows:")
        print(df.head())
        
        # Check for date-like columns
        for col in df.columns:
            sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
            print(f"Column '{col}': sample value = {sample} (type: {type(sample)})")
            
    except Exception as e:
        print(f"Error reading file: {e}")

def main():
    # Check a few OPCOM files
    opcom_dir = Path("downloads/opcom_pzu")
    if opcom_dir.exists():
        opcom_files = list(opcom_dir.rglob("*.csv"))[:3]  # Check first 3
        for f in opcom_files:
            examine_file(f)
    
    # Check imbalance files
    imb_dir = Path("downloads/transelectrica_imbalance")
    if imb_dir.exists():
        imb_files = list(imb_dir.rglob("*.xlsx")) + list(imb_dir.rglob("*.xls")) + list(imb_dir.rglob("*.csv"))
        for f in imb_files[:2]:  # Check first 2
            examine_file(f)
    
    # Check export-8 specifically
    for ext in ['.xlsx', '.xls']:
        export_file = Path(f"export-8{ext}")
        if export_file.exists():
            examine_file(export_file)

if __name__ == "__main__":
    main()