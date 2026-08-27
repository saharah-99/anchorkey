#!/usr/bin/env python3
# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
quickstart.py — see the whole idea in under a minute, on real public data.

Run:
    python examples/quickstart.py

It does four things:
  1. Shows the real spellings of one sensor model collapsing to one key.
  2. Shows two byte-different look-alike units becoming the same key.
  3. Shows where the library STOPS — and why refusing is the right answer.
  4. Shows the natural key a record would be stored under.

No arguments, no setup beyond `pip install -e .`.
"""

import sys

from anchorkey import describe, natural_key, needs_review, normalize, same_entity

# Windows consoles default to a legacy code page that cannot print µ/μ; force UTF-8 so
# the look-alike-unit demo prints cleanly on every platform.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def show(title: str) -> None:
    print("\n" + title)
    print("-" * len(title))


def main() -> None:
    show("1. One sensor model, several spellings -> one key")
    # These strings were all observed in the public openSenseMap data for the SAME
    # particulate sensor (the Nova Fitness SDS011).
    for raw in ["SDS 011", "SDS011", "sds011", "SDS1001"]:
        print(f"  {raw!r:12} -> normalize -> {normalize(raw)!r}")
    print("  (the typo 'SDS1001' correctly stays separate: see section 3)")

    show("2. Look-alike units (MICRO SIGN vs GREEK MU) -> one key")
    micro = "µg/m³"   # written with U+00B5 MICRO SIGN
    greek = "μg/m³"   # written with U+03BC GREEK SMALL LETTER MU
    print(f"  {micro!r} (U+00B5...) -> {normalize(micro)!r}")
    print(f"  {greek!r} (U+03BC...) -> {normalize(greek)!r}")
    print(f"  same key? {normalize(micro) == normalize(greek)}")

    show("3. Where this library stops, and why")
    print("  Proven identical -> merged:")
    print(f"    'SDS 011' vs 'sds011'   : same_entity = {same_entity('SDS 011', 'sds011')}")
    print()
    print("  A human would call this a typo. The library still refuses:")
    print(f"    'hdc1080' vs 'hhdc1080' : same_entity = {same_entity('hdc1080', 'hhdc1080')}"
          f"   needs_review = {needs_review('hdc1080', 'hhdc1080')}")
    print()
    print("  Because the same 'obvious' rule would also merge THESE — and they are")
    print("  two REAL Texas Instruments parts, not a typo:")
    print(f"    'hdc1008' vs 'hdc1080' : same_entity = {same_entity('hdc1008', 'hdc1080')}")
    print()
    print("  Every string-similarity metric measured scores the REAL pair as similar as,")
    print("  or more similar than, the typo. No threshold separates them, because the")
    print("  deciding fact — 'is this a shipping part?' — is a manufacturer's catalog,")
    print("  not a property of the characters. So the pair is deferred to a person and")
    print("  recorded as an effective-dated label, never guessed.")
    print("  Evidence: data/separability_sample.py + data/ground_truth_catalog.csv")

    show("4. The natural key a record would be stored under")
    for raw in ["SDS 011", "MPU-6050"]:
        info = describe(raw)
        print(f"  {raw!r}")
        print(f"      normalized  : {info['normalized']!r}")
        print(f"      natural key : {info['natural_key']!r}")
    print(f"\n  Pure function of content: natural_key('MPU-6050') == "
          f"{natural_key('MPU-6050')!r} on any machine, in any order.")


if __name__ == "__main__":
    main()
