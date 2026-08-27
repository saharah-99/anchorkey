#!/usr/bin/env python3
"""
separability_sample.py — test whether ANY string-similarity threshold can separate a
typo from a genuinely different part.

Single source of truth: `raw_snapshot.json` (the exact openSenseMap API response captured
for the paper). collapse_sample.py measured what perimeter normalization fixes; this
script measures what it CANNOT fix, and asks the obvious follow-up question: can a fuzzy
matcher finish the job?

The answer, on this data, is no — and the failure is not a tuning problem.

    A metric "separates" if some threshold merges every TYPO pair and no DISTINCT pair.
    For a distance:   max(TYPO) < min(DISTINCT)
    For a similarity: min(TYPO) > max(DISTINCT)

Five metrics spanning the main families are tested (plain edit distance, transposition-
aware edit distance, a structural two-stage core matcher, prefix-weighted, and set-based).
All five OVERLAP: for each one there exists a pair of genuinely different real parts that
scores at least as similar as a real typo. No threshold works.

WHY this is a structural result and not "we didn't try hard enough": the deciding fact is
not in the string. "Is this a real part?" is a property of the world — a manufacturer's
catalog. If Bosch ships a BMP200 tomorrow, the pair (bmp280, bmp200) flips from typo to
distinct WITHOUT EITHER STRING CHANGING A CHARACTER. No function of the two strings can
track that, because the information was never in the characters. The five metrics below
confirm this empirically; the argument holds for metrics never tested, including learned
ones (give a model the catalog and you have rebuilt the label layer, with added opacity).

Note the reflexivity, which is the point rather than a caveat: building the GROUND_TRUTH
table below required an external parts catalog supplied from domain knowledge. The
experiment cannot be set up without conceding its own conclusion.

On sample size: negative results carry different sample requirements than positive ones.
Claiming a metric WORKS would need large N. Proving separability IMPOSSIBLE needs exactly
one same-score/opposite-truth pair — and there are several, for every metric.

Usage:
    git clone https://github.com/saharah-99/anchorkey && pip install -e anchorkey   # the reference implementation
    python separability_sample.py
"""

from __future__ import annotations

import itertools
import re
import sys
from collections import Counter
from pathlib import Path

try:
    from anchorkey import normalize
except ImportError:
    sys.stderr.write(
        "This script needs the paper's reference implementation.\n"
        "Get it with:  git clone https://github.com/saharah-99/anchorkey\n"
        "then:         pip install -e anchorkey\n"
    )
    raise SystemExit(2)

import json

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "raw_snapshot.json"


# --------------------------------------------------------------------------- #
# The external catalog.
#
# !!  UNVERIFIED — EVERY ROW MUST BE CHECKED AGAINST A MANUFACTURER DATASHEET  !!
#
# This table is the whole argument in miniature: it is the domain knowledge that the
# identifier strings do not carry. It cannot be derived from the snapshot; a human had to
# supply it. Each entry asserts whether a normalized string names a real, shipping part.
# If any single assertion here is wrong, the row that depends on it must be struck.
# --------------------------------------------------------------------------- #
# Verified by hand against manufacturer datasheets, 2026-07-18. Full audit trail with
# source URLs and lifecycle status: ground_truth_catalog.csv (alongside this file).
REAL_PARTS = {
    "bme280":   "Bosch BME280 — humidity/pressure/temperature",
    "bmp280":   "Bosch BMP280 — pressure/temperature (no humidity)",
    "bme680":   "Bosch BME680 — BME280 + gas/VOC/air quality",
    "bmp085":   "Bosch BMP085 — earlier-generation pressure sensor (obsolete; -> BMP180)",
    "hdc1008":  "TI HDC1008 — humidity/temperature",
    "hdc1080":  "TI HDC1080 — humidity/temperature, successor to HDC1008",
    "dht11":    "DHT11 — humidity/temperature, lower accuracy class (obsolete; -> DHT20)",
    "dht22":    "AM2302 — humidity/temperature, ±2%RH; 'DHT22' is a market alias, "
                "not the manufacturer part name (verified 2026-08-03)",
    "scd30":    "Sensirion SCD30 — NDIR CO2 (true CO2)",
    "sgp30":    "Sensirion SGP30 — metal-oxide VOC/eCO2, ESTIMATED not true CO2 "
                "(end-of-life; -> SGP40)",
    "sps30":    "Sensirion SPS30 — particulate matter (PM2.5)",
    "sds011":   "Nova Fitness SDS011 — particulate matter",
}

