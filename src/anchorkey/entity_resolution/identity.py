# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
identity.py — derive the key a record is stored under.

The golden rule, repeated here because it is the whole point of the framework: bind
identity to the DATA's own content (a natural key), never to an arbitrary auto-increment
id or random UUID. A natural key is reproducible from an export and survives a database
re-seed; a surrogate id is neither.

For identifier fields the natural key is simply the normalized string. There is no token
extraction step: the fields this layer governs (`sensorType`, `unit`) are atomic — in the
reference dataset, 94% and 99.6% of their values respectively are a single token. Pulling
"identity-bearing" substrings out of them would re-introduce the very fragmentation the
normalizer exists to remove. An earlier draft of this module did exactly that, splitting
on whitespace before normalizing, which keyed `SDS 011` (the most common spelling, n=239)
separately from `sds011` and forked one sensor into two — the precise failure Paper 1
warns about when a second call site normalizes differently from the first.

One normalizer, one definition, everywhere.
"""

from __future__ import annotations

from ..ingestion.normalize import normalize


def natural_key(name: str) -> str:
    """Return the canonical identity key for one observed identifier string.

    A pure function of the input content: same content in, same key out, on any machine,
    with no dependence on insertion order or a counter.

    Note what this key does NOT do: it does not unify a part with a misspelling of that
    part (`hdc1080` and `hhdc1080` yield different keys), because deciding that they are
    the same requires a manufacturer catalog rather than a property of the strings. That
    resolution belongs to the effective-dated label layer, applied over these keys at
    query time.
    """
    return normalize(name) or "unknown"


def describe(name: str) -> dict:
    """Explain how a string resolves — for debugging and for the quickstart.

    Shows the input, its normalized form, and the resulting natural key, so a reader can
    see why two strings do or do not share an identity.
    """
    return {
        "input": name,
        "normalized": normalize(name),
        "natural_key": natural_key(name),
    }
