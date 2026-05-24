"""
utils.py – Shared utility helpers.
"""
import math


def fmt(v):
    """Format a float for display, handling infinity and large values."""
    if math.isinf(v): return "∞"
    if v >= 10000:    return f"{v:,.0f}"
    if v >= 100:      return f"{v:.1f}"
    return f"{v:.3f}"


def parse_float(entry_widget, default=None):
    """Read a float (or fraction like '2/3') from a tk.Entry."""
    try:
        s = entry_widget.get().strip()
        if not s:
            return default
        if "/" in s:
            a, b = s.split("/")
            return float(a) / float(b)
        return float(s)
    except Exception:
        return default


def parse_int(entry_widget, default=None):
    """Read an integer from a tk.Entry."""
    try:
        return int(entry_widget.get().strip())
    except Exception:
        return default
