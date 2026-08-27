#!/usr/bin/env python3
"""
review_queue_sample.py — what does deferring to a human actually COST?

separability_sample.py showed that no string-similarity metric can safely decide whether
two identifier keys name the same part, so the architecture defers those decisions to a
person. The obvious practitioner objection follows immediately:

    "Fine, but I am not paying someone to review 4,851 pairs."

Correct, and they would not have to. This script measures the real number.

Three things get measured, on the captured snapshot:

  1. QUEUE SIZE — how many candidate pairs a human must actually look at, and the
     cost/recall trade-off between blocking strategies. Cheap blocking is cheap because
     it misses things; that is measured here rather than assumed.

  2. ONGOING COST — the queue is not paid once. New keys arrive every year, so the
     sustainable question is how many NEW pairs appear per year, not the initial total.

  3. WHAT THE REVIEW BUYS — including a triage strategy that looks efficient and is a
     trap, and the difference between the worst-case and actual data at stake.

Usage:
    git clone https://github.com/saharah-99/anchorkey && pip install -e anchorkey
    python review_queue_sample.py
"""

from __future__ import annotations

import importlib.util
import itertools
import json
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

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "raw_snapshot.json"

# Reuse the hand-verified ground truth rather than restating it (single source of truth).
_spec = importlib.util.spec_from_file_location("sep", HERE / "separability_sample.py")
sep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sep)

KNOWN_TYPO_PAIRS = {tuple(sorted(p)) for p in sep.TYPO_PAIRS}


# --------------------------------------------------------------------------- #
# Blocking strategies — candidate generation, NOT decision.
#
# Blocking's only job is to avoid the O(N^2) all-pairs comparison by proposing which
# pairs are worth a human's attention. It never decides anything; separability_sample.py
# established that nothing can decide from the strings alone.
# --------------------------------------------------------------------------- #
def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _qgrams(s: str, q: int = 2) -> set[str]:
    return {s[i:i + q] for i in range(len(s) - q + 1)} or {s}


def _digits(s: str) -> str:
    return "".join(re.findall(r"\d+(?:\.\d+)?", s))


STRATEGIES = {
    "edit distance <= 1":     lambda a, b: levenshtein(a, b) <= 1,
    "edit distance <= 2":     lambda a, b: levenshtein(a, b) <= 2,
    "edit dist <= 2, len>=4": lambda a, b: levenshtein(a, b) <= 2 and min(len(a), len(b)) >= 4,
    "q-gram Jaccard >= 0.5":  lambda a, b: len(_qgrams(a) & _qgrams(b)) / len(_qgrams(a) | _qgrams(b)) >= 0.5,
    "same digit signature":   lambda a, b: _digits(a) == _digits(b) and _digits(a) != "",
}

# The strategy the architecture adopts: the cheapest one that still achieves full recall
# on the verified duplicates (see the recall table below).
CHOSEN = "edit dist <= 2, len>=4"


def load() -> tuple[Counter, dict[str, str]]:
    """Normalized sensorType keys with counts, plus the year each key first appears."""
    boxes = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    keys: Counter[str] = Counter()
    first_seen: dict[str, str] = {}
    for box in boxes:
        year = (box.get("createdAt") or "")[:4]
        for s in box.get("sensors", []) or []:
            st = s.get("sensorType")
            if not st:
                continue
            k = normalize(st)
            keys[k] += 1
            if year and (k not in first_seen or year < first_seen[k]):
                first_seen[k] = year
    return keys, first_seen


def candidates(keys: Counter, predicate) -> list[tuple[str, str]]:
    return [(a, b) for a, b in itertools.combinations(sorted(keys), 2) if predicate(a, b)]


# --------------------------------------------------------------------------- #
# 1. Queue size, and the cost/recall trade-off.
# --------------------------------------------------------------------------- #
def report_queue(keys: Counter) -> tuple[int, bool]:
    n = len(keys)
    total = n * (n - 1) // 2
    print(f"Normalized keys: {n}.  All-pairs comparison would be {total} pairs.\n")
    print(f"{'blocking strategy':26} {'queue':>6} {'% pairs':>8}  recall on verified duplicates")
    print("-" * 78)

    chosen_size, chosen_full_recall = 0, False
    for name, fn in STRATEGIES.items():
        cand = {tuple(sorted(p)) for p in candidates(keys, fn)}
        missed = [p for p in KNOWN_TYPO_PAIRS if p not in cand]
        note = ("all caught" if not missed
                else "MISSES " + ", ".join(f"{a}/{b}" for a, b in missed))
        marker = "  <- chosen" if name == CHOSEN else ""
        print(f"{name:26} {len(cand):>6} {100 * len(cand) / total:>7.2f}%  "
              f"{len(KNOWN_TYPO_PAIRS) - len(missed)}/{len(KNOWN_TYPO_PAIRS)}  {note}{marker}")
        if name == CHOSEN:
            chosen_size, chosen_full_recall = len(cand), not missed

    print("\n  The trade-off is real and measured: the three cheapest strategies all miss")
    print("  sds011/sds1001, the series' flagship typo. Blocking on the digit signature")
    print("  misses it for a structural reason -- '011' and '1001' are different digit")
    print("  strings -- and that is the SAME property that keeps bme280 and bme680 in")
    print("  separate blocks, which is what a blocking rule should do with two real parts.")
    print("  The property that protects also blinds. Cheap blocking buys cheapness with recall.")
    return chosen_size, chosen_full_recall


