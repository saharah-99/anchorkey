# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
matching.py — decide whether two observed identifier strings are the SAME real part.

The answer this module gives is deliberately narrow: two strings are the same entity if
and only if they normalize to the same natural key. Anything else is not decided here.
It is deferred, with the raw strings preserved, to a human-adjudicated label.

WHY SO CONSERVATIVE

Normalization (Paper 1) collapses spelling drift at zero risk: `SDS 011`, `SDS011`, and
`sds011` all converge, because the differences are stylistic — spacing, case, look-alike
Unicode. What survives is harder. Two examples from the reference dataset:

    hdc1080 / hhdc1080   ->  a typo. One real TI part, one string that names nothing.
    bme280  / bmp280     ->  NOT a typo. Two real Bosch parts; BME280 measures humidity,
                             BMP280 does not. Merging them silently averages two
                             different sensors into one.

Those two pairs are one edit apart. Every string-similarity metric measured (see
data/separability_sample.py) scores the *real* pair as similar as, or more similar than,
the typo pair. There is no threshold that separates them, and no amount of tuning creates
one, because the information that decides the question was never in the characters:
`hhdc1080` is a typo and `bme280` is a product because of what Texas Instruments and
Bosch did or did not manufacture. That is a catalog. Catalogs are external, and they
change — a string that names nothing today may name a real part next year.

So this module does not guess. It merges the certain and defers the rest.
"""

from __future__ import annotations

from ..ingestion.normalize import normalize


def same_entity(name_a: str, name_b: str) -> bool:
    """True if the two observed strings are certainly the same entity.

    Certainty here means: they differ only by drift the normalizer is proven to remove
    (spacing, case, separators, compatibility Unicode). `SDS 011` and `sds011` -> True.

    A False result means "not proven identical", NOT "proven different". `hdc1080` and
    `hhdc1080` return False even though a human would call them the same part, because
    that judgement requires a parts catalog this function does not have. Route those to
    review via `needs_review()` rather than treating False as a decision.
    """
    return normalize(name_a) == normalize(name_b)


def needs_review(name_a: str, name_b: str) -> bool:
    """True if the pair is unresolved: not certainly the same, not certainly different.

    This is the honest output of the layer and the input to the label workflow. Any pair
    that normalization does not merge is a candidate for human adjudication; a person
    consults the manufacturer catalog and records an effective-dated label. The label is
    a deterministic overlay applied at query time. It is never fed back into this
    function as training signal, which is what keeps identity a reproducible function of
    content rather than of accumulated history.
    """
    return not same_entity(name_a, name_b)
