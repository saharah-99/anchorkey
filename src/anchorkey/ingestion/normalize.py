"""
normalize.py — turn a messy observed identifier string into a stable natural key.

THE PROBLEM (in one sentence): the same physical thing gets written down many
slightly-different ways ("SDS 011", "SDS011", "sds011"), and if a database treats
each spelling as a different thing, every count and average computed across them is
silently wrong.

THE FIX (what this file does): run every observed string through ONE deterministic
cleanup pipeline before it is ever used as a key. After the pipeline, the harmless
differences (a stray space, a capital letter, a look-alike Unicode character) are
gone, so the three spellings above all collapse to the single key "sds011".

Design rules this file obeys (both essential):
  1. IDEMPOTENT. Running the pipeline twice gives the same answer as running it once:
     normalize(normalize(x)) == normalize(x). This is what lets us safely re-clean
     keys that are already stored, and it is pinned by a property test (see tests/).
  2. CONSERVATIVE. It only removes differences that carry NO identity (case, spacing,
     look-alike characters). It deliberately KEEPS meaningful punctuation such as the
     dot in "PM2.5", because deleting it would merge "PM2.5" into "PM25" — two
     genuinely different things. Over-cleaning is how you trade one bug for a worse one.
"""

from __future__ import annotations

import unicodedata


# Characters we treat as "no identity here" and remove:
#   * all whitespace (spaces, tabs, newlines), so "SDS 011" == "SDS011";
#   * separator punctuation that joins parts of a model string, so "MPU-6050" == "MPU6050".
# The separator set is deliberately TINY: hyphens (several Unicode dash variants) and the
# underscore. Crucially it does NOT include the decimal point ".", because the dot
# distinguishes real things ("PM2.5" must stay different from "PM25"). Deleting every
# punctuation mark is the classic over-cleaning mistake that turns a spelling fix into a
# collision; we avoid it by naming exactly which separators are meaningless here.
_SEPARATORS = {
    "-",        # HYPHEN-MINUS
    "‐",   # HYPHEN
    "‑",   # NON-BREAKING HYPHEN
    "‒",   # FIGURE DASH
    "–",   # EN DASH
    "—",   # EM DASH
    "−",   # MINUS SIGN
    "_",        # LOW LINE (underscore)
}


def _is_droppable_separator(ch: str) -> bool:
    return ch.isspace() or ch in _SEPARATORS


# Unicode assigns every character a two-letter "category". Two of those categories are
# invisible plumbing we never want inside a key:
#   "Cc" = control characters (e.g. a stray NULL or tab-like control byte)
#   "Cf" = format characters (e.g. zero-width joiners, left-to-right marks) — these are
#          invisible but change the bytes, so two "identical-looking" strings can differ.
def _is_control_or_format(ch: str) -> bool:
    return unicodedata.category(ch) in ("Cc", "Cf")


def normalize(value: str) -> str:
    """Return the stable natural key for one observed identifier string.

    The pipeline, step by step:

        NFKC  ->  strip control/format  ->  casefold  ->  NFKC again  ->  strip separators

    Why each step exists:

    * NFKC (Unicode Normalization Form KC). Unicode has many characters that look the
      same but have different code numbers. The classic trap in real sensor data:
      "µg/m³" can be written with MICRO SIGN (U+00B5) or with GREEK SMALL LETTER MU
      (U+03BC); the two are visually identical but byte-different. NFKC rewrites such
      "compatibility" characters to one canonical form, so the look-alikes converge.
      It also folds the superscript "³" (U+00B3) down to a plain "3".

    * strip control/format. Remove the invisible plumbing characters described above,
      so an unseen zero-width character can never fork one identity into two.

    * casefold. A more aggressive, Unicode-aware lower-casing. Makes "SDS011", "sds011",
      and "SOUNDLEVELMETER" / "soundlevelmeter" agree on case.

    * NFKC again. Casefolding can itself introduce characters that want re-normalizing,
      so we normalize a second time to reach a guaranteed fixed point. This second pass
      is also what makes the whole function idempotent.

    * strip separators. Remove every space and meaningless joining mark (hyphen,
      underscore), so "SDS 011" == "SDS011" and "MPU-6050" == "MPU6050". The decimal
      point is preserved, so "PM2.5" stays distinct from "PM25".

    What it intentionally does NOT do: it does not strip "." or digits, because those
    distinguish real things ("PM2.5" vs "PM25"). Catching genuine typos like "SDS1001"
    is a SEPARATE, fuzzy problem handled in matching.py; normalization is exact by design.
    """
    if value is None:
        raise ValueError("normalize() expects a string, got None")

    # We apply the five-step cleanup repeatedly until the output stops changing (a fixed
    # point). One pass is almost always enough, but a few rare combining characters (for
    # example a base letter plus a combining macron) interact with casefolding so that a
    # single pass leaves a not-quite-stable string; a second pass settles it. Looping to a
    # fixed point is what GUARANTEES idempotency, f(f(x)) == f(x), for every possible input
    # (this is pinned by a Hypothesis property test in tests/). The cap is a safety bound;
    # convergence happens in one or two iterations in practice.
    s = value
    for _ in range(8):
        previous = s
        # Step 1: canonicalise look-alike Unicode (MICRO SIGN -> GREEK MU, "³" -> "3", ...).
        s = unicodedata.normalize("NFKC", s)
        # Step 2: drop invisible control/format characters.
        s = "".join(ch for ch in s if not _is_control_or_format(ch))
        # Step 3: case-insensitive fold.
        s = s.casefold()
        # Step 4: re-normalise (casefolding can re-introduce non-canonical sequences).
        s = unicodedata.normalize("NFKC", s)
        # Step 5: remove whitespace and meaningless joining marks (keep the decimal point).
        s = "".join(ch for ch in s if not _is_droppable_separator(ch))
        if s == previous:
            break
    return s
