from __future__ import annotations

from contextlib import contextmanager
from typing import Tuple

import matplotlib.pyplot as plt


@contextmanager
def safe_pyplot_figure(*args, **kwargs) -> Tuple[plt.Figure, plt.Axes]:
    """Context manager ensuring matplotlib figures are closed to avoid Streamlit rerun loops."""
    fig, ax = plt.subplots(*args, **kwargs)
    try:
        yield fig, ax
    finally:
        plt.close(fig)


__all__ = ["safe_pyplot_figure"]