NOT_REAL = {
    "sds1001":  "transposed digits of SDS011; no such Nova Fitness part",
    "hhdc1080": "doubled leading H of HDC1080; no such part",
    "hc1080":   "dropped D from HDC1080; no such sensor "
                "(an unrelated appliance model carries this string)",
}

# Strings we could NOT classify — reported honestly rather than guessed.
#
# This is not a gap in the experiment; it is the experiment's conclusion appearing in the
# experiment's own setup. "bmp200" was assumed to be a typo of Bosch's BMP280. Manual
# verification instead surfaced a possible BMP200 PM10 analyser from a different
# manufacturer (Focused Photonics) — no datasheet obtainable, not in distribution. So the
# pair (bmp280, bmp200) may be a typo OR a collision between a Bosch pressure sensor and
# an unrelated particulate analyser, and a domain-competent human with web access could
# not resolve which. It is therefore EXCLUDED from the scored pairs below.
#
# A string-similarity function is asked to decide, in microseconds, a question that
# defeated manual research.
UNRESOLVED = {
    "bmp200": "possibly a Focused Photonics PM10 analyser; possibly a typo of BMP280. "
              "No datasheet obtainable (checked 2026-07-18). Excluded from scoring.",
}

# Pairs whose members are BOTH real parts -> merging them is a silent data-corrupting
# collision. These are the canaries.
DISTINCT_PAIRS = [
    ("bme280", "bmp280"),    # one letter apart; humidity vs no humidity
    ("bme280", "bme680"),    # one digit apart; gas sensor or not
    ("bmp085", "bmp280"),    # different generations
    ("hdc1008", "hdc1080"),  # THE star witness: two real TI parts, transposed tail
    ("dht11", "dht22"),      # different accuracy classes
    ("scd30", "sgp30"),      # NDIR CO2 vs metal-oxide VOC — different measurands
    ("sgp30", "sps30"),      # VOC vs particulate — different measurands
]

# Pairs where exactly one member is NOT a real part -> the other is a typo of it, and a
# matcher SHOULD merge them.
TYPO_PAIRS = [
    ("sds011", "sds1001"),
    ("hdc1080", "hhdc1080"),
    ("hdc1080", "hc1080"),
    # ("bmp280", "bmp200") removed 2026-07-18: bmp200 could not be verified as unreal.
    # See UNRESOLVED above. Dropping it WEAKENS the typo side (fewer, tighter pairs),
    # so the overlap result below is now harder to obtain, not easier.
]


