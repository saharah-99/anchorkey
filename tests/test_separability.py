# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
Tests for the REJECTED fuzzy-matching approach (data/separability_sample.py).

Why test code that does not ship?

Because the measurement is the paper's central evidence, and these tests are the receipt.
These tests are not protecting a feature — the feature was discarded. They show why the
CLAIM: that no tested string-similarity metric separates a typo from two genuinely
different parts, and that the failure is reproducible rather than a tuning accident.

That claim shapes the reasoning for Paper 2's architecture choice. If a future change to the
normalizer, the ground truth, or the metrics ever made a metric separable, the conclusion
would need revisiting, and this suite is what would say so, loudly, instead of the code
and the prose drifting apart in silence. Same guard as collapse_sample.py's cross-check,
applied to a negative result.

Three layers of assertion:
  1. the metrics compute what they claim to (unit tests on known values);
  2. the ground truth is internally coherent and matches its published audit trail;
  3. the finding itself still holds.
"""

import csv
import importlib.util
from pathlib import Path

import pytest

# data/ is not an importable package, so load the script by path.
_DATA = Path(__file__).resolve().parents[1] / "data"
_SPEC = importlib.util.spec_from_file_location("separability_sample",
                                               _DATA / "separability_sample.py")
sep = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sep)

CATALOG_CSV = _DATA / "ground_truth_catalog.csv"


# --------------------------------------------------------------------------- #
# 1. The metrics compute what they claim to.
# --------------------------------------------------------------------------- #
def test_levenshtein_known_values():
    assert sep.levenshtein("sds011", "sds011") == 0
    assert sep.levenshtein("", "abc") == 3
    assert sep.levenshtein("hdc1080", "hhdc1080") == 1     # one insertion
    assert sep.levenshtein("sds011", "sds1001") == 2


def test_damerau_treats_transposition_as_one_edit():
    """The defining difference from plain Levenshtein."""
    assert sep.levenshtein("ab", "ba") == 2
    assert sep.damerau_levenshtein("ab", "ba") == 1


def test_damerau_upgrade_makes_the_collision_worse():
    """The paper's counter-intuitive result, pinned as a test.

    Damerau-Levenshtein is the 'obvious upgrade' for this domain because SDS1001 is a
    digit transposition of SDS011. But hdc1008/hdc1080 — two REAL TI parts — are also a
    transposition apart, so the upgrade drags a genuine collision from distance 2 down to
    distance 1, into the same band as real typos. The sophisticated choice is the more
    dangerous one.
    """
    assert sep.levenshtein("hdc1008", "hdc1080") == 2
    assert sep.damerau_levenshtein("hdc1008", "hdc1080") == 1


def test_two_stage_refuses_when_digit_cores_differ():
    assert sep.two_stage("sds011", "sds1001") == sep.DISAGREE   # 011 vs 1001
    assert sep.two_stage("bme280", "bmp280") == 1               # cores match; e vs p


def test_similarity_metrics_are_bounded_and_reflexive():
    for fn in (sep.jaro_winkler, sep.qgram_jaccard):
        assert fn("bme280", "bme280") == pytest.approx(1.0)
        assert 0.0 <= fn("bme280", "sps30") <= 1.0


# --------------------------------------------------------------------------- #
# 2. The ground truth is coherent, and matches its published audit trail.
# --------------------------------------------------------------------------- #
def test_ground_truth_classes_are_disjoint():
    real, fake, unres = set(sep.REAL_PARTS), set(sep.NOT_REAL), set(sep.UNRESOLVED)
    assert not (real & fake), "a string cannot be both real and not real"
    assert not (real & unres) and not (fake & unres), "unresolved means unclassified"


def test_every_scored_string_is_classified():
    """No pair may rest on an unstated assumption."""
    classified = set(sep.REAL_PARTS) | set(sep.NOT_REAL)
    for a, b in sep.DISTINCT_PAIRS + sep.TYPO_PAIRS:
        assert a in classified and b in classified


def test_distinct_pairs_are_both_real_and_typo_pairs_are_mixed():
    for a, b in sep.DISTINCT_PAIRS:
        assert a in sep.REAL_PARTS and b in sep.REAL_PARTS, "collision needs two real parts"
    for a, b in sep.TYPO_PAIRS:
        assert (a in sep.REAL_PARTS) != (b in sep.REAL_PARTS), "typo needs exactly one real side"


def test_unresolved_strings_are_never_scored():
    """bmp200 could not be verified either way, so it must not influence the result."""
    scored = {s for pair in sep.DISTINCT_PAIRS + sep.TYPO_PAIRS for s in pair}
    assert not (scored & set(sep.UNRESOLVED))
    assert "bmp200" in sep.UNRESOLVED


def test_script_and_csv_audit_trail_agree():
    """The published audit trail must not drift from the code that uses it.

    ground_truth_catalog.csv is what a reader checks the claims against; the dicts above
    are what actually get scored. If they ever disagree, the paper is citing one thing and
    measuring another.
    """
    rows = list(csv.DictReader(CATALOG_CSV.open(encoding="utf-8")))
    csv_real = {r["normalized_key"] for r in rows
                if r["claimed_status"] == "REAL" and r["verdict"] == "CONFIRMED"}
    csv_not_real = {r["normalized_key"] for r in rows
                    if r["claimed_status"] == "NOT REAL" and r["verdict"] == "CONFIRMED"}
    csv_excluded = {r["normalized_key"] for r in rows if r["scoring_status"] == "EXCLUDED"}

    assert csv_real == set(sep.REAL_PARTS)
    assert csv_not_real == set(sep.NOT_REAL)
    assert csv_excluded == set(sep.UNRESOLVED)


def test_every_confirmed_real_part_cites_a_datasheet():
    """A ground-truth claim without a source is an assertion, not evidence."""
    rows = list(csv.DictReader(CATALOG_CSV.open(encoding="utf-8")))
    unsourced = [r["normalized_key"] for r in rows
                 if r["claimed_status"] == "REAL" and not r["datasheet_url"].strip()]
    assert not unsourced, f"REAL rows missing a datasheet URL: {unsourced}"


# --------------------------------------------------------------------------- #
# 3. The finding itself still holds.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name, fn, kind", sep.METRICS,
                         ids=[m[0] for m in sep.METRICS])
def test_no_metric_separates_typos_from_distinct_parts(name, fn, kind):
    """Paper 2's central claim, one test per metric.

    A metric separates if some threshold merges every TYPO pair and no DISTINCT pair.
    All five overlap. If this test ever fails, a metric became separable and the paper's
    conclusion needs re-examining. Which is exactly why this test exists.
    """
    ok, worst_typo, best_distinct = sep.separable(fn, kind)
    assert not ok, (
        f"{name} unexpectedly SEPARATES "
        f"(worst typo={worst_typo:.3g}, best distinct={best_distinct:.3g}) — "
        "re-check the ground truth and revisit Paper 2's conclusion"
    )


def test_star_witness_outscores_a_real_typo_on_every_metric():
    """The single pair that defeats the whole board.

    hdc1008/hdc1080 are two real TI parts. On every metric they look at least as similar
    as at least one genuine typo — so no tuning saves a fuzzy matcher here.
    """
    for name, fn, kind in sep.METRICS:
        score = fn("hdc1008", "hdc1080")
        typos = [fn(a, b) for a, b in sep.TYPO_PAIRS]
        closer = (sum(1 for t in typos if score <= t) if kind == "distance"
                  else sum(1 for t in typos if score >= t))
        assert closer >= 1, f"{name}: star witness no longer collides with any typo"


def test_all_scored_strings_occur_in_the_citable_snapshot():
    """Every string under test must be real observed data, not an invented example."""
    keys = sep.snapshot_keys()
    for a, b in sep.DISTINCT_PAIRS + sep.TYPO_PAIRS:
        assert keys[a] > 0, f"{a} absent from snapshot"
        assert keys[b] > 0, f"{b} absent from snapshot"


def test_dropping_bmp200_did_not_manufacture_the_result():
    """Honesty check: the excluded pair must not have been load-bearing.

    bmp200 was dropped because it could not be verified. Removing a TYPO pair SHRINKS the
    typo side, which makes overlap harder to obtain, not easier — so the conclusion cannot
    be an artifact of the exclusion. This asserts the typo side is still non-trivial.
    """
    assert len(sep.TYPO_PAIRS) >= 3
    assert len(sep.DISTINCT_PAIRS) >= 7


# --------------------------------------------------------------------------- #
# 4. The cost of deferring — data/review_queue_sample.py
#
# The architecture's practitioner-facing claim is that human review is affordable.
# That is a number, so it gets a test.
# --------------------------------------------------------------------------- #
_QSPEC = importlib.util.spec_from_file_location("review_queue_sample",
                                                _DATA / "review_queue_sample.py")
rq = importlib.util.module_from_spec(_QSPEC)
_QSPEC.loader.exec_module(rq)


def test_chosen_blocking_has_full_recall_on_verified_duplicates():
    """A cheap queue that misses real duplicates is worthless.

    The chosen strategy must surface every hand-verified typo pair. If it ever stops
    doing so, the queue is no longer trustworthy regardless of how small it is.
    """
    keys, _ = rq.load()
    cand = {tuple(sorted(p)) for p in rq.candidates(keys, rq.STRATEGIES[rq.CHOSEN])}
    missed = [p for p in rq.KNOWN_TYPO_PAIRS if p not in cand]
    assert not missed, f"chosen blocking misses verified duplicates: {missed}"


def test_cheaper_blocking_trades_away_recall():
    """The cost/recall trade-off is a finding, not an assumption — pin it.

    Three cheaper strategies each miss sds011/sds1001. Digit-signature blocking misses it
    structurally ('011' and '1001' differ), which is the same property that makes digit
    blocking safe elsewhere. If a cheaper strategy ever achieved full recall, the chosen
    strategy should be revisited — hence the assertion.
    """
    keys, _ = rq.load()
    for name in ("edit distance <= 1", "q-gram Jaccard >= 0.5", "same digit signature"):
        cand = {tuple(sorted(p)) for p in rq.candidates(keys, rq.STRATEGIES[name])}
        assert [p for p in rq.KNOWN_TYPO_PAIRS if p not in cand], (
            f"{name} now has full recall — cheaper blocking may be viable, revisit CHOSEN"
        )


def test_review_queue_stays_humanly_tractable():
    """The affordability claim, as an assertion."""
    keys, _ = rq.load()
    n = len(keys)
    queue = len(rq.candidates(keys, rq.STRATEGIES[rq.CHOSEN]))
    assert queue <= 50, f"queue grew to {queue} pairs — no longer a morning's work"
    assert queue / (n * (n - 1) // 2) < 0.01, "queue exceeded 1% of the all-pairs space"


def test_volume_triage_is_a_trap():
    """Filtering by volume on both sides deletes exactly the pairs review exists to find.

    Typos are rare by construction, so the minority side of a real typo pair is almost
    always below any sensible volume threshold. This documents the trap so nobody
    'optimizes' the queue by reintroducing it.
    """
    keys, _ = rq.load()
    for a, b in rq.KNOWN_TYPO_PAIRS:
        assert min(keys[a], keys[b]) < 5, (
            f"{a}/{b} minority side is no longer rare; the triage trap may not hold"
        )


def test_most_candidates_resolve_to_no_merge():
    """The queue is dominated by look-alike pairs that are genuinely different parts.

    This is why the review cannot be skipped by 'just merging the close ones': the
    upper-bound impact (everything merged) is an order of magnitude larger than the
    actual impact (only verified typos merged).
    """
    keys, _ = rq.load()
    cand = rq.candidates(keys, rq.STRATEGIES[rq.CHOSEN])
    upper = sum(min(keys[a], keys[b]) for a, b in cand)
    actual = sum(min(keys[a], keys[b]) for a, b in cand
                 if tuple(sorted((a, b))) in rq.KNOWN_TYPO_PAIRS)
    assert actual < upper / 10, "merging every candidate is no longer far worse than truth"


# --------------------------------------------------------------------------- #
# 5. The domain claim — data/keyshape_sample.py
#
# Paper 2 distinguishes itself from established record-linkage results by arguing these
# identifiers are short part-number codes, not personal names or postal addresses. That is
# a claim about the data, so it gets a test.
# --------------------------------------------------------------------------- #
_KSPEC = importlib.util.spec_from_file_location("keyshape_sample",
                                                _DATA / "keyshape_sample.py")
ks = importlib.util.module_from_spec(_KSPEC)
_KSPEC.loader.exec_module(ks)


def test_shape_classification_is_purely_syntactic():
    """The taxonomy must not need a parts catalog to sort its own rows.

    A classification requiring domain knowledge would concede Paper 2's conclusion in the
    setup and would not be reproducible by a reader. These cases pin the syntax-only rule.
    """
    assert ks.classify("bme280") == "part-number code"
    assert ks.classify("sds011") == "part-number code"
    assert ks.classify("microphone") == "alphabetic word"
    assert ks.classify("1") == "bare number"
    assert ks.classify("tsl45315&veml6070") == "other"
    # 'zahl' is German for 'number', i.e. a placeholder, but nothing in its SYNTAX says so.
    # It must land in the alphabetic group, not be special-cased by meaning.
    assert ks.classify("zahl") == "alphabetic word"


def test_part_number_codes_dominate_by_observation_volume():
    """The domain claim. Codes are a bare majority of keys but nearly all of the data."""
    keys = ks.load()
    codes = [k for k in keys if ks.classify(k) == "part-number code"]
    obs_share = sum(keys[k] for k in codes) / sum(keys.values())
    assert obs_share > 0.9, f"code share of observations fell to {obs_share:.0%}"
    assert len(codes) > len(keys) / 2, "codes are no longer a majority of keys"


def test_every_scored_string_is_a_part_number_code():
    """Scope integrity: the measured claim must not rest on placeholders or phrases.

    If a scored pair ever included an alphabetic word or a phrase, the paper would be
    generalizing from outside the population it claims to describe.
    """
    scored = {s for pair in sep.DISTINCT_PAIRS + sep.TYPO_PAIRS for s in pair}
    shapes = {s: ks.classify(s) for s in scored}
    offenders = {s: v for s, v in shapes.items() if v != "part-number code"}
    assert not offenders, f"scored strings outside the code population: {offenders}"


def test_residual_is_not_claimed_to_be_uniform():
    """Honesty guard: the paper must not be able to claim a clean population.

    If the non-code groups ever emptied, the prose warning against claiming uniformity
    would become false and should be revisited.
    """
    keys = ks.load()
    non_code = [k for k in keys if ks.classify(k) != "part-number code"]
    assert len(non_code) >= 10, (
        "the residual became nearly uniform; revisit the 'do not claim uniformity' warning"
    )


# --------------------------------------------------------------------------- #
# 6. The claim Figure 1 makes — data/make_figures.py
#
# The figure asserts a number the prose will quote: how many genuinely different parts get
# swept up by the loosest threshold that still catches every typo. That is a derived claim,
# so it is tested here rather than trusted to a rendering script.
# --------------------------------------------------------------------------- #
def _false_merges(fn, kind):
    """Real pairs merged by the loosest threshold that still catches every typo."""
    typo = [fn(a, b) for a, b in sep.TYPO_PAIRS]
    dist = [fn(a, b) for a, b in sep.DISTINCT_PAIRS]
    if kind == "distance":
        thresh = max(typo)
        return [v for v in dist if v <= thresh]
    thresh = min(typo)
    return [v for v in dist if v >= thresh]


@pytest.mark.parametrize("name, fn, kind", sep.METRICS, ids=[m[0] for m in sep.METRICS])
def test_full_recall_threshold_always_merges_real_parts(name, fn, kind):
    """Every metric, tuned to catch all typos, merges at least one genuinely different pair.

    This is the same finding as the separability test, stated the way a practitioner
    actually meets it: not "the bands overlap" but "tune it to work and it corrupts data."
    """
    caught = _false_merges(fn, kind)
    assert caught, (
        f"{name} now achieves full typo recall with zero false merges; "
        "Figure 1 and Paper 2's conclusion both need revisiting"
    )


def test_no_metric_is_close_to_clean():
    """Guards the strength of the claim, not just its direction.

    If some metric dropped to a single false merge out of seven while others stayed high,
    the prose would need to stop saying every metric fails badly and start reporting a
    spread. Jaro-Winkler is the best performer and still merges the star witness.
    """
    worst = {name: len(_false_merges(fn, kind)) for name, fn, kind in sep.METRICS}
    assert min(worst.values()) >= 1, worst
    assert worst["Levenshtein"] == len(sep.DISTINCT_PAIRS), (
        "plain Levenshtein no longer merges every real pair at full recall; "
        f"got {worst['Levenshtein']} of {len(sep.DISTINCT_PAIRS)}"
    )


# --------------------------------------------------------------------------- #
# 6. The alias blind spot — the paper's strongest ADMISSION, held to the same
#    standard as its strongest result.
#
# The honest-limits section claims that no blocking rule would ever propose
# `dht22`/`am2302`, so a human is never asked about a pair naming one sensor.
# That claim is falsifiable and therefore gets a test rather than only prose.
# --------------------------------------------------------------------------- #
_Q_SPEC = importlib.util.spec_from_file_location("review_queue_sample",
                                                 _DATA / "review_queue_sample.py")
rq = importlib.util.module_from_spec(_Q_SPEC)
_Q_SPEC.loader.exec_module(rq)


def test_no_blocking_strategy_proposes_the_alias_pair():
    """If any strategy ever proposes it, the honest-limits section is overstated."""
    a, b = rq.ALIAS_CASE
    proposed = [name for name, fn in rq.STRATEGIES.items() if fn(a, b)]
    assert not proposed, (
        f"a blocking rule now proposes {a}/{b}: {proposed}. The paper's alias "
        "limitation would need rewriting, and so would this test."
    )


def test_alias_pair_is_far_apart_on_every_string_measure():
    """Pins WHY it is never proposed: the two names share essentially nothing."""
    a, b = rq.ALIAS_CASE
    assert rq.levenshtein(a, b) >= 5
    overlap = rq._qgrams(a) & rq._qgrams(b)
    assert not overlap, f"expected zero shared bigrams, got {overlap}"
    assert rq._digits(a) != rq._digits(b)


def test_alias_case_is_grounded_in_the_verified_catalog():
    """The pair is not invented for the argument.

    `dht22` must be a scored, datasheet-verified row whose official part name is the
    other half of the alias. If the catalog ever stops recording that, the worked
    example loses its footing and the section must not keep claiming it.
    """
    a, b = rq.ALIAS_CASE
    rows = {r["normalized_key"]: r for r in csv.DictReader(CATALOG_CSV.open(encoding="utf-8"))}
    assert a in rows, f"{a} is no longer in the ground-truth catalog"
    row = rows[a]
    assert row["verdict"] == "CONFIRMED"
    assert row["official_part_name"].strip().lower() == b, (
        f"catalog says the official name for {a} is {row['official_part_name']!r}, "
        f"but the alias demonstration is built on {b!r}"
    )
