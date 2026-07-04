"""Detection thresholds (DEMO-ONLY — tune here, not in code)."""

from datetime import timedelta

DEMURRAGE_WARN = timedelta(hours=12)   # warn when free time is this close to expiry
DWELL_MAX = timedelta(hours=8)         # max time with no observed progress before STALL
