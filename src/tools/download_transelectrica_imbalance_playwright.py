from __future__ import annotations
import argparse
import re
from datetime import date, timedelta
from pathlib import Path
from typing import List, Tuple, Optional
import pandas as pd
from playwright.sync_api import sync_playwright

URL = "https://newmarkets.transelectrica.ro/uu-webkit-maing02/00121011300000000000000000000100/estimatedImbalancePrices"


def parse_rows(texts: List[str]) -> pd.DataFrame:
    # Attempt to parse rows containing time or slot, price, and frequency
    # Output columns: slot (0..95), price (RON/MWh), frequency (Hz)
    rows: List[Tuple[int, float, Optional[float]]] = []
    for t in texts:
        parts = [p.strip() for p in re.split(r"\s{2,}|\t|\n", t) if p.strip()]
        if not parts:
            continue
        # Try detect time "HH:MM" or slot number
        slot: Optional[int] = None
        price: Optional[float] = None
        freq: Optional[float] = None
        for p in parts:
            # time like 12:30
            if re.match(r"^\d{1,2}:\d{2}$", p):
                try:
                    hh, mm = p.split(":")
                    slot = int(hh) * 4 + (int(mm) // 15)
                except Exception:
                    pass
                continue
            # numeric that could be slot 1..96
            if slot is None:
                try:
                    iv = int(p)
                    if 1 <= iv <= 96:
                        slot = iv - 1
                        continue
                except Exception:
                    pass
            # detect frequency ~ 45..55
            if freq is None:
                pp = p.replace(" ", "").replace(",", ".")
                try:
                    fv = float(pp)
                    if 45.0 <= fv <= 55.0:
                        freq = fv
                        continue
                except Exception:
                    pass
            # detect price (RON/MWh), broader range
            if price is None:
                pp = p.replace(".", "").replace(",", ".")
                try:
                    val = float(pp)
                    if -2000.0 < val < 10000.0:
                        price = val
                        continue
                except Exception:
                    pass
        if slot is not None and price is not None:
            rows.append((slot, price, freq))
    if not rows:
        return pd.DataFrame(columns=["slot", "price", "frequency"])
    df = pd.DataFrame(rows, columns=["slot", "price", "frequency"]).drop_duplicates("slot").sort_values("slot")
    df = df[(df["slot"] >= 0) & (df["slot"] <= 95)]
    return df


def scrape_day(page, d: date) -> pd.DataFrame:
    # More robust date handling for Transelectrica
    try:
        # Try multiple date input patterns
        date_patterns = [
            f"input[type='date']",
            f"input[placeholder*='date']",
            f"input[id*='date']",
            f"input[name*='date']"
        ]
        
        date_set = False
        for pattern in date_patterns:
            try:
                date_input = page.locator(pattern).first
                if date_input.count() > 0:
                    date_input.fill(d.isoformat())
                    date_set = True
                    break
            except:
                continue
        
        if not date_set:
            # Try URL parameter approach
            url_with_date = f"{URL}?date={d.isoformat()}"
            page.goto(url_with_date, timeout=30000)
        
        # Look for submit/apply buttons
        submit_patterns = [
            "button:has-text('Apply')",
            "button:has-text('Search')", 
            "button:has-text('Filter')",
            "input[type='submit']",
            "*:has-text('Cauta')",
            "*:has-text('Filtreaza')"
        ]
        
        for pattern in submit_patterns:
            try:
                page.locator(pattern).first.click(timeout=2000)
                break
            except:
                continue
                
    except Exception as e:
        print(f"Date setting error for {d}: {e}")

    page.wait_for_timeout(3000)

    # Enhanced data extraction
    texts = []
    
    # Try multiple extraction strategies
    strategies = [
        # Strategy 1: Look for data tables
        lambda: [page.locator("table").all_inner_texts()],
        lambda: [tr.inner_text() for tr in page.locator("tbody tr").all()],
        
        # Strategy 2: Look for price data containers  
        lambda: page.locator("*").filter(has_text=re.compile(r"\d+[,\.]\d+.*Hz")).all_text_contents(),
        lambda: page.locator("*").filter(has_text=re.compile(r"\d{2}:\d{2}")).all_text_contents(),
        
        # Strategy 3: Generic numeric data
        lambda: page.locator("*").filter(has_text=re.compile(r"\b\d+[,\.]\d{2,}\b")).all_text_contents()
    ]
    
    for i, strategy in enumerate(strategies):
        try:
            result = strategy()
            if result and any(result):
                texts.extend(result)
                print(f"Strategy {i+1} found {len(result)} items for {d}")
                break
        except Exception as e:
            print(f"Strategy {i+1} failed: {e}")
            continue
    
    return parse_rows(texts)


def run(years: int, out_dir: Path, headless: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.goto(URL, timeout=60000)
        # Cookie consent
        try:
            page.get_by_role("button", name=re.compile("Accept|Sunt de acord|Accepta", re.I)).click(timeout=3000)
        except Exception:
            pass

        start = date.today() - timedelta(days=365 * years)
        end = date.today()
        d = start
        while d <= end:
            try:
                page.reload(timeout=30000)
            except Exception:
                page.goto(URL, timeout=60000)
            df = scrape_day(page, d)
            if not df.empty:
                df.insert(0, "date", d.isoformat())
                out_path = out_dir / f"imbalance_{d.isoformat()}.csv"
                df.to_csv(out_path, index=False)
                print(f"Saved {out_path} ({len(df)} rows)")
            else:
                print(f"No data parsed for {d}")
            d += timedelta(days=1)
        browser.close()


def main():
    ap = argparse.ArgumentParser(description="Download Transelectrica estimated imbalance prices for last N years using Playwright")
    ap.add_argument("--years", type=int, choices=[1, 2, 3], required=True)
    ap.add_argument("--out-dir", type=str, default="downloads/transelectrica_imbalance/auto")
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    run(args.years, Path(args.out_dir), headless=not args.headful)


if __name__ == "__main__":
    main()
