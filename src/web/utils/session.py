from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st


def sanitize_session_value(value: Any):
    """Convert values to objects Streamlit session state can serialise."""
    try:
        if isinstance(value, dict):
            return {k: sanitize_session_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [sanitize_session_value(v) for v in value]
        if isinstance(value, tuple):
            return tuple(sanitize_session_value(v) for v in value)
        if isinstance(value, pd.DataFrame):
            return value.to_dict(orient="records")
        if isinstance(value, pd.Series):
            return value.to_list()
        if value is pd.NaT:
            return None
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        if isinstance(value, pd.Period):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            value = float(value)
            return None if math.isnan(value) else value
        if isinstance(value, float):
            return None if math.isnan(value) else value
        return value
    except Exception:
        return value


def safe_session_state_update(key: str, new_value: dict) -> None:
    """Update Streamlit session state without triggering rerun loops."""
    try:
        sanitized = sanitize_session_value(new_value)
        new_hash = hashlib.md5(
            json.dumps(sanitized, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        hash_key = f"{key}_hash"
        if (
            st.session_state.get(hash_key) != new_hash
            or key not in st.session_state
        ):
            st.session_state[key] = sanitized
            st.session_state[hash_key] = new_hash
    except Exception:
        st.session_state[key] = new_value


__all__ = [
    "sanitize_session_value",
    "safe_session_state_update",
]