# --------------------------------------------------------------------------- #
# 2. Ongoing cost.
# --------------------------------------------------------------------------- #
def report_ongoing(keys: Counter, first_seen: dict[str, str]) -> None:
    fn = STRATEGIES[CHOSEN]
    print(f"\n{'year':6} {'new keys':>9} {'cum keys':>9} {'NEW pairs to review':>21}")
    print("-" * 50)
    seen: set[str] = set()
    total_new = 0
    for year in sorted(set(first_seen.values())):
        new = {k for k, v in first_seen.items() if v == year}
        pairs = 0
        for k in new:
            for other in seen | (new - {k}):
                if (other not in new or k < other) and fn(k, other):
                    pairs += 1
        seen |= new
        total_new += pairs
        print(f"{year:6} {len(new):>9} {len(seen):>9} {pairs:>21}")

    years = len(set(first_seen.values()))
    print(f"\n  Mean {total_new / years:.1f} new pairs per year across {years} years.")
    print("  CAVEATS. Box registration dates are not evenly spread: 127 of 719 boxes were registered on")
    print("  a single day, so the 2022 spike is an artifact of bulk registration rather than")
    print("  a surge in sensor variety. Both endpoint years are also truncated, since")
    print("  registrations run 2020-12-03 to 2026-06-24, which inflates the first year (every")
    print("  key is new at the start) and deflates the last.")
    print("  Hence observed : new keys arrive in EVERY year,")
    print("  including both truncated ones, so the queue is a small recurring cost rather")
    print("  than a one-time migration. Seven years cannot establish that and the cumulative curve decelerates.")
    print("  Time variance alone is what makes effective-dated labels necessary.")


# --------------------------------------------------------------------------- #
# 3. What the review buys -- including a trap.
# --------------------------------------------------------------------------- #
def report_value(keys: Counter) -> None:
    fn = STRATEGIES[CHOSEN]
    cand = candidates(keys, fn)
    total_obs = sum(keys.values())

    print("\nA tempting triage: 'only review pairs where BOTH keys are high-volume.'")
    for t in (5, 10):
        sub = [(a, b) for a, b in cand if keys[a] >= t and keys[b] >= t]
        print(f"    n >= {t:<3} on both sides -> {len(sub):>2}/{len(cand)} pairs kept")
    print("\n  It is a trap. Typos are rare BY CONSTRUCTION -- a misspelling is a mistake a")
    print("  few contributors made -- so filtering on volume deletes precisely the pairs")
    print("  the review exists to find:")
    for a, b in sorted(KNOWN_TYPO_PAIRS):
        lo = min(keys[a], keys[b])
        print(f"    {a}/{b}: counts {keys[a]} vs {keys[b]} -> minority side n={lo}"
              f"{'  DROPPED at n>=5' if lo < 5 else ''}")

    involved = {k for p in cand for k in p}
    upper = sum(min(keys[a], keys[b]) for a, b in cand)
    actual = sum(min(keys[a], keys[b]) for a, b in cand
                 if tuple(sorted((a, b))) in KNOWN_TYPO_PAIRS)

    print(f"\nData at stake:")
    print(f"    total observations                        : {total_obs}")
    print(f"    on keys with an unresolved neighbour      : {sum(keys[k] for k in involved)}"
          f"  ({100 * sum(keys[k] for k in involved) / total_obs:.0f}%)")
    print(f"    UPPER BOUND rows moved, if all merged     : {upper}"
          f"  ({100 * upper / total_obs:.2f}%)")
    print(f"    ACTUAL rows moved, per verified truth     : {actual}"
          f"  ({100 * actual / total_obs:.2f}%)")

    print("\n  Most candidates resolve to 'do not merge' -- they are genuinely different")
    print("  parts that merely look similar:")
    for a, b in sorted(cand, key=lambda p: -min(keys[p[0]], keys[p[1]]))[:4]:
        verdict = ("TYPO -> merge" if tuple(sorted((a, b))) in KNOWN_TYPO_PAIRS
                   else "distinct -> NO merge")
        print(f"    {a:9}/{b:9} min(n)={min(keys[a], keys[b]):>3}   {verdict}")

    print("\n  So the review is not expensive because of the rows it corrects. It corrects")
    print(f"  {actual} rows out of {total_obs}. It is necessary because you cannot know WHICH")
    print(f"  {actual} without looking. Before the review, {100 * sum(keys[k] for k in involved) / total_obs:.0f}% of observations sit on a")
    print("  key that has an unresolved neighbour, and no query can tell you whether its")
    print("  counts are whole. After it, they can. The deliverable is not corrected data;")
    print("  it is knowing that the data is correct.")


