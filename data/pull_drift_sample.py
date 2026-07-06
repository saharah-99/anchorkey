#!/usr/bin/env python3
# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
pull_drift_sample.py — reproducible identifier-drift sample from openSenseMap.

Pulls public sensor stations ("boxes") for a bounding box from the openSenseMap
REST API and aggregates the *distinct* identifier strings observed across their
sensors: sensorType (the sensor model), title (the measured phenomenon), and
unit. The point is to show, on real public-domain data, how one physical sensor
model or one measured phenomenon appears under many drifted identifier strings
(fragmentation) — the motivating evidence for Paper 1.

Data source: https://api.opensensemap.org  (openSenseMap, data under
Public Domain Dedication and License 1.0). No API key required.

Usage:
    python pull_drift_sample.py

Outputs (next to this script):
    raw_snapshot.json   — the exact API response (the citable snapshot)
    drift_table.md      — derived distinct-string tables with counts
    capture_meta.json   — endpoint, bbox, UTC capture timestamp, box count

Re-running regenerates all three. Figures in the paper are built from the
snapshot, so they stay stable even as the live data drifts.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://api.opensensemap.org"
# Münster bounding box (minLon, minLat, maxLon, maxLat) — dense senseBox cluster
# (openSenseMap originated there). Swap freely; the drift pattern is global.
BBOX = "7.58,51.93,7.66,51.99"
ENDPOINT = f"{API_BASE}/boxes?bbox={BBOX}&format=json"

HERE = Path(__file__).resolve().parent


def fetch(url: str) -> object:
    req = urllib.request.Request(
        url, headers={"User-Agent": "paper1-drift-sample/1.0 (research)"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def codepoints(s: str) -> str:
    """Render a string with explicit codepoints — exposes µ (U+00B5) vs μ (U+03BC)."""
    return " ".join(f"U+{ord(c):04X}" for c in s)


def main() -> int:
    # Windows consoles default to cp1252 and choke on µ/μ; force UTF-8 stdout
    # so the summary prints (and re-runs) are clean. File writes are already UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    boxes = fetch(ENDPOINT)
    if not isinstance(boxes, list):
        print("Unexpected response shape (expected a JSON array).", file=sys.stderr)
        return 1

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

    # Save the raw snapshot (the citable artifact).
    (HERE / "raw_snapshot.json").write_text(
        json.dumps(boxes, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    meta = {
        "endpoint": ENDPOINT,
        "bbox": BBOX,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "box_count": len(boxes),
        "distinct_sensorType": len(sensor_types),
        "distinct_title": len(titles),
        "distinct_unit": len(units),
    }
    (HERE / "capture_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Highlight the two cleanest fragmentation cases for the paper.
    sds = {k: v for k, v in sensor_types.items() if re.search(r"sds", k, re.I)}
    micro_units = {
        k: v for k, v in units.items() if "g/m" in k.replace(" ", "")
    }

    def table(counter: Counter[str], header: str, show_cp: bool = False) -> str:
        lines = [f"### {header} ({len(counter)} distinct)", ""]
        lines.append("| count | value |" + (" codepoints |" if show_cp else ""))
        lines.append("|------:|-------|" + ("------------|" if show_cp else ""))
        for val, n in counter.most_common():
            row = f"| {n} | `{val}` |"
            if show_cp:
                row += f" {codepoints(val)} |"
            lines.append(row)
        return "\n".join(lines) + "\n"

    out = [
        f"# openSenseMap identifier-drift sample",
        "",
        f"- Endpoint: `{ENDPOINT}`",
        f"- Captured (UTC): {meta['captured_at_utc']}",
        f"- Boxes: {meta['box_count']} · distinct sensorType: {meta['distinct_sensorType']}"
        f" · title: {meta['distinct_title']} · unit: {meta['distinct_unit']}",
        "",
        "## Highlighted fragmentation cases",
        "",
        "### SDS011 PM-sensor model written multiple ways",
        "",
        "| count | sensorType |",
        "|------:|------------|",
        *[f"| {n} | `{k}` |" for k, n in sorted(sds.items())],
        "",
        "### Particulate-unit µg/m³ written multiple ways (note µ U+00B5 vs μ U+03BC)",
        "",
        "| count | unit | codepoints |",
        "|------:|------|------------|",
        *[f"| {n} | `{k}` | {codepoints(k)} |" for k, n in sorted(micro_units.items())],
        "",
        "## Full distinct-string tables",
        "",
        table(sensor_types, "sensorType (sensor model)"),
        table(titles, "title (measured phenomenon)"),
        table(units, "unit", show_cp=True),
    ]
    (HERE / "drift_table.md").write_text("\n".join(out), encoding="utf-8")

    print(f"OK — {meta['box_count']} boxes; "
          f"{meta['distinct_sensorType']} sensorType / "
          f"{meta['distinct_title']} title / {meta['distinct_unit']} unit distinct.")
    print(f"SDS variants: {sorted(sds)}")
    print(f"micro-unit variants: {sorted(micro_units)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
