# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
anchorkey — earn a stable identity for observed-entity telemetry before you key on it.

Auditable provenance for observed-entity telemetry: identity resolution under identifier
drift. This release ships the normalization layer (Paper 1) and the entity-resolution
layer (Paper 2). The immutable-snapshot storage layer is forthcoming with a later paper
in the series (see the README roadmap).

The package is organised by pipeline stage:
    anchorkey.ingestion          -> normalization (Paper 1)
    anchorkey.entity_resolution  -> identity resolution (Paper 2, this release)

Public API:
    normalize(value)            -> the stable natural key for one identifier string
    natural_key(name)           -> the canonical identity key for one observed string
    same_entity(a, b)           -> True only when normalization PROVES the two identical
    needs_review(a, b)          -> True when the pair is unresolved and needs a human
    describe(name)              -> show how a string resolves (debugging aid)

A note on what `same_entity` does not do, because it is the whole finding of Paper 2:
False means "not proven identical", never "proven different". Fuzzy auto-merge was
implemented, measured against datasheet-verified ground truth, and rejected — five
metrics spanning the main families all merge genuinely different parts at any threshold
loose enough to catch genuine typos. The deciding fact is a manufacturer's catalog,
which is external to the string and changes over time. So unresolved pairs are routed to
`needs_review` and adjudicated by a person, not guessed at by a threshold.

See the README for the full argument. Start with normalize().
"""

# NOTE: importing from .entity_resolution makes this module depend on that subpackage.
# It is held out of the v0.1.0 public tree, so this import and the un-holding of
# src/anchorkey/entity_resolution/ must land in the SAME commit — shipping this file
# alone would break `import anchorkey` for every existing user.
from .entity_resolution import describe, natural_key, needs_review, same_entity
from .ingestion.normalize import normalize

__all__ = ["normalize", "natural_key", "same_entity", "needs_review", "describe"]
__version__ = "0.2.0"