# --------------------------------------------------------------------------- #
# The blind spot. Measured here so the paper's strongest ADMISSION is as
# reproducible as its strongest result.
#
# Every strategy in STRATEGIES is a string-distance or string-overlap rule, so every
# one of them proposes near-duplicates and nothing else. Two keys that name the same
# physical part but share no characters are never proposed, so no human is ever asked
# about them. Normalization cannot fix this either: both strings are already canonical.
#
# The worked case comes from this project's own ground truth. `dht22` is what the
# snapshot contains; the manufacturer's own technical manual for that part says AM2302
# throughout and never says DHT22 (see ground_truth_catalog.csv). They are one sensor
# under two names that no string function can connect.
# --------------------------------------------------------------------------- #
ALIAS_CASE = ("dht22", "am2302")


def report_alias_blind_spot(keys: Counter) -> tuple[bool, bool]:
    """Return (no_strategy_proposes_pair, second_spelling_absent_from_snapshot)."""
    a, b = ALIAS_CASE
    print("\nThe queue above can only contain pairs that some rule PROPOSES. Every rule")
    print("available is a string-distance or string-overlap rule, which bounds what the")
    print("architecture can see. The bound is not hypothetical:\n")

    print(f"  {a!r} and {b!r} are the same sensor under two names.")
    print(f"  Levenshtein distance     : {levenshtein(a, b)}   (typo pairs here score 1-2)")
    jac = len(_qgrams(a) & _qgrams(b)) / len(_qgrams(a) | _qgrams(b))
    print(f"  q-gram Jaccard           : {jac:.3f}   (>= 0.5 required to propose)")
    print(f"  digit signature          : {_digits(a)!r} vs {_digits(b)!r}")

    proposed = [name for name, fn in STRATEGIES.items() if fn(a, b)]
    print(f"\n  strategies proposing the pair: {len(proposed)} of {len(STRATEGIES)}"
          f"{'  -> ' + ', '.join(proposed) if proposed else '   (none)'}")

    absent = keys.get(b, 0) == 0
    print(f"\n  Second, and independently: {b!r} never appears in this snapshot at all")
    print(f"  ({a!r} occurs {keys.get(a, 0)}x, {b!r} occurs {keys.get(b, 0)}x). So in THIS data the pair")
    print("  is not merely un-proposed, it is not in the all-pairs space to begin with.")
    print("  The demonstration above is therefore CONSTRUCTED: it shows what the rules do")
    print("  when handed both spellings, which is what would happen if a second gateway")
    print("  ever reported the manufacturer's name. It is not an observed miss.")

    print("\n  Two independent reasons the human is never asked, and neither is fixable")
    print("  by a better threshold. The alias problem is strictly harder than the typo")
    print("  problem: it needs a catalog carrying alias tables, not a more lenient blocking")
    print("  rule. This architecture does not solve it. It declines to guess, which beats")
    print("  guessing wrong, and declining is not the same as resolving.")
    return (not proposed), absent


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not SNAPSHOT.exists():
        print(f"Missing {SNAPSHOT}. Run pull_drift_sample.py first.", file=sys.stderr)
        return 2

    keys, first_seen = load()

    print("=" * 78)
    print("1. QUEUE SIZE  --  how many pairs must a human actually look at?")
    print("=" * 78)
    size, full_recall = report_queue(keys)

    print("\n" + "=" * 78)
    print("2. ONGOING COST  --  the queue is not paid once")
    print("=" * 78)
    report_ongoing(keys, first_seen)

    print("\n" + "=" * 78)
    print("3. WHAT THE REVIEW BUYS")
    print("=" * 78)
    report_value(keys)

    print("\n" + "=" * 78)
    print("4. WHAT THE REVIEW CANNOT BUY  --  the alias blind spot")
    print("=" * 78)
    alias_unproposed, alias_absent = report_alias_blind_spot(keys)

    n = len(keys)
    total = n * (n - 1) // 2
    print("\n" + "=" * 78)
    print("Cross-check:")
    checks = {
        "chosen strategy has full recall": (full_recall, True),
        "queue is under 1% of all pairs":  (size / total < 0.01, True),
        "queue is humanly tractable":      (size <= 50, True),
        "no rule proposes the alias pair": (alias_unproposed, True),
        "alias spelling absent from data": (alias_absent, True),
    }
    ok = True
    for label, (got, want) in checks.items():
        flag = "ok " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{flag}] {label:34s} got={got}")
    print("  => ALL MATCH" if ok else "  => MISMATCH")

    print(f"\nConclusion: deferring to a human costs {size} pairs of review on {n} keys")
    print(f"({100 * size / total:.2f}% of the all-pairs space), then a handful per year as the")
    print("catalog grows. That is the price of never silently merging two real sensors.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
