# anchorkey

**Auditable provenance for observed-entity telemetry: identity resolution under identifier
drift, with tamper-evident sealing.**

When a pipeline gives every *observed identifier string* its own primary key, one physical
thing fragments into many keys the moment that string drifts, and in the real world it always
drifts. Then every count and average computed across the fleet is silently wrong, and nothing
throws an error. `anchorkey` is a small, dependency-free library that *anchors* identity to a
**stable natural key** derived from messy observed names, so the same thing collapses to the
same key, and (planned) seals that identity into a tamper-evident ledger.

It is the reference implementation for a technical paper series on surrogate-key failure under
identifier drift (links below). Every number in the docs comes from real, public openSenseMap
sensor data.

> **A research and educational reference implementation.** This accompanies a technical paper
> series and is a personal learning project, provided as-is under Apache-2.0 with no warranty.
> It is not a commercial product or service.

```
SDS 011   ─┐
SDS011    ─┼─ normalize() ─▶  "sds011"
sds011    ─┘
SDS1001   ──── stays separate (a typo, not a spelling variant — that's a matching problem)
```

---

## The problem, in one real picture

Pull the public sensor stations in one city from [openSenseMap](https://opensensemap.org) and
look at how a single sensor model, the Nova Fitness SDS011, writes its own name:

![One sensor model recorded under four different strings; the stray-space spelling dwarfs the canonical one.](figures/fig1_fragmentation.png)

The most common spelling is not the canonical one. A fleet count keyed on this string is wrong
in the **majority** case, not at the margin. And it gets worse below the surface, where two
units can be byte-different while looking identical:

![Two unit strings that look identical but differ by one codepoint, MICRO SIGN versus GREEK MU, with the dominance reversed between two families.](figures/fig2_unicode_trap.png)

`µg/m³` written with MICRO SIGN (`U+00B5`) and with GREEK SMALL LETTER MU (`U+03BC`) are
indistinguishable to the eye and different to the database. A `GROUP BY unit` treats them as
two units forever.

---

## Quickstart (under a minute)

```bash
pip install -e .
python examples/quickstart.py
```

```python
from anchorkey import normalize

normalize("SDS 011") == normalize("sds011")        # True  — spacing/case drift gone
normalize("µg/m³")   == normalize("μg/m³")          # True  — look-alike Unicode collapsed
normalize("PM2.5")   != normalize("PM25")           # True  — meaningful "." preserved
normalize("MPU-6050") == normalize("MPU6050")       # True  — hyphen drift gone
```

---

## What it does today

| Concern | `anchorkey` | Note |
|---|---|---|
| Spacing / case drift | ✅ `normalize` | `SDS 011` → `sds011` |
| Look-alike Unicode | ✅ `normalize` | MICRO SIGN vs GREEK MU, sub/superscripts |
| Hyphen / separator drift | ✅ `normalize` | `MPU-6050` → `mpu6050` |
| Meaningful punctuation | ✅ preserved | `PM2.5` stays distinct from `PM25` |
| Idempotent keys | ✅ guaranteed | `f(f(x)) == f(x)`, pinned by a property test |

**Design stance:** the core library has **zero runtime dependencies** and is pure standard
library, on purpose. This identity logic should be readable, auditable, and easy
to vendor. The code is commented to be followed by readers who do not write Python.

### Roadmap

- **Entity resolution** (typos like `SDS1001` → `SDS011`, accessory-vs-device, cross-source
  duplicates): natural-key matching with a conservative fuzzy fallback. *Forthcoming with the
  next paper in the series.*
- **Tamper-evident ledger**: hash-chained, sealed snapshots, built *after* identity is correct
  so the seal protects a true grouping. *Planned.*

---

## Structure

The package is organised by pipeline stage, mirroring the paper series:

```
anchorkey/
  ingestion/           normalize observed strings into stable natural keys   (ships today)
  # entity_resolution/ match typos, derive the natural key                   (forthcoming)
  # ledger/            tamper-evident sealing of correct identities          (planned)
```

`ingestion` ships today. Each later stage is added when it has real code, not before, so
nothing here advertises a capability that does not exist. Identity is made correct *first*, by
design, so a later seal protects a true grouping.

---

## Why a separate layer, and where it sits

Device-identity frameworks like [Eclipse Ditto](https://eclipse.dev/ditto/) and
[Eclipse Hono](https://eclipse.dev/hono/) manage device twins and provisioning on the
assumption that a *stable device identity already exists*. `anchorkey` is the layer
underneath: it earns that identity when the world hands you 88 different ways to write a unit.

---

## The paper series

1. **Surrogate-key failure under identifier drift** — the diagnosis, on real openSenseMap data.
   *(this release backs it)*
2. **Entity resolution with natural keys** — the matching that handles typos and cross-source
   duplicates. *(forthcoming)*
3. Resource optimization — adaptive cadence and noise filtering. *(planned)*
4. Idempotency end-to-end in a data lake. *(planned)*
5. Cryptographic verification ledger — tamper-evident snapshots, built *after* identity is
   correct. *(planned)*

---

## Reproduce the data

```bash
python data/pull_drift_sample.py     # re-pull the live openSenseMap sample
```

A captured snapshot ships in `data/raw_snapshot.json` so the numbers above are stable even as
the live data drifts, which is, fittingly, the whole point.

## Develop

```bash
pip install -e ".[dev]"   # pytest + hypothesis
pytest                    # includes the idempotency property test
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under [Apache-2.0](LICENSE). If you use this
work, please cite it via [CITATION.cff](CITATION.cff).
