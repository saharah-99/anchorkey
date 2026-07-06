#!/usr/bin/env python3
# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
quickstart.py — see the idea in under a minute, on real public data.

Run:
    python examples/quickstart.py

It does two things:
  1. Shows the four real spellings of one sensor model collapsing to one key.
  2. Shows two byte-different look-alike units becoming the same key.

(Entity matching — linking typos, rejecting accessories — ships with the next paper in
the series.)

No arguments, no setup beyond `pip install -e .`.
"""

import sys

from anchorkey import normalize

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
    show("1. One sensor model, four spellings -> one key")
    # These four strings were all observed in the public openSenseMap data for the
    # SAME particulate sensor (the Nova Fitness SDS011).
    for raw in ["SDS 011", "SDS011", "sds011", "SDS1001"]:
        print(f"  {raw!r:12} -> normalize -> {normalize(raw)!r}")
    print("  (note: the typo 'SDS1001' correctly stays separate under normalization)")

    show("2. Look-alike units (MICRO SIGN vs GREEK MU) -> one key")
    micro = "µg/m³"   # written with U+00B5 MICRO SIGN
    greek = "μg/m³"   # written with U+03BC GREEK SMALL LETTER MU
    print(f"  {micro!r} (U+00B5...) -> {normalize(micro)!r}")
    print(f"  {greek!r} (U+03BC...) -> {normalize(greek)!r}")
    print(f"  same key? {normalize(micro) == normalize(greek)}")


if __name__ == "__main__":
    main()
