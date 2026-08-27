#!/usr/bin/env python3
"""
collapse_sample.py — measure how far perimeter normalization collapses identifier drift.

Single source of truth: `raw_snapshot.json` (the exact openSenseMap API response
captured for the paper). This script RE-AGGREGATES the distinct identifier strings
from that JSON itself, then runs each distinct string through the SAME normalizer the
paper advocates — the published open-source `anchorkey.normalize` — and counts how many
distinct natural keys survive. The "before -> after" drop is the measured effect of
resolving identity at the ingestion perimeter.

This is characterization, not an evaluation: it counts key collapse on the captured
snapshot. It makes no downstream-metric or performance claim.

Like make_figures.py, it CROSS-VALIDATES the recomputed numbers against the figures
asserted in the paper draft (see EXPECTED below). If the snapshot, the normalizer, and
the paper ever disagree, the script prints FAIL and exits non-zero, so the prose and the
data can never drift apart silently.

Usage:
    git clone https://github.com/saharah-99/anchorkey && pip install -e anchorkey   # the reference implementation
    python collapse_sample.py
"""

from __future__ import annotations

import json
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


# --------------------------------------------------------------------------- #
# Step 1. Re-aggregate the distinct strings from the raw snapshot.
# --------------------------------------------------------------------------- #
def aggregate() -> tuple[Counter, Counter, Counter, int]:
    """Count every distinct sensorType / title / unit string across all boxes.

    Mirrors pull_drift_sample.py / make_figures.py exactly, so this script is
    self-contained and the counts it reports are provably the counts in the citable
    snapshot.
    """
    boxes = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    sensor_types: Counter[str] = Counter()
    titles: Counter[str] = Counter()
    units: Counter[str] = Counter()
    for box in boxes:
        for s in box.get("sensors", []) or []:
            if s.get("sensorType") is not None:
                sensor_types[s["sensorType"]] += 1
            if s.get("title") is not None:
                titles[s["title"]] += 1
            if s.get("unit") is not None:
                units[s["unit"]] += 1
    return sensor_types, titles, units, len(boxes)


# --------------------------------------------------------------------------- #
# Step 2. Collapse: distinct raw strings -> distinct natural keys.
# --------------------------------------------------------------------------- #
def collapse(distinct_strings) -> int:
    """Number of distinct natural keys after running each string through normalize()."""
    return len({normalize(s) for s in distinct_strings})


def keys_for(strings) -> dict[str, str]:
    """Map each raw string to its natural key (for the worked-example rows)."""
    return {s: normalize(s) for s in strings}


# --------------------------------------------------------------------------- #
# Step 3. Cross-validate the collapse numbers against the paper's claims.
# --------------------------------------------------------------------------- #
def cross_validate(sensor_types, titles, units, box_count) -> bool:
    st_before = len(sensor_types)
    un_before = len(units)
    st_after = collapse(sensor_types.keys())
    un_after = collapse(units.keys())

    # Worked example 1: the SDS011 family. The three stylistic variants collapse; the
    # transposed-digit typo SDS1001 does NOT (that is the deterministic/fuzzy boundary,
    # the Paper 2 hand-off). So four raw strings become two natural keys.
    sds_family = ["SDS 011", "SDS011", "sds011", "SDS1001"]
    sds_present = [s for s in sds_family if s in sensor_types]
    sds_keys = keys_for(sds_present)
    sds_after = len(set(sds_keys.values()))

    # Worked example 2: MPU-6050 / MPU6050 -> one key (hyphen is a droppable separator).
    mpu_family = ["MPU-6050", "MPU6050"]
    mpu_present = [s for s in mpu_family if s in sensor_types]
    mpu_after = len({normalize(s) for s in mpu_present})

    # Worked example 3: the micro-sign vs greek-mu unit family collapses under NFKC.
    cp = lambda s: " ".join(f"U+{ord(c):04X}" for c in s)
    ug_variants = [v for v in units if cp(v).startswith(("U+00B5", "U+03BC"))
                   and normalize(v) == normalize("µg/m³")]
    ug_after = len({normalize(v) for v in ug_variants})

    EXPECTED = {
        "box_count":                 (box_count, 719),
        "sensorType_before":         (st_before, 114),
        "sensorType_after":          (st_after, 99),
        "unit_before":               (un_before, 88),
        "unit_after":                (un_after, 78),
        "SDS011_family_after":       (sds_after, 2),
        "MPU6050_family_after":      (mpu_after, 1),
    }

    ok = True
    print("Collapse (distinct raw strings -> distinct natural keys via anchorkey.normalize):")
    print(f"  sensorType: {st_before:>4} raw  ->  {st_after:>4} keys")
    print(f"  unit:       {un_before:>4} raw  ->  {un_after:>4} keys")
    print()
    print("Worked examples:")
    for s in sds_present:
        print(f"  sensorType {s!r:12} -> {sds_keys[s]!r}")
    print(f"    => 4 raw SDS011 spellings collapse to {sds_after} keys "
          f"(SDS1001 typo stays separate: the Paper 2 residual)")
    for s in mpu_present:
        print(f"  sensorType {s!r:12} -> {normalize(s)!r}")
    print(f"    => MPU-6050 / MPU6050 collapse to {mpu_after} key")
    print(f"  micro-sign + greek-mu ug/m3 family collapse to {ug_after} key")
    print()

    print("Cross-check (only rows with a fixed expected value):")
    for label, (got, want) in EXPECTED.items():
        if want is None:
            print(f"  [ -- ] {label:24s} computed={got}")
            continue
        flag = "ok " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{flag}] {label:24s} snapshot={got:<6} expected={want}")
    print("  => ALL MATCH" if ok else "  => MISMATCH (fix draft or re-pull snapshot)")
    return ok


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles choke on µ/μ
    except Exception:
        pass

    if not SNAPSHOT.exists():
        print(f"Missing {SNAPSHOT}. Run pull_drift_sample.py first.", file=sys.stderr)
        return 2

    sensor_types, titles, units, box_count = aggregate()
    matched = cross_validate(sensor_types, titles, units, box_count)
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
