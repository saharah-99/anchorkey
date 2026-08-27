#!/usr/bin/env python3
"""
make_figures.py — build Paper 2's figures straight from the archived snapshot.

Single source of truth: `raw_snapshot.json`, plus the hand-verified ground truth in
`ground_truth_catalog.csv`. Every value drawn here is recomputed from the same functions
the measurement scripts use, so a figure cannot disagree with the text it illustrates.

Like Paper 1's figure script, this CROSS-VALIDATES what it draws (see EXPECTED at the
bottom) and exits non-zero on a mismatch.

Outputs (into ../figures/, raster and vector for each):
    fig4_separability.{png,svg}    five metrics, five panels, every one overlapping
    fig5_catalog_growth.{png,svg}  new keys appear in every year observed

Figure numbering note: filenames continue Paper 1's sequence (fig1..fig3 are Paper 1's).
Within Paper 2's text these are Figure 1 and Figure 2, numbered by order of appearance,
matching the convention Paper 1 already uses.

Usage:
    pip install matplotlib
    python make_figures.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

try:
    from anchorkey import normalize
except ImportError:
    sys.stderr.write("Needs the reference implementation:\n"
                     "  git clone https://github.com/saharah-99/anchorkey\n"
                     "  pip install -e anchorkey\n")
    raise SystemExit(2)

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "raw_snapshot.json"
FIG_DIR = HERE.parent / "figures"

# Paper 1's palette, so the series reads as one set.
INK = "#1a1a1a"      # near-black text/axes
CANON = "#2a7de1"    # blue: the correct / must-not-merge population
DRIFT = "#e07a1f"    # amber: the drifted / should-merge population
MUTE = "#9aa0a6"     # grey: de-emphasis
OVERLAP = "#d93636"  # red: the region where the two populations interleave

_spec = importlib.util.spec_from_file_location("sep", HERE / "separability_sample.py")
sep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sep)

_rspec = importlib.util.spec_from_file_location("rq", HERE / "review_queue_sample.py")
rq = importlib.util.module_from_spec(_rspec)
_rspec.loader.exec_module(rq)


def save(fig, stem: str) -> None:
    FIG_DIR.mkdir(exist_ok=True)
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Figure 1 (fig4): small multiples, one panel per metric.
#
# A single shared axis was rejected deliberately. The five metrics are on incompatible
# scales: two are distances, two are similarities, and the two-stage matcher emits a
# sentinel when it refuses to compare. Any transform placing them on one axis would be a
# rhetorical choice presented as a measurement. Five native-scale panels let the reader
# compare WITHIN a panel, which is the only honest comparison, and the repeated shape
# across panels carries the argument.
# --------------------------------------------------------------------------- #
def _stack(values):
    """Vertical offsets so pairs sharing a score stay individually visible.

    Several pairs land on identical scores (three typos score 1, 1, 2 under Levenshtein).
    Drawn flat they would collapse into fewer marks than there are pairs, understating the
    evidence. Duplicates are stacked instead.
    """
    seen, out = Counter(), []
    for v in values:
        out.append(seen[v] * 0.17)
        seen[v] += 1
    return out


def fig_separability() -> dict:
    fig, axes = plt.subplots(1, len(sep.METRICS), figsize=(16.5, 3.9))
    fig.subplots_adjust(wspace=0.42)
    facts = {}

    for i, (ax, (name, fn, kind)) in enumerate(zip(axes, sep.METRICS)):
        typo = [fn(a, b) for a, b in sep.TYPO_PAIRS]
        dist = [fn(a, b) for a, b in sep.DISTINCT_PAIRS]

        # The two-stage matcher returns a sentinel (99) meaning "cores differ, refused".
        # Plotting 99 beside values of 1 and 2 on a linear axis would erase the detail that
        # matters, so the sentinel gets its own labelled tick rather than being hidden.
        if name == "two-stage core":
            real = sorted({v for v in typo + dist if v != sep.DISAGREE})
            slot = {v: j for j, v in enumerate(real)}
            refused = len(real) + 0.7
            tx = lambda v: refused if v == sep.DISAGREE else slot[v]
            ticks = list(range(len(real))) + [refused]
            labels = [str(v) for v in real] + ["refused"]
        else:
            tx = lambda v: v
            ticks = labels = None

        ty, dy = [tx(v) for v in typo], [tx(v) for v in dist]

        # The threshold a practitioner is forced to adopt: the loosest setting that still
        # catches every typo. Everything on the merge side of it gets merged, whether or
        # not it should be. That is the argument, so it is what the figure draws.
        if kind == "distance":
            thresh = max(ty)
            caught = [v for v in dy if v <= thresh]
            span = (min(min(ty), min(dy)) - 0.35, thresh)
        else:
            thresh = min(ty)
            caught = [v for v in dy if v >= thresh]
            span = (thresh, max(max(ty), max(dy)) + 0.02)

        ax.axvspan(*span, color=OVERLAP, alpha=0.11, zorder=1)
        ax.axvline(thresh, color=OVERLAP, linewidth=1.4, linestyle="--", zorder=2)

        # Typo row stacks up, distinct row stacks DOWN, so a tall stack in one row can
        # never drift into the other and be misread.
        toff, doff = _stack(ty), [-o for o in _stack(dy)]
        ax.scatter(ty, [1.0 + o for o in toff], s=95, color=DRIFT, zorder=4)
        ax.scatter(dy, [0.0 + o for o in doff], s=95, color=CANON, marker="s", zorder=4)
        # Ring the real parts that the forced threshold sweeps up.
        ax.scatter([v for v in dy if v in caught],
                   [0.0 + o for v, o in zip(dy, doff) if v in caught],
                   s=230, facecolors="none", edgecolors=OVERLAP, linewidths=1.8, zorder=5)

        ax.set_title(name, fontsize=10.5, color=INK, pad=10)
        ax.annotate(f"{len(caught)} real pair{'s' if len(caught) != 1 else ''} "
                    f"wrongly merged",
                    xy=(0.5, 0.965), xycoords="axes fraction", ha="center", va="top",
                    fontsize=8.5, color=OVERLAP, fontweight="bold")
        if i == 0:
            ax.set_yticks([0, 1])
            ax.set_yticklabels(["distinct", "typo"], fontsize=9, color=INK)
        else:
            ax.set_yticks([])
        ax.set_ylim(-0.85, 1.75)
        if ticks is not None:
            ax.set_xticks(ticks)
            ax.set_xticklabels(labels, fontsize=8.5)
        ax.tick_params(axis="x", labelsize=8.5, colors=INK)
        ax.set_xlabel("lower = more similar" if kind == "distance"
                      else "higher = more similar", fontsize=7.5, color=MUTE)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(MUTE)
        ax.grid(axis="x", color=MUTE, alpha=0.16, linewidth=0.6)

        facts[name] = len(caught) > 0

    handles = [
        plt.Line2D([], [], marker="o", linestyle="", color=DRIFT, markersize=8,
                   label="typo pair (should merge)"),
        plt.Line2D([], [], marker="s", linestyle="", color=CANON, markersize=8,
                   label="two real parts (must not merge)"),
        plt.Line2D([], [], color=OVERLAP, linestyle="--", linewidth=1.5,
                   label="loosest threshold catching every typo"),
        plt.Line2D([], [], marker="o", linestyle="", markerfacecolor="none",
                   markeredgecolor=OVERLAP, markersize=11,
                   label="real parts merged by that threshold"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, -0.09))
    fig.suptitle("Any threshold that catches every typo also merges genuinely different parts",
                 fontsize=12.5, color=INK, y=1.03)
    save(fig, "fig4_separability")
    return facts


# --------------------------------------------------------------------------- #
# Figure 2 (fig5): the catalog never saturates.
#
# This converts "catalogs change" from an assertion into a measurement, which is what
# makes effective-dated labels forced rather than ceremonial.
# --------------------------------------------------------------------------- #
def fig_catalog_growth() -> dict:
    keys, first_seen = rq.load()
    years = sorted(set(first_seen.values()))
    new = [sum(1 for v in first_seen.values() if v == y) for y in years]
    cum, run = [], 0
    for n in new:
        run += n
        cum.append(run)

    # Both endpoints are PARTIAL years and must be marked, or the shape misleads.
    # Registrations run 2020-12-03 to 2026-06-24: the first year is one month (which
    # inflates it, since every key is new at the start) and the last is six months (which
    # deflates it). Reading a trend across unmarked partial endpoints would overstate any
    # flattening.
    partial = {years[0], years[-1]}

    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.bar(years, new, width=0.62, zorder=2,
                  color=[MUTE if y not in partial else "#cdd1d5" for y in years],
                  hatch=["" if y not in partial else "///" for y in years],
                  edgecolor=MUTE)
    ax2 = ax.twinx()
    ax2.plot(years, cum, color=CANON, marker="o", linewidth=2.2, zorder=3)
    for x, y in zip(years, cum):
        ax2.annotate(str(y), (x, y), textcoords="offset points", xytext=(0, 9),
                     ha="center", fontsize=8.5, color=CANON)

    # The 2022 bar is inflated by bulk registration, not by a surge in sensor variety.
    spike = years.index("2022")
    ax.annotate("bulk registration:\n127 of 719 boxes\non a single day",
                xy=(years[spike], new[spike]), xytext=(2, 20),
                textcoords="offset points", ha="center", fontsize=7.5, color=INK,
                arrowprops=dict(arrowstyle="->", color=MUTE, linewidth=0.9))
    for y in partial:
        j = years.index(y)
        span = "Dec only" if j == 0 else "Jan-Jun"
        ax.annotate(f"partial year\n({span})", xy=(y, new[j]), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=7, color=MUTE)

    ax.set_ylabel("new keys first seen that year", fontsize=9, color=INK)
    ax2.set_ylabel("cumulative distinct keys", fontsize=9, color=CANON)
    ax.set_ylim(0, max(new) * 1.5)
    ax2.set_ylim(0, max(cum) * 1.22)
    ax.tick_params(labelsize=9, colors=INK)
    ax2.tick_params(labelsize=9, colors=CANON)
    ax.spines["top"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    # The claim is time-variance, not unbounded growth. Seven years cannot establish that
    # a catalog never saturates, and the cumulative curve visibly decelerates. What the
    # data does support is that new keys appear in every year observed, including both
    # truncated ones, which is all that effective-dated labels require.
    ax.set_title("New identifier keys appear in every year observed,\n"
                 "including both partial years",
                 fontsize=11, color=INK, pad=12)
    ax.grid(axis="y", color=MUTE, alpha=0.18, linewidth=0.6)
    ax.set_axisbelow(True)
    save(fig, "fig5_catalog_growth")

    return {
        "years": years, "new": new, "cumulative": cum,
        "every_year_grew": all(n > 0 for n in new),
        "partial_years_marked": len(partial) == 2,
        "final": cum[-1],
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not SNAPSHOT.exists():
        print(f"Missing {SNAPSHOT}. Run pull_drift_sample.py first.", file=sys.stderr)
        return 2

    overlaps = fig_separability()
    growth = fig_catalog_growth()

    print("Figure 1 (fig4_separability): overlap per metric")
    for name, ok in overlaps.items():
        print(f"    {name:16} {'OVERLAP' if ok else 'separable'}")
    print(f"\nFigure 2 (fig5_catalog_growth): {growth['years'][0]}..{growth['years'][-1]}")
    print(f"    new per year : {growth['new']}")
    print(f"    cumulative   : {growth['cumulative']}")

    EXPECTED = {
        "every metric overlaps":      (all(overlaps.values()), True),
        "five panels drawn":          (len(overlaps), 5),
        "catalog grew every year":    (growth["every_year_grew"], True),
        "catalog ends at 99 keys":    (growth["final"], 99),
        "partial years are marked":   (growth["partial_years_marked"], True),
    }
    print("\nCross-check:")
    ok = True
    for label, (got, want) in EXPECTED.items():
        flag = "ok " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{flag}] {label:26s} got={got} expected={want}")
    print("  => ALL MATCH" if ok else "  => MISMATCH (figure would contradict the text)")
    print(f"\nWrote 2 figures (png+svg) to {FIG_DIR}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
