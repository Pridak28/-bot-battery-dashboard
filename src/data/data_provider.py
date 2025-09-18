from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional
from datetime import date
import pandas as pd


class DataProvider:
    def __init__(self, pzu_csv: Optional[str] = None, bm_csv: Optional[str] = None):
        self.pzu_csv = pzu_csv
        self.bm_csv = bm_csv

    def load_price_forecasts(self, target_date: date) -> Dict[str, pd.Series]:
        out: Dict[str, pd.Series] = {}
        if self.pzu_csv and Path(self.pzu_csv).exists():
            df = pd.read_csv(self.pzu_csv)
            # Expect columns: date, hour(0-23), price
            sub = df[df["date"] == target_date.isoformat()].sort_values("hour")
            if not sub.empty:
                out["pzu"] = pd.Series(sub["price"].to_list())
        if self.bm_csv and Path(self.bm_csv).exists():
            df = pd.read_csv(self.bm_csv)
            # Expect columns: date, slot(0-95), price
            sub = df[df["date"] == target_date.isoformat()].sort_values("slot")
            if not sub.empty:
                out["balancing"] = pd.Series(sub["price"].to_list())
        return out
