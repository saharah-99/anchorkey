# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
anchorkey.ingestion — turn messy observed identifier strings into stable natural keys.

This is the Paper 1 layer: deterministic, idempotent normalization applied at ingestion,
before any key is written. See normalize().
"""

from .normalize import normalize

__all__ = ["normalize"]
