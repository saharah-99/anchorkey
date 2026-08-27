#!/usr/bin/env python3
"""
keyshape_sample.py — profile the 99 normalized keys by shape.

This answers a question a reader asks before accepting anything else in Paper 2: what KIND
of string is under discussion? Record-linkage results about personal names and postal
addresses are well established, and if these identifiers were names, the paper would be
restating known work. They are not. The majority are short part-number codes drawn from a
manufacturer's catalog, and that difference in kind is what makes the failure structural
rather than statistical.

The classification here is DELIBERATELY SYNTACTIC. Every key is placed by pattern alone,
with no domain knowledge consulted. That constraint matters: a taxonomy that needed a parts
catalog to sort its own rows would concede Paper 2's conclusion in the setup, and the
categories would not be reproducible by a reader. Syntax is checkable; judgement is not.

The profile is also honest about what it finds. The residual is not a clean population of
part numbers. It contains descriptive words, placeholders, German-language phrases, and at
least one string joining two part numbers. The claim Paper 2 needs is that the MAJORITY are
short digit-bearing codes and that the scored pairs all come from that subpopulation, not
that the residual is uniform.

Usage:
    git clone https://github.com/saharah-99/anchorkey && pip install -e anchorkey
    python keyshape_sample.py
"""

from __future__ import annotations

import importlib.util
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

# The scored pairs, to confirm they all sit in the code-shaped subpopulation.
_spec = importlib.util.spec_from_file_location("sep", HERE / "separability_sample.py")
sep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sep)


# --------------------------------------------------------------------------- #
# Shape classification. Syntactic only, applied in order, first match wins.
# --------------------------------------------------------------------------- #
_CODE = re.compile(r"^[a-z]+\d[a-z0-9]*$")   # alpha prefix then at least one digit
_ALPHA = re.compile(r"^[a-z]+$")             # letters only
_DIGIT = re.compile(r"^\d+$")                # digits only

SHAPES = [
    ("part-number code", _CODE.match,
     "alpha prefix followed by digits, e.g. `bme280`, `sds011`, `hdc1080`"),
    ("alphabetic word", _ALPHA.match,
     "letters only, e.g. `gps`, `microphone`, `regenmesser`"),
    ("bare number", _DIGIT.match,
     "digits only, e.g. `1`"),
    ("other", lambda s: True,
     "anything else: symbols, joined codes, phrases"),
]


def classify(key: str) -> str:
    for name, test, _ in SHAPES:
        if test(key):
            return name
    return "other"


def load() -> Counter:
    boxes = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    keys: Counter[str] = Counter()
    for box in boxes:
        for s in box.get("sensors", []) or []:
            st = s.get("sensorType")
            if st:
                keys[normalize(st)] += 1
    return keys


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not SNAPSHOT.exists():
        print(f"Missing {SNAPSHOT}. Run pull_drift_sample.py first.", file=sys.stderr)
        return 2

    keys = load()
    n_keys = len(keys)
    n_obs = sum(keys.values())
    by_shape: dict[str, list[str]] = {name: [] for name, _, _ in SHAPES}
    for k in keys:
        by_shape[classify(k)].append(k)

    # ----------------------------------------------------------------- #
    print("Shape of the residual: what kind of string is under discussion?")
    print(f"{n_keys} normalized keys over {n_obs} observations.\n")
    print(f"{'shape':20} {'keys':>6} {'% keys':>8} {'observations':>13} {'% obs':>7}")
    print("-" * 60)
    for name, _, _ in SHAPES:
        ks = by_shape[name]
        obs = sum(keys[k] for k in ks)
        print(f"{name:20} {len(ks):>6} {100 * len(ks) / n_keys:>7.0f}% "
              f"{obs:>13} {100 * obs / n_obs:>6.0f}%")

    code_keys = by_shape["part-number code"]
    code_obs = sum(keys[k] for k in code_keys)

    # ----------------------------------------------------------------- #
    print("\nLength (normalized keys are short, which is why a single edit matters):")
    lens = sorted(len(k) for k in keys)
    code_lens = sorted(len(k) for k in code_keys)
    print(f"  all keys        : min {lens[0]}, median {lens[len(lens) // 2]}, "
          f"mean {sum(lens) / len(lens):.1f}, max {lens[-1]}")
    print(f"  part-number only: min {code_lens[0]}, median {code_lens[len(code_lens) // 2]}, "
          f"mean {sum(code_lens) / len(code_lens):.1f}, max {code_lens[-1]}")
    print(f"  keys of 10 characters or fewer: {sum(1 for x in lens if x <= 10)}/{n_keys}")

    # ----------------------------------------------------------------- #
    print("\nThe residual is NOT a uniform population of part numbers. Examples of what")
    print("else is in it, all real values from the snapshot:")
    for name in ("alphabetic word", "bare number", "other"):
        sample = sorted(by_shape[name], key=lambda k: (-keys[k], k))[:6]
        if sample:
            print(f"  {name:16}: " + ", ".join(repr(s) for s in sample))
    print("\n  Distinguishing a placeholder such as 'zahl' or 'nein' from a part name inside")
    print("  the alphabetic group would itself require the manufacturer catalog. The")
    print("  classification above avoids that by testing syntax only, so a reader can")
    print("  reproduce every row without domain knowledge.")

    # ----------------------------------------------------------------- #
    scored = {s for pair in sep.DISTINCT_PAIRS + sep.TYPO_PAIRS for s in pair}
    scored_shapes = Counter(classify(s) for s in scored)
    print(f"\nScoped claim check: all {len(scored)} strings in the scored pairs are")
    print(f"part-number codes -> {dict(scored_shapes)}")

    # ----------------------------------------------------------------- #
    EXPECTED = {
        "normalized keys":            (n_keys, 99),
        "part-number code keys":      (len(code_keys), None),
        "part-number code is plural": (len(code_keys) >= 2, True),
        "codes are the largest group": (
            len(code_keys) == max(len(v) for v in by_shape.values()), True),
        "codes dominate by volume":   (code_obs / n_obs > 0.5, True),
        "scored pairs are all codes": (
            set(scored_shapes) == {"part-number code"}, True),
    }
    print("\nCross-check:")
    ok = True
    for label, (got, want) in EXPECTED.items():
        if want is None:
            print(f"  [ -- ] {label:28s} computed={got}")
            continue
        flag = "ok " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{flag}] {label:28s} got={got} expected={want}")
    print("  => ALL MATCH" if ok else "  => MISMATCH")

    print(f"\nConclusion: {len(code_keys)} of {n_keys} keys ({100 * len(code_keys) / n_keys:.0f}%) are "
          f"part-number codes, carrying {100 * code_obs / n_obs:.0f}% of observations.")
    print("These are short codes drawn from manufacturer catalogs, not personal names or")
    print("postal addresses. That distinction is what Paper 2's argument rests on.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
