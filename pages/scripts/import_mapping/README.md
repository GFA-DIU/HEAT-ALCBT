# Cambodia 250-building import — mapping & assumptions

Companion to `epd_alias.csv`. Records the decisions behind the imported figures so
results are auditable and easy to revise.

## Scope boundary (important when quoting the numbers)

**The embodied figures cover STRUCTURAL COMPONENTS ONLY.** They exclude MEP/services,
facade build-up, and fit-out. Embodied A1–A3 therefore lands near the low end
(~300 kgCO₂e/m²) of the 300–500 kgCO₂e/m² benchmark published for whole RC-frame
schools (RICS/LETI/CIBSE) — that is expected for a structure-only scope, and these
values must not be presented as whole-building embodied carbon.

## Data sources (two, and they are not interchangeable)

| Data | Source | Why |
|---|---|---|
| Structural components | the 250 per-building templates | real, building-specific |
| Operational energy | `Data of Cambodia Buildings - 250 list V2.xlsx`, sheet `operational energy demand` | the per-building templates' operational sheets are UNFILLED PLACEHOLDERS (identical in every file — e.g. lighting is literally "Hospital: Patient Room" in schools, hotels and offices alike) |

## Accepted source-data characteristics (not altered)

- **Rebar ratio ≈ 160 kg steel per m³ concrete** (typical 80–150). Consequently steel
  out-carbons concrete (≈155 vs ≈133 kgCO₂e/m²). BEAT's arithmetic reconciles exactly;
  the ratio comes from the source quantities and is accepted as given.
- `TMT Steel bars (Fe 550)` maps to the generic rebar EPD (2.6 kgCO₂e/kg), not the
  98%-recycled product (0.592), so the stock is represented conservatively.

## Assumptions applied during pre-processing

- One component per material; component quantity = that material's absolute quantity.
- Material share converted to BEAT's convention: Volume → 100 %; Area + m²-declared EPD
  → 1 layer; Area + kg-declared EPD → assumed layer thickness
  (brick 10 cm, aluminium 0.3 cm, single glazing 0.6 cm).
- Ready-mix concrete M30/M25 use the India EPD — no Cambodia equivalent exists.
- Ceramic tile mapped away from an outlier EPD (165 kgCO₂e/m², ~13× every other tile)
  to the regional product at 12.7.

## Verified reference result

ACE Tuol Tom Poung Campus (7,840 m², 50 yr, Cambodia):
embodied upfront A1–A5 **323.1**, operational B6 **2,154.5**, whole-life **2,477.6**
kgCO₂e/m²; EUI 73.2 kWh/m²/yr. Concrete 0.40 m³/m² and EUI both sit inside published
ranges.

## Post-import alignment against the source geometry tool (2026-09-23)

The templates were generated from `Final Embodied Carbon Easy Calculation tool for
embodied carbon - HEAT.xlsx` (`Datasheet` sheet, one row per building). Comparing the
loaded quantities against that sheet element by element — 3,142 rows — showed a median
ratio of **1.000** for foundation, columns, beams, floors, staircases and walls, so the
import itself is faithful. Five discrepancies were real and were corrected in the data:

| Issue | Scope | Resolution |
| --- | --- | --- |
| Floor Finish hard-coded to **240 m²** in every template | 100 buildings | recomputed as `W × L × (floors+1) × 0.8` |
| Template simply had no row for a core element | 7 lines / 5 buildings | added from the tool's formulas (Keystone was missing 1,098 m³ of foundation concrete) |
| Rebar pointed at `Steel reinforcement (steel rebar) ` — **India, trailing space**, 2.60 | 1,389 lines | repointed to the Cambodia record, 2.4247 |
| Aluminium pointed at `Aluminum ingot ` — **India, trailing space**, `conversions: []` | 56 lines | repointed to the Cambodia record (volume density 2700 kg/m³) |
| Only 28 of 250 templates carried any envelope | 1,086 components / 218 buildings | backfilled from the tool's geometry |

**Watch for the trailing-space EPD duplicates.** Several generic EPDs exist twice — an
India copy whose name ends in a space, and the country-localised copy without it. Name
matching silently prefers the India one. Worse, the India `Aluminum ingot ` carries no
conversion data at all, so an area assembly raises
`ImpactCalculationError: Cannot convert area assembly to kg`, which the statistics code
swallows in a bare `except`. The material then reports as **0 %** rather than as an
error. Check any group that shows exactly zero.

**Scope caveat — the envelope is modelled, not measured.** Only **28 of 246** buildings
have walls, windows and doors from their own template. For the other 218 those
components were derived parametrically (`perimeter × 3.2 m × floors`, windows at 60 %
of wall area split 30/70 frame/glass). Treat the envelope share of any benchmark drawn
from this dataset as an estimate. The structural frame is source data throughout.

**Left as-is by decision.** Beam and column volumes are kept at the templates' original
values: the tool's own sheet is half-edited, with a later `*50%` factor present in 127
of 250 beam rows and 22 of 250 column rows, so ~17 buildings hold twice the tool's
current figure. Concrete also stays on `Ready-mix concrete, M30` (India, 331 kgCO₂e/m³)
rather than the Cambodia C25/30 generic (304.4).

Two defects in the Excel tool itself, for anyone reconciling against it:
`Intermediate floor2` (column BU) duplicates `Intermediate floor` (BS) cell-for-cell in
all 250 rows and both sit inside the total; and rebar mass uses a density of
**1,000 kg/m³** instead of 7,850 (and drops the factor entirely for basement,
foundation and columns), understating reinforcement roughly eightfold.

