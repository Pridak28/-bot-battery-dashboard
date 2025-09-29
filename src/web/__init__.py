"""Expose Streamlit app module when importing src.web."""

from . import app as app  # re-export for `from src.web import app`

__all__ = ["app"]
