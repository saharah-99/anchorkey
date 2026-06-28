"""
Tests for the normalizer.

Two kinds of test live here:

  * EXAMPLE tests: real strings pulled from public openSenseMap data, asserting the
    exact convergence the paper claims (the four SDS011 spellings, the µ-vs-µ units).

  * A PROPERTY test (using Hypothesis): for ANY string at all, normalizing twice equals
    normalizing once. This is the idempotency guarantee the paper leans on, checked
    against thousands of random inputs rather than a handful we thought of.
"""

from hypothesis import given, strategies as st

from anchorkey import normalize


# --------------------------------------------------------------------------- #
# Example tests — the cases from the paper, on real data.
# --------------------------------------------------------------------------- #
def test_sds011_spellings_converge():
    # Three of the four observed spellings are the SAME device and must collapse.
    assert normalize("SDS 011") == "sds011"
    assert normalize("SDS011") == "sds011"
    assert normalize("sds011") == "sds011"


def test_sds1001_typo_stays_separate():
    # The transposed-digit typo is a DIFFERENT string; normalization must NOT merge it.
    # (Catching it is matching.py's job, via fuzzy comparison — see test_matching.py.)
    assert normalize("SDS1001") != normalize("SDS011")


def test_micro_sign_vs_greek_mu_converge():
    # "µg/m³" written with MICRO SIGN (U+00B5) and with GREEK SMALL LETTER MU (U+03BC)
    # look identical but are byte-different; NFKC must make them the same key.
    micro = normalize("µg/m³")   # µg/m³
    greek = normalize("μg/m³")   # μg/m³
    assert micro == greek


def test_meaningful_punctuation_is_preserved():
    # The dot in PM2.5 carries identity; it must survive so PM2.5 and PM25 stay distinct.
    assert normalize("PM2.5") != normalize("PM25")


def test_whitespace_and_case_removed():
    assert normalize("  Sound Level Meter ") == normalize("soundlevelmeter")


# --------------------------------------------------------------------------- #
# Property test — idempotency for ANY input.
# --------------------------------------------------------------------------- #
@given(st.text())
def test_idempotent(value):
    # f(f(x)) == f(x): re-normalizing an already-normalized key changes nothing.
    once = normalize(value)
    twice = normalize(once)
    assert once == twice