## Reinforcement: why rebar is ~half the embodied carbon, and how far to trust it

BEAT's conversion is correct — steel is **7,850 kg/m³**, and the source geometry tool's
1,000 kg/m³ is a straightforward error. But the *quantity* that conversion is applied to
rests on an assumption that is at the top of, and in places above, the defensible band.
Three points to state whenever this dataset is quoted.

**1. A flat 2% by volume is a column ratio applied to everything.** The templates
reinforce every element at 2% of its gross volume → **157 kg rebar per m³ of concrete**.
Real ratios differ by roughly threefold between elements, and this dataset's concrete is
dominated by the lightly reinforced ones:

| Element | share of concrete volume | template | typical |
| --- | --- | --- | --- |
| Intermediate floors | 41.1 % | 2.00 % | 0.8–1.2 % |
| Foundation | 20.0 % | 2.00 % | 0.8–1.5 % |
| Roof | 8.8 % | 2.00 % | 0.8–1.2 % |
| Bottom floor | 8.8 % | 2.00 % | 0.8–1.2 % |
| Columns | 11.2 % | 2.00 % | 2.0–4.0 % ✓ |
| Beams | 10.1 % | 2.00 % | 1.5–2.0 % ✓ |

**61 % of the volume is slabs and foundations.** Volume-weighted, a realistic ratio is
**1.01–1.66 % = 79–130 kg/m³** against the 157 used. Rebar is therefore likely
**overstated by 30–50 %**. At ~105 kg/m³ the split would be about 48 % concrete / 38 %
rebar — the usual published pattern — and the median would fall from 377 to ≈320
kgCO₂e/m².

**2. Steel intensity is inverted against building height.** Real structures need more
steel per m² as they rise; this parametric geometry gives the opposite, and the
over-reinforced low-rise buildings are the majority of the sample:

| Storeys | n | dataset median | typical |
| --- | --- | --- | --- |
| 1–3 | 136 | **76.9 kg/m²** | 35–60 — well above |
| 4–8 | 67 | 66.7 kg/m² | 50–80 — ok |
| 9–15 | 17 | 60.6 kg/m² | 70–100 — below |
| 16+ | 25 | 60.9 kg/m² | 90–130 — well below |

The dataset-wide 63.5 kg/m² looks unremarkable only because these errors offset. Do not
read the aggregate as validation.

**3. The emission factor is a blast-furnace value.** `Steel reinforcement (steel rebar)`
Cambodia = **2.4247 kgCO₂e/kg**, derived by scaling the India generic by grid emission
factor. That localisation suits electricity-intensive materials; for BF-BOF steel, where
coke and process emissions dominate and grid power is a minor share, it is weak. Much
Vietnamese and Thai rebar — Cambodia's main supply — is EAF-from-scrap well under
1 kgCO₂e/kg (the database holds a Thai welded mesh at 0.763 and a 98 %-recycled Indian
TMT bar at 0.592). 2.4247 is a conservative worst case, not a regional average.

**Decision taken:** all three are left as they are. The 2 % ratio is GT's own assumption
and changing it would break traceability to the templates; the factor is kept consistent
with the India registry this dataset is benchmarked against; and a conservative error is
the safer direction for a policy tool. The rebar share of this dataset is therefore an
**assumption-driven upper bound, not a measured result**.

**Unrelated data defect, recorded but not fixed:** a family of rebar EPDs stores a
per-tonne figure against a `kg` declared unit — `TMT Bars - ARS 550D` 592,
`Steel Rebar from Tata Steel Limited` 2727.16, `TMT Bars` 3219.8,
`Average Reinforcement Steel Bars` 3454.4, and others. None are used by the 246 Cambodia
buildings, but any building that picks one gets a 1000× overstatement.

## Data-quality column in the registry export

`export_registry.py` screens every building and writes a `Data quality` column, so
defective records can be filtered out of a benchmark without deleting them. Thresholds
are the published plausibility bands for RC-frame buildings:

| Test | Flag |
| --- | --- |
| no concrete at all | `no structural data` |
| concrete outside 0.15–1.0 m³/m² | `concrete X m3/m2` |
| steel outside 20–150 kg/m² | `steel X kg/m2` |
| envelope area > 3× floor area | `envelope Xx floor area` |
| rebar volume > concrete volume | `rebar volume exceeds concrete` |

**236 of 246 read `ok`.** Filtering to those leaves the median essentially unchanged but
makes the spread usable — which matters because a registry is read for its distribution,
not only its midpoint:

| | all 246 | `ok` only (236) |
| --- | --- | --- |
| median | 375.7 | 372.3 |
| mean | 446.5 | **393.5** |
| std dev | 471.8 | **77.2** |

Always filter on this column before quoting a mean, a range or a distribution.

**Backfilled envelope is scaled to BEAT's floor area, not the tool's.** The first
backfill took wall/window/door areas straight from the tool, which put 1,423 m² of facade
on a 60 m² building wherever the tool's `W × L × floors` disagreed with the gross floor
area BEAT holds. Envelope area scales with perimeter, so the areas are multiplied by
`s = sqrt(GFA_beat / (W * L * floors))`. Only 13 of 218 buildings needed it — including
the nine ISPP campus buildings, which share one `buildingId` and were therefore all
inheriting the same geometry row.
