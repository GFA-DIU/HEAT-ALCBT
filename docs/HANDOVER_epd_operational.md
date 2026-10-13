# Handover — EPD catalogue and operational carbon work

Branch `rohit-qa`, in PR #593. Everything described here is pushed; the commit
messages and the three methodology docs carry the detail. This note is only for
what is **unfinished** and what has **already been decided**, so a later session
does not reopen settled questions.

Last updated 2026-10-12.

## Open

**`pages/management/commands/recategorise_epds.py` is written but uncommitted.**
Dry-run reviewed: 115 of 156 vague labels re-filed, 191 German Holcim ready-mix
moved off `1.1.01 Cement` to `1.4.01 Ready mixed concrete`, 41 refused as
unguessable (brass fittings, ball valves, TEXCA/CERA panels, mosaics). Changes
no carbon number — category drives the picker tree, search and the label only.
Deliberately left out of this batch to keep the diff reviewable.

**Lower-carbon alternatives feature — scoped, not built.** See
`docs/lower_carbon_alternatives_scope.md`. The naive version is unsafe:
grouping on `material_name` still mixes a 9 mm standard plasterboard with a
15 mm moisture-resistant wall board, and Portland cement with BF Slag. Agreed
direction is a **range benchmark** — "gypsum plasterboard in Thailand ranges
0.88–4.35 kgCO₂e/m² across 13 official EPDs; yours is 3.09, upper quartile" —
which is true without claiming substitutability. Awaiting GT on the framing
and on three questions listed at the end of that doc.

**12 environdec rows still unimported.** 10 are held back by decision (three
plywood declarations with negative A1-A3, Formosa billet/bloom/slab, DRI, an
acoustic control room, the bad CEM III/A). Two are genuinely unidentified:
**`SC 100` (0.264 kgCO₂e/kg) and `SC 300` (0.333)** from BUMATECH, Vietnam.
Values extracted fine; nobody has said what the products are. One line each in
`CATEGORY_RULES` when someone knows.

**Part-load factor on air conditioners.** `rated capacity × full hours ÷ COP`
bills every operating hour at 100% load. A 1.5 TR split at COP 2.8 on 8×7×52
gives 5,485 kWh/yr against a metered 1,500–2,500. Applying a 0.4–0.7 factor
would lower every cooled building's reported energy, so it is GT's call, not a
patch. Written up in `docs/operational_carbon_methodology.md`.

**A4 national rail share — needs GT.** The `national` sourcing scenario now
splits its 300 km land haul between rail and road. The shares are
**an assumption, not sourced**: India 60%, Thailand 30%, Vietnam 20%,
Indonesia 10%, Cambodia 0% (Cambodia has negligible rail freight, so that one
is safe). They are consequential — India's rail factor is 0.008 against road
at 0.070, so introducing the split moved India's national haul from **21.0 to
9.84 kgCO₂e/tonne**, lowering A4 for every nationally-sourced material in an
Indian building. Before any published figure relies on this, the shares need
real modal-split data. Flagged in `pages/scripts/a4a5/defaults.py`,
`docs/a4_a5_upfront_carbon_scope.md` and the `estimate_a4a5` output.

**A4 imported sea leg is a flat 3,000 km** regardless of origin. Chinese steel
into Vietnam and Brazilian steel into India get the same distance. Known
simplification, left deliberately: now that the sea leg is reported separately
rather than blended away, the assumption is at least visible to whoever reads
the figure. The per-material override fields (`a4_distance_km`, `a4_ef`) can
already be used to correct a specific material.

**F-gas emissions as a B1 line.** Refrigerant type, charge, leakage factor and
GWP are collected on every AC and chiller. They now feed the operational
baseline on the Savings tab, but there is no B1 scope line and the Systems tab
breakdown is unchanged. Under RICS, leakage is B1 rather than B6.

**Five pre-existing test failures**, untouched by this work and failing before
the branch: `test_operational_carbon_by_system` ×4 and
`test_operational_savings_measures` ×1. They assert label lists that no longer
match since plug load entered the breakdown.

**34 buildings hold stale `EnergySummary` values** from earlier fixes. A
`recalculate()` pass over all summaries would correct them. Unrelated to the
cassette re-attribution, which was verified to change no total.

## Decided — do not reopen

**A4 is modelled as legs, never a blended factor.** A journey is one leg per
transport mode, each carrying its own mode's emission factor. The earlier model
collapsed each scenario into a single distance and a single averaged factor,
which reported India's factor as 0.070 over 50 km and 0.01286 over 3,150 km —
reading as though the factor fell as distance rose. The arithmetic was correct
(an import is 95% sea, and sea is ~7× cleaner per tonne-km than road) but the
displayed number was a weighted mean of a ship and a truck and was not a
property of anything. `effective_ef()` survives only to fill the missing half of
a half-specified override; `test_a4_transport.py` fails if a blended factor is
reported again.


**Cement carries no GCCA rating.** GCCA publishes cement ratings, but each
country must first choose its own clinker/cement ratio to derive the
thresholds, and GCCA's own guidance says some countries will adopt concrete
ratings only. The near-zero line is reconstructable (`AA = 40 + 85 × ratio`,
giving exactly 100.0 at Germany's 0.706) but the A–F spacing is inside a figure
image. Reasoning and sources in `docs/carbon_rating_labels.md`.

**LESS is not implemented for steel.** It classifies on two axes — kgCO₂e per
tonne **and scrap share** — and `EPD` has no scrap field, nor do most source
declarations state one. BEAT's 92 ALCBT steel EPDs span 0.76–3.45 kgCO₂e/kg and
that spread is largely EAF against BF-BOF, i.e. largely the scrap share, so
inferring it back out and then rating on both would be circular.

**Generic EPDs are excluded from any product comparison.** This costs nothing:
of the 130 EPDs in the comparable families, 125 are already official.

**Cross-country material availability belongs on its own tab**, not in the
per-building savings panel.

**Concrete comparisons are matched on strength class**, and a concrete whose
strength cannot be parsed is excluded rather than compared against an unknown
mix. One such group showed a bogus −61%.

**Savings below 10% are noise** and should not be shown — that is prestressing
strand at 1% and ready-mix M50 at 5%.

**The GCCA concrete scale is AA–F, not A–G.** Seven bands; there is no G, and
AA is the near-zero band BEAT was missing. Re-rating left all 280 existing
labels unchanged and withdrew two Gs that were genuinely above the top of F.

## Things worth knowing before changing this code

- **Django `{# #}` comments only reach the end of their line.** A multi-line
  block renders onto the page as text. This shipped twice. `test_template_comments`
  now fails on it.
- **The material picker does not pass EPD instances to its template** — it
  builds a `FilteredEPD` dataclass. A template referencing a field that
  dataclass lacks renders an empty string rather than raising, which is how
  every product name silently vanished from the picker once already.
- **`data-icon` names are not validated.** Ten did not exist and rendered as
  empty boxes. The valid set is in `static/js/icons.js`, 87 names.
- **django-debug-toolbar is opt-in now** (`ENABLE_DEBUG_TOOLBAR=1`). It was 85%
  of each picker request — ~600 ms with it, ~75 ms without, against 30 ms of
  SQL. Production was never affected.

## Deployment

PR #593 carries two comments with the commands. The second supersedes the
first: migrations are **0056 through 0060**, not 0056 alone. No files need
sending to anyone — the 250 EPD values are committed at
`pages/data/environdec_epds.csv`.
