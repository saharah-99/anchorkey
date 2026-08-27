# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
Tests for the entity-resolution layer (the Paper 2 half).

The layer makes one promise and one refusal, and these tests pin both:

  * PROMISE  — strings that differ only by drift the normalizer removes are the same
               entity, and share one natural key.
  * REFUSAL  — everything else is NOT decided here. It is deferred, with the raw strings
               preserved, to a human-adjudicated effective-dated label.

The refusal is the substantive half. An earlier draft of this module auto-merged
"near-enough" strings via edit distance; measurement showed that no threshold separates a
typo from two genuinely different parts (see tests/test_separability.py). So the tests
below assert not only that real drift merges, but that verified-distinct real parts do
NOT — including pairs a fuzzy matcher would happily have collapsed.
"""

import pytest

from anchorkey.entity_resolution import describe, natural_key, same_entity
from anchorkey.entity_resolution.matching import needs_review


# --------------------------------------------------------------------------- #
# PROMISE: drift the normalizer removes -> same entity, one key.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("a, b, why", [
    ("SDS 011", "sds011",   "space + case"),
    ("SDS 011", "SDS011",   "space only"),
    ("MPU-6050", "MPU6050", "separator (hyphen)"),
    ("µg/m³", "μg/m³",      "MICRO SIGN vs GREEK SMALL LETTER MU"),
    ("  Sound Level Meter ", "soundlevelmeter", "whitespace + case"),
])
def test_drift_variants_are_the_same_entity(a, b, why):
    assert same_entity(a, b), f"should merge ({why})"
    assert natural_key(a) == natural_key(b)


def test_sds011_family_collapses_to_one_key():
    """Paper 1's flagship example, re-asserted at the identity layer.

    Regression guard: a previous implementation tokenized on RAW whitespace before
    normalizing, so 'SDS 011' (the most common spelling in the snapshot, n=239) keyed as
    '011' while 'sds011' keyed as 'sds011' — forking one sensor into two, which is the
    exact failure Paper 1 warns about when a second call site normalizes differently.
    """
    keys = {natural_key(s) for s in ("SDS 011", "SDS011", "sds011")}
    assert keys == {"sds011"}


# --------------------------------------------------------------------------- #
# REFUSAL: verified-distinct real parts must never merge.
#
# Ground truth for every pair below is hand-verified against manufacturer datasheets;
# the audit trail (source URL, lifecycle, access date) is in data/ground_truth_catalog.csv.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("a, b, why", [
    ("bme280", "bmp280",   "both real Bosch parts; BME280 has humidity, BMP280 does not"),
    ("bme280", "bme680",   "both real Bosch parts; BME680 adds a gas sensor"),
    ("bmp085", "bmp280",   "both real Bosch parts, different generations"),
    ("hdc1008", "hdc1080", "STAR WITNESS: two real TI parts, one transposition apart"),
    ("dht11", "dht22",     "both real; different accuracy classes"),
    ("scd30", "sgp30",     "both real Sensirion; NDIR CO2 vs metal-oxide VOC/eCO2"),
    ("sgp30", "sps30",     "both real Sensirion; VOC vs particulate matter"),
])
def test_distinct_real_parts_never_merge(a, b, why):
    """Merging these would be a silent collision: two real sensors averaged into one."""
    assert not same_entity(a, b), f"must NOT merge ({why})"
    assert natural_key(a) != natural_key(b)


def test_star_witness_stays_separate():
    """hdc1008 / hdc1080 is the pair that defeats every measured metric.

    Both are real Texas Instruments parts. Every string-similarity metric tested scores
    them as similar as, or more similar than, a genuine typo — so any fuzzy matcher tuned
    to catch typos merges these two. The normalize-only rule cannot, by construction.
    """
    assert not same_entity("hdc1008", "hdc1080")


# --------------------------------------------------------------------------- #
# REFUSAL: typos are DEFERRED, not merged and not dismissed.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("real, typo", [
    ("sds011", "sds1001"),
    ("hdc1080", "hhdc1080"),
    ("hdc1080", "hc1080"),
])
def test_typos_are_deferred_not_merged(real, typo):
    """A human would call these the same part. The layer still refuses to.

    Not conservatism for its own sake: the judgement requires a manufacturer catalog,
    which is external to the strings and changes over time. So the pair is routed to
    review rather than guessed at.
    """
    assert not same_entity(real, typo)
    assert needs_review(real, typo), "an unmerged pair must be visible to the label queue"


def test_needs_review_is_the_complement_of_certainty():
    """False from same_entity() means 'not proven identical', never 'proven different'.

    needs_review() exists so that distinction is explicit in the API rather than implied
    by an absence.
    """
    assert not needs_review("SDS 011", "sds011")     # certain -> no review needed
    assert needs_review("hdc1008", "hdc1080")        # unresolved -> review
    assert needs_review("sds011", "sds1001")         # unresolved -> review


# --------------------------------------------------------------------------- #
# Key derivation.
# --------------------------------------------------------------------------- #
def test_natural_key_is_pure_and_reproducible():
    """Same content in, same key out — no dependence on order or a counter."""
    assert natural_key("SDS 011") == natural_key("SDS 011")
    assert natural_key("SDS 011") == "sds011"


def test_natural_key_never_returns_empty():
    """A key must always be usable as an identity, even for degenerate input."""
    assert natural_key("") == "unknown"
    assert natural_key("   ") == "unknown"


def test_meaningful_punctuation_still_separates():
    """The decimal point carries identity (Paper 1): PM2.5 and PM25 are different."""
    assert not same_entity("PM2.5", "PM25")


def test_describe_explains_the_decision():
    out = describe("SDS 011")
    assert out == {"input": "SDS 011", "normalized": "sds011", "natural_key": "sds011"}
