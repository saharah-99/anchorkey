"""
anchorkey — earn a stable identity for observed-entity telemetry before you key on it.

Auditable provenance for observed-entity telemetry: identity resolution under identifier
drift, with tamper-evident sealing. This release ships the normalization layer (Paper 1); the
entity-resolution layer (matching + natural keys) and the tamper-evident ledger are forthcoming
with later papers in the series (see the README roadmap).

The package is organised by pipeline stage:
    anchorkey.ingestion          -> normalization (Paper 1, this release)

Public API:
    normalize(value)            -> the stable natural key for one identifier string

See the README for the full argument. Start with normalize().
"""

from .ingestion.normalize import normalize

__all__ = ["normalize"]
__version__ = "0.1.0"
