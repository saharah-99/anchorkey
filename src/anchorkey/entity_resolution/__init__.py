# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
anchorkey.entity_resolution — decide which observed identifier strings are the SAME entity.

This is the Paper 2 layer. It resolves the residual left by ingestion: after normalization
collapses spelling drift, ~99 distinct `sensorType` keys remain for a domain with roughly
two dozen real sensor models. The question this layer answers is which of those remaining
keys refer to the same physical part.

WHAT THIS LAYER DOES
    Merges only what normalization proves identical, and defers everything else to a
    human-adjudicated, effective-dated label. It does not guess.

FUZZY MATCHING WAS EVALUATED AND REJECTED
    The obvious design — merge keys that are "close enough" under a string-similarity
    metric — was implemented and measured before being discarded. Five metrics (plain
    Levenshtein, Damerau-Levenshtein, Jaro-Winkler, q-gram Jaccard, and a two-stage
    digit-core matcher) were scored against hand-verified ground truth on the archived
    snapshot.

    All five overlap. Every threshold that merges a genuine typo also merges two
    genuinely different parts. The result makes the approach undependable.
    Tuning does not help, because the deciding fact is not in the
    string: whether `bmp280` and `bme280` name one part or two is a property of Bosch's
    catalog, not of those six characters. A catalog is external knowledge, and it
    changes over time as parts ship and are discontinued.

    That is why identity here is resolved by a human-supplied label rather than a
    distance function, and why those labels must be effective-dated.

    Measurement:  data/separability_sample.py
    Ground truth: data/ground_truth_catalog.csv  (12 real parts + 3 confirmed non-parts,
                  each verified against a manufacturer datasheet; 1 string could not be
                  resolved either way and is excluded — see the BMP200 row, which is
                  itself a demonstration of the problem)

SCOPE
    Identifier fields only (`sensorType`, `unit`) — atomic, single-token strings.
    Descriptive fields (`title`) are out of scope: in the reference dataset they are
    measurand labels in mixed languages ("Temperatur", "rel. Luftfeuchte", "PM10"), not
    device names, and naming what is measured is a different problem from naming what
    measured it.
"""

from .identity import describe, natural_key
from .matching import needs_review, same_entity

__all__ = ["same_entity", "needs_review", "natural_key", "describe"]