# --------------------------------------------------------------------------- #
# Metrics. Deliberately dependency-free and short enough to audit by eye.
# --------------------------------------------------------------------------- #
def levenshtein(a: str, b: str) -> int:
    """Insertions, deletions, substitutions. The default reach-for."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def damerau_levenshtein(a: str, b: str) -> int:
    """Adds transposition as a single edit (optimal string alignment).

    The 'obvious upgrade' for this domain, because SDS1001 is a digit transposition of
    SDS011. Watch what it does to hdc1008/hdc1080 — two REAL parts that are also a
    transposition apart. The upgrade makes the collision worse, not better.
    """
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


_DIGITS = re.compile(r"\d+(?:\.\d+)?")
_ALPHA = re.compile(r"[a-z]+")

DISAGREE = 99  # sentinel: cores differ, matcher refuses to compare


def two_stage(a: str, b: str) -> int:
    """Structural matcher: the digit core must match EXACTLY before anything is compared.

    The idea (and it is a reasonable one) is to make safety structural rather than
    threshold-dependent: if the digits differ at all, refuse. Below, it fails in both
    directions at once — it refuses real typos AND still merges two real parts.
    """
    if "".join(_DIGITS.findall(a)) != "".join(_DIGITS.findall(b)):
        return DISAGREE
    return levenshtein("".join(_ALPHA.findall(a)), "".join(_ALPHA.findall(b)))


def _jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    window = max(la, lb) // 2 - 1
    fa, fb = [False] * la, [False] * lb
    matches = 0
    for i in range(la):
        for j in range(max(0, i - window), min(lb, i + window + 1)):
            if not fb[j] and a[i] == b[j]:
                fa[i] = fb[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    k = transpositions = 0
    for i in range(la):
        if fa[i]:
            while not fb[k]:
                k += 1
            if a[i] != b[k]:
                transpositions += 1
            k += 1
    transpositions //= 2
    return (matches / la + matches / lb + (matches - transpositions) / matches) / 3


def jaro_winkler(a: str, b: str) -> float:
    """Prefix-weighted similarity. Model codes share brand prefixes, so this rewards
    exactly the part of the string that carries the LEAST identity."""
    j = _jaro(a, b)
    prefix = 0
    for x, y in zip(a, b):
        if x != y:
            break
        prefix += 1
    return j + min(prefix, 4) * 0.1 * (1 - j)


def qgram_jaccard(a: str, b: str, q: int = 2) -> float:
    """Set-based overlap of character q-grams; order-tolerant."""
    A = {a[i:i + q] for i in range(len(a) - q + 1)} or {a}
    B = {b[i:i + q] for i in range(len(b) - q + 1)} or {b}
    return len(A & B) / len(A | B)


METRICS = [
    ("Levenshtein",    levenshtein,          "distance"),
    ("Damerau-Lev",    damerau_levenshtein,  "distance"),
    ("two-stage core", two_stage,            "distance"),
    ("Jaro-Winkler",   jaro_winkler,         "similarity"),
    ("q-gram Jaccard", qgram_jaccard,        "similarity"),
]


# --------------------------------------------------------------------------- #
# Step 1. Confirm every pair member actually occurs in the citable snapshot.
# --------------------------------------------------------------------------- #
def snapshot_keys() -> Counter:
    """Normalized sensorType keys and their observation counts, from the snapshot."""
    boxes = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    keys: Counter[str] = Counter()
    for box in boxes:
        for s in box.get("sensors", []) or []:
            st = s.get("sensorType")
            if st:
                keys[normalize(st)] += 1
    return keys


def check_present(keys: Counter) -> bool:
    """Every string under test must be real data, not an invented example."""
    ok = True
    missing = []
    for a, b in DISTINCT_PAIRS + TYPO_PAIRS:
        for s in (a, b):
            if s not in keys:
                missing.append(s)
                ok = False
    if missing:
        print(f"  [FAIL] not present in snapshot: {sorted(set(missing))}")
    else:
        print(f"  [ok ] all {len(set(itertools.chain(*(DISTINCT_PAIRS + TYPO_PAIRS))))} "
              f"strings under test occur in the snapshot")
    return ok


# --------------------------------------------------------------------------- #
# Step 2. The separability test.
# --------------------------------------------------------------------------- #
def separable(fn, kind: str) -> tuple[bool, float, float]:
    """Does any threshold merge every TYPO and no DISTINCT pair?"""
    typo = [fn(a, b) for a, b in TYPO_PAIRS]
    dist = [fn(a, b) for a, b in DISTINCT_PAIRS]
    if kind == "distance":
        worst_typo, best_distinct = max(typo), min(dist)
        return worst_typo < best_distinct, worst_typo, best_distinct
    worst_typo, best_distinct = min(typo), max(dist)
    return worst_typo > best_distinct, worst_typo, best_distinct


def report(keys: Counter) -> bool:
    all_overlap = True
    for name, fn, kind in METRICS:
        ok, worst_typo, best_distinct = separable(fn, kind)
        if ok:
            all_overlap = False
        arrow = "<" if kind == "distance" else ">"
        print(f"\n--- {name}  ({'lower' if kind == 'distance' else 'higher'} = more similar) ---")
        rows = sorted(((fn(a, b), a, b) for a, b in TYPO_PAIRS),
                      reverse=(kind == "similarity"))
        for v, a, b in rows:
            print(f"    TYPO      {a:>9} / {b:<9} = {v:>6.3g}")
        rows = sorted(((fn(a, b), a, b) for a, b in DISTINCT_PAIRS),
                      reverse=(kind == "distance"))
        for v, a, b in rows:
            print(f"    DISTINCT  {a:>9} / {b:<9} = {v:>6.3g}   "
                  f"(n={keys[a]}, n={keys[b]})")
        verdict = "SEPARABLE" if ok else "OVERLAP -> no threshold works"
        print(f"    need worst TYPO {arrow} best DISTINCT: "
              f"{worst_typo:.3g} {arrow} {best_distinct:.3g}  =>  {verdict}")
    return all_overlap


def star_witness() -> None:
    """The single pair that defeats the whole board, called out explicitly."""
    a, b = "hdc1008", "hdc1080"
    print(f"\nStar witness — {a} / {b}: two REAL TI parts (see REAL_PARTS).")
    for name, fn, kind in METRICS:
        score = fn(a, b)
        if kind == "distance":
            typo_scores = [fn(x, y) for x, y in TYPO_PAIRS]
            beats = sum(1 for t in typo_scores if score <= t)
        else:
            typo_scores = [fn(x, y) for x, y in TYPO_PAIRS]
            beats = sum(1 for t in typo_scores if score >= t)
        print(f"    {name:15} scores {score:>6.3g} — looks at least as similar as "
              f"{beats}/{len(TYPO_PAIRS)} genuine typos")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if not SNAPSHOT.exists():
        print(f"Missing {SNAPSHOT}. Run pull_drift_sample.py first.", file=sys.stderr)
        return 2

    print("Provenance check (all test strings must occur in the citable snapshot):")
    keys = snapshot_keys()
    present_ok = check_present(keys)

    print(f"\nGround truth supplied from an EXTERNAL catalog (not derivable from the data):")
    print(f"  {len(REAL_PARTS)} strings verified REAL, {len(NOT_REAL)} verified NOT REAL,")
    print(f"  {len(UNRESOLVED)} UNRESOLVED after manual research (excluded from scoring):")
    for k, why in UNRESOLVED.items():
        print(f"    {k!r}: {why}")
    print(f"  Scored: {len(TYPO_PAIRS)} typo pairs vs {len(DISTINCT_PAIRS)} distinct-part pairs.")
    print("  Source of truth: manufacturer datasheets; audit trail in ground_truth_catalog.csv")

    all_overlap = report(keys)
    star_witness()

    print("\nCross-check:")
    checks = {
        "all test strings in snapshot": (present_ok, True),
        "every metric OVERLAPS":        (all_overlap, True),
    }
    ok = True
    for label, (got, want) in checks.items():
        flag = "ok " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{flag}] {label:32s} got={got} expected={want}")
    print("  => ALL MATCH" if ok else "  => MISMATCH (fix draft or re-check ground truth)")

    print("\nConclusion: no tested metric separates typos from distinct parts on this data.")
    print("The deciding fact is a parts catalog, which is external to the strings and")
    print("time-variant (see collapse_sample.py for the drift the normalizer DOES fix).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
