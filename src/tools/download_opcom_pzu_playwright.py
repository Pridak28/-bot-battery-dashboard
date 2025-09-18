from __future__ import annotations
import argparse
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Tuple
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import requests

# Direct CSV export URL pattern
URL_PATTERN = "https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/{day}/{month}/{year}/ro"


def download_csv_direct(d: date, out_dir: Path) -> bool:
    """Download CSV directly using the export URL pattern"""
    url = URL_PATTERN.format(day=d.day, month=d.month, year=d.year)
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Check if we got actual CSV data
        if response.text and (',' in response.text or ';' in response.text):
            out_path = out_dir / f"pzu_{d.isoformat()}.csv"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"Downloaded {out_path} directly from CSV export")
            return True
        else:
            print(f"No CSV data found for {d}")
            return False
    except Exception as e:
        print(f"Direct download failed for {d}: {e}")
        return False


def parse_table_texts(texts: List[str]) -> pd.DataFrame:
    rows: List[Tuple[int, float]] = []
    for t in texts:
        # Split row into cells by whitespace while preserving commas
        parts = [p.strip() for p in re.split(r"\s{2,}|\t|\n", t) if p.strip()]
        # Heuristic: first cell hour 1..24, find a price-like token (e.g., 485,38 or 485.38)
        if not parts:
            continue
        try:
            hour = int(parts[0])
        except Exception:
            continue
        if not (1 <= hour <= 24):
            continue
        price = None
        for p in parts[1:]:
            # Normalize decimal comma to dot
            pp = p.replace(".", "").replace(",", ".")
            try:
                val = float(pp)
                # price in RON/MWh is usually between -1000 and 5000
                if -1000.0 < val < 5000.0:
                    price = val
                    break
            except Exception:
                continue
        if price is not None:
            rows.append((hour, price))
    if not rows:
        return pd.DataFrame(columns=["hour", "price"])
    df = pd.DataFrame(rows, columns=["hour", "price"]).drop_duplicates("hour").sort_values("hour")
    # Convert to 0..23 hours
    df["hour"] = df["hour"].astype(int) - 1
    return df


def scrape_day(page, d: date) -> pd.DataFrame:
    # More robust date input handling for OPCOM
    try:
        # Look for date inputs in various forms
        date_selectors = [
            "input[type='text'][name*='zi']",
            "input[type='text'][name*='day']", 
            "input[id*='day']",
            "input[id*='zi']",
            "input.form-control",
            "input[type='number']"
        ]
        
        day_input = None
        month_input = None
        year_input = None
        
        for selector in date_selectors:
            inputs = page.locator(selector)
            if inputs.count() >= 3:
                day_input = inputs.nth(0)
                month_input = inputs.nth(1) 
                year_input = inputs.nth(2)
                break
        
        if day_input and month_input and year_input:
            day_input.clear()
            day_input.fill(str(d.day))
            month_input.clear()
            month_input.fill(str(d.month))
            year_input.clear()
            year_input.fill(str(d.year))
            
            # Try various refresh button patterns
            refresh_selectors = [
                "button:has-text('Refresh')",
                "input[type='submit']",
                "button[type='submit']",
                "*:has-text('Actualizeaza')",
                "*:has-text('Afiseaza')"
            ]
            
            for sel in refresh_selectors:
                try:
                    page.locator(sel).first.click(timeout=2000)
                    break
                except:
                    continue
                    
        page.wait_for_timeout(3000)  # Wait longer for data to load
        
    except Exception as e:
        print(f"Date input error for {d}: {e}")

    # More comprehensive table data extraction
    texts = []
    
    # Try multiple table extraction methods
    extraction_methods = [
        lambda: [page.locator("table").inner_text()],
        lambda: [tr.inner_text() for tr in page.locator("table tr").all()],
        lambda: [page.locator("#grafic").inner_text()],
        lambda: [page.locator(".chart").inner_text()],
        lambda: page.locator("*").filter(has_text=re.compile(r"\d+[,\.]\d+")).all_text_contents()
    ]
    
    for method in extraction_methods:
        try:
            result = method()
            if result and any(result):
                texts.extend(result)
                break
        except:
            continue
    
    print(f"Extracted {len(texts)} text blocks for {d}")
    df = parse_table_texts(texts)
    return df


def run(years: int, out_dir: Path, headless: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    
    start = date.today() - timedelta(days=365 * years)
    end = date.today()
    d = start
    
    # Try direct CSV downloads first
    successful_downloads = 0
    failed_dates = []
    
    print(f"Attempting direct CSV downloads for {(end - start).days + 1} dates...")
    
    while d <= end:
        if download_csv_direct(d, out_dir):
            successful_downloads += 1
        else:
            failed_dates.append(d)
        d += timedelta(days=1)
    
    print(f"Direct downloads: {successful_downloads} successful, {len(failed_dates)} failed")
    
    # If we have too many failures, fall back to browser automation for failed dates
    if failed_dates and len(failed_dates) < 50:  # Only retry a reasonable number
        print(f"Retrying {len(failed_dates)} failed dates with browser automation...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(locale="ro-RO")
            page = context.new_page()
            
            for d in failed_dates[:10]:  # Limit retries
                try:
                    page.goto(f"https://www.opcom.ro/grafice-ip-raportPIP-si-volumTranzactionat/ro", timeout=60000)
                    df = scrape_day(page, d)
                    if not df.empty:
                        df.insert(0, "date", d.isoformat())
                        out_path = out_dir / f"pzu_{d.isoformat()}.csv"
                        df.to_csv(out_path, index=False)
                        print(f"Browser fallback saved {out_path} ({len(df)} rows)")
                except Exception as e:
                    print(f"Browser fallback also failed for {d}: {e}")
            
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="Download OPCOM PZU hourly prices for last N years using Playwright")
    ap.add_argument("--years", type=int, choices=[1, 2, 3], required=True)
    ap.add_argument("--out-dir", type=str, default="downloads/opcom_pzu/auto")
    ap.add_argument("--headful", action="store_true", help="Run with visible browser for debugging")
    args = ap.parse_args()

    run(args.years, Path(args.out_dir), headless=not args.headful)


if __name__ == "__main__":
    main()
