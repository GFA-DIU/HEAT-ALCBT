# Operational Carbon (B6) — Methodology & Improvement Plan

Status: **for review.** Focused artifact on BEAT's operational carbon — how it works
today, whether it's defensible, and the agreed improvements. Companion to
`docs/carbon_calculation_methodology.md` (embodied + operational overview) and
`docs/bim_beat_integration_methodology.md`.

---

## 1. What BEAT does today

**Formula** (`pages/views/building/building_dashboard/utility.py` → `prep_operational_df`):

```
operational_GWP = annual_energy × emission_factor × reference_period
```

with the annual value held **constant** across the whole period.

- `reference_period` = `building.reference_period` (default **50 years**, user-editable).
- **Annual energy** is modelled from the building's equipment inputs — cooling (AC/chiller/
  VRF), ventilation, lighting, hot water, etc. — producing a single representative annual
  figure. It is **not** year-by-year metered data.
- Impacts are stored at life-cycle stage **B6** (`gwp_b6`, per kWh).

**Verdict:** annual × Reference Study Period (RSP) is the **standard EN 15978 module B6
method**, and is what One Click LCA and comparable tools do by default. **The baseline is
valid and acceptable** — it is simply conservative (see §4).

---

## 2. Emission factors

Energy carriers are generic EPDs (`source = GFA-HEAT`, `declared_unit = kwh`, stage B6),
loaded from `pages/data/generic_operational_EPDs_v2.csv`.

- **Electricity is country-specific** (grid mix differs by country).
- **Fuels use one shared factor** across the ALCBT countries — combustion emissions are
  ≈ physics, not country-dependent.

**Current electricity factors (kgCO₂e/kWh):**

| Country | Factor | Source |
|---|---|---|
| Thailand | 0.475 | TGO 2022–24 |
| Vietnam | **0.659** | MONRE 2023 (corrected from an understated 0.410) |
| Cambodia | **0.588** | Electricity Authority of Cambodia 2023 (corrected from 0.418) |
| Indonesia | 0.78 | national published (Ember 2023 ~0.76 / prior 0.778) |
| India | 0.705 | CEA / IEA ~0.71 |

Fuels (Thailand set, from the TGO Operational_EF sheet) and carrier names were also
cleaned — see `docs/thailand_operational_ef.md`.

---

## 3. Building age — how it's handled (a common question)

**You enter only the current / representative annual energy — never historical
year-by-year consumption**, even for an old building. BEAT applies one representative
annual figure across the RSP.

BEAT uses a **timeless design assessment**: the RSP is assessed from the assessment year
forward; the building's **actual age / construction year is not an input** and does not
change the result. This keeps whole-life figures comparable between buildings and matches
standard design-stage LCA practice. (The alternative — calendar-anchoring to the
construction year and integrating historical grid factors — was considered and **not
adopted**, to keep the model simple and comparable.)

---

## 4. Known weakness: the constant factor

Holding the emission factor constant for 50 years ignores **grid decarbonisation** — grids
will get much cleaner as renewables grow. Using *today's* electricity factor for 50 years
**systematically overestimates** operational carbon, often by roughly half for
electricity-heavy buildings. This is the single biggest realism gap, addressed in §5.

(Fuel factors staying constant is fine — combustion intensity doesn't decline.)

---

## 5. Agreed improvement — optional grid decarbonisation

**Design (locked):**
- **Optional per-building toggle:** *constant* (today's factor × RSP — conservative baseline)
  ↔ *declining* (realistic). User chooses; both can be reported side by side.
- **Electricity only** — fuels stay constant.
- **Timeless:** the decline starts at the assessment year (consistent with §3).
- **Shape:** linear from an anchor (today's factor) to a near-zero **target** at the
  country's net-zero year; flat at the residual thereafter.
- **Data-driven:** values live in a per-country table (anchor, target year, residual, shape)
  so they can be swapped for IEA WEO/APS year-by-year trajectories later.

**Locked per-country dataset:**

| Country | Anchor kgCO₂/kWh | Source | Net-zero target yr | Residual | Eff. 50-yr factor | vs constant |
|---|---|---|---|---|---|---|
| Thailand | 0.475 | TGO 2022–24 | 2050 (carbon-neutral) | 0.05 | ~0.152 | −68% |
| Vietnam | 0.659 | MONRE 2023 | 2050 | 0.05 | ~0.196 | −70% |
| Cambodia | 0.588 | EAC 2023 | 2050 | 0.05 | ~0.179 | −70% |
| Indonesia | 0.78 | national published (Ember/prior) | 2060 | 0.05 | ~0.298 | −62% |
| India | 0.705 | CEA/IEA ~0.71 | 2070 | 0.05 | ~0.338 | −52% |

Reference trajectory: ASEAN grid intensity ~0.54 → 0.18 kgCO₂/kWh by 2050 under a net-zero
view (S&P Global; ScienceDirect). Net-zero years from national NDC/carbon-neutrality pledges.

**Impact:** applying the decline roughly **halves** electricity operational carbon vs the
constant assumption — material, and honest to report both.

**Build plan (when approved):**
1. Add a per-country grid-trajectory table (anchor EF, target year, residual, shape).
2. Add a per-building toggle (`constant` | `declining`) + optional custom RSP.
3. In `prep_operational_df`, apply the year-integrated factor **to the electricity carrier
   only**; leave fuels constant.
4. Report constant vs declining side by side; cite the anchor + target sources in the report.
5. (Later) accept an explicit year→EF table so licensed IEA APS values can replace the
   linear model.

---

## 6. Deferred / out of scope (documented limitations)

- **Embodied ↔ operational thermal trade-off.** A low-embodied material can insulate poorly
  → more operational energy. BEAT **cannot flag this today** because thermal conductivity λ
  is not in the EPD data (verified: 0 of 1,279 envelope EPDs). Proper handling needs an
  envelope U-value → energy link (an energy model), with λ from an **ISO 10456** reference
  table by material type — belongs with the future gbXML / energy-simulation work.
- **Mass/volume fuels** (diesel/LPG/…) are stored per-kWh; converting the TGO per-litre/kg
  factors needs calorific values (deferred, Thailand-scoped).
- **Beyond B6:** operational water (B7) and any operational scope other than energy are not
  modelled.

---

## 7. Open items before building §5

- **Cambodia anchor (0.588)** is from the Electricity Authority of Cambodia (2023),
  consultant-provided; attach the EAC source document for citation (not independently
  verifiable via a public URL).
- Confirm target-year basis per country (carbon-neutrality vs net-zero-GHG dates) and the
  residual (0.05 vs 0) — these are the levers that most change the result.
- Decide default toggle state (recommend **constant** as the conservative default, with
  declining as an explicit opt-in).

## 8. References
EN 15978 (module B6), EN 15804 / ISO 21930 (EPDs). Grid EFs: TGO, MONRE 2023 (Vietnam),
Electricity Authority of Cambodia 2023, IEA Emissions Factors, CEA (India). National NDC /
net-zero pledges. IEA World Energy Outlook / Southeast Asia Energy Outlook 2024 (scenario
trajectories, licensed).

---

## System classification: cassette air conditioners

A cassette AC is cooling equipment. The ventilation form nevertheless offered
"Ceiling/Wall Mounted Cassette AC", and it became the most used ventilation
type in the database: **106 records across 67 buildings**, against **zero**
records on the cooling form's own `packaged → cassette` path.

No building had both, so nothing was ever double counted. The fault was
attribution: both forms compute annual energy the same way —

```
energy = power_input × hours/day × days/week × weeks/year
```

— so the figures were right, but 106 air conditioners reported on the
*ventilation* line of every report and benchmark.

`EnergySummary.recalculate` now counts cassette records as cooling. Verified
across all 267 energy summaries: the cooling/ventilation split changes for 66
buildings and the cooling + ventilation **sum is identical for every one**.
No building total moves.

The records are re-attributed rather than physically moved to
`CoolingSystemAirConditioner`, because that model requires
`year_of_installation`, `refrigerant_type` and `refrigerant_quantity_kg` as
NOT NULL and the ventilation form collects none of them. Moving the rows would
mean inventing three values per record.

The option is withheld from new ventilation entries while the value stays valid
on the model, so the 106 existing records keep rendering and editing normally.

## Known gap: refrigerant (F-gas) emissions are collected but not counted

Every air conditioner and chiller records:

- `refrigerant_type`
- `refrigerant_quantity_kg`
- `baseline_leakage_factor_percent` (default 2%)
- `baseline_refrigerant_emission_factor` (the refrigerant's GWP, auto-filled
  from `RefrigerantGWP`)

**None of it enters any carbon figure.** The values are stored and exposed
through the API, and nothing computes leakage emissions from them. The leakage
tooltip previously claimed the field "drives the refrigerant (F-gas)
emissions", which was untrue; it now says the value is recorded for reporting
only.

The calculation itself would be straightforward —

```
annual F-gas kgCO₂e = charge_kg × leakage% × GWP × units
```

— but adding it raises the reported operational carbon of every cooled
building. Under RICS WLCA refrigerant leakage sits in **B1**, not B6, so it is
a scope decision rather than a bug fix and needs agreeing with GT before it
ships.

## Efficiency metrics: EER, ISEER and COP are not interchangeable

The cooling form lets a user enter the efficiency figure from their own
national label. Three are offered, and only one of them needs converting:

| Metric | Unit | Where | Typical | Convert to COP |
|---|---|---|---|---|
| COP | W/W | generic | 2.3 – 5.3 | as entered |
| ISEER | W/W | India, BEE (`CSTL ÷ CSEC`) | 3.5 – 5.5 | **as entered** |
| EER | Btu/h per W | Thailand, EGAT No.5 | 9 – 14 | `÷ 3.412` |

BEAT previously divided **both** EER and ISEER by 3.412. ISEER is already
dimensionless, so an Indian 5-star unit at ISEER 5.30 was treated as a COP of
1.55 and the AC reported about 3.4× the energy it should.

No stored record was affected. The picker defaults to COP, and reconstructing
all 167 AC records from their own inputs showed every one of them was computed
on the COP basis — 105 matched the COP arithmetic exactly, 47 were entered as
a power input, and none matched the divided form. The fault was latent, not
historical.

The metric is now stored on the record (`efficiency_metric`). Without it,
re-opening a saved AC recomputed its energy against whatever the form happened
to default to, silently changing a number the user never touched.

The field hint also contradicted the code: it read "Typical EER: 2.3 – 3.5",
which is a COP range. A Thai user following that hint while EER was selected
would have entered a COP and got an answer 3.4× out. The hint now follows the
picker.

## Known gap: no part-load factor on air conditioners

```
annual energy = rated capacity × units ÷ COP × hours × days × weeks
```

This bills every operating hour at 100% of rated capacity. Real air
conditioners cycle or modulate once the setpoint is reached, so the figure
runs high. A worked example from the live data:

> A 1.5 TR (5.27 kW) split at COP 2.8 running 8 h × 7 d × 52 w
> BEAT: **5,485 kWh/yr per unit**. Metered consumption for a unit of that size
> and duty is typically **1,500 – 2,500 kWh/yr**.

Simplified tools commonly apply a part-load or diversity factor of about
0.4 – 0.7 to close that gap. BEAT applies none.

This is deliberately left alone for now. Applying a factor would lower the
reported operational energy of **every** cooled building in the database, so it
is a methodology decision to agree with GT rather than a defect to patch. Note
the same assumption does not apply to the chiller path, which is driven by a
measured plant load and a kW/RT efficiency.

One related tidy-up: `recalcCoolingSimpleEnergy` in the cooling template
multiplies the plant load by the unit count, which would double count — the
chiller tooltip correctly states the load "already covers all machines". The
function is unreferenced and is left in place only because removing dead code
was out of scope for this change; it must not be wired up as it stands.

## Unit counts: which quantities are per-unit and which are totals

Reviewed across every operational sheet, because a count multiplying a total is
how double counting starts.

| Sheet | Quantity entered | × unit count? | Verdict |
|---|---|---|---|
| Cooling — window / split / cassette / VRF | capacity or power **per unit** | yes | correct |
| Cooling — chiller | **total** plant load | no | correct; the unit count is explicitly for reference |
| Ventilation — AHU / DOAS | airflow **per unit** | yes | correct, label now says so |
| Ventilation — FCU / cassette / fan | power **per unit** | yes | **fixed**, see below |
| Lighting | watts per bulb × tubes per fixture × fixtures | yes | correct |
| Hot water | power **per unit** | yes (equipment count) | correct, label now says so |

### Fixed: the fan and FCU forms ignored their own unit count

They asked for "Total ventilation system power input" and computed
`energy = power × hours × days × weeks`, never touching `number_of_units` —
which was nonetheless a required field. Someone entering one fan's nameplate
power alongside 50 units received a fiftieth of the real figure.

Power is now asked per unit and the total derived, matching the AHU and DOAS
forms on the same page and the cooling form. `total_power_input_kw` remains the
stored field and still holds the total, so the 143 existing records keep their
meaning; the editable per-unit field is derived from it on load.

### Deliberately not multiplied

The chiller form's unit count does not scale the result, and says so in its own
tooltip: the plant energy comes from the total cooling load, which already
covers every machine. `recalcCoolingSimpleEnergy` in the cooling template does
multiply a total load by the unit count and would double count, but it is
unreferenced; it must not be wired up as it stands.

## Packaged, ductable and cassette are three different things

- **Packaged** — self-contained, every component in one casing; rooftop or
  floor-standing, air distributed through ducts.
- **Ductable** — indoor unit concealed in a ceiling void, air delivered through
  ductwork.
- **Cassette** — ceiling-recessed indoor unit of a *split* system, blowing
  straight into the room through a four-way grille. No ducts.

Cassette is therefore its own cooling type, not a sub-type of packaged. It was
briefly offered in both places; the packaged sub-type has been removed, with no
records affected.

## Refrigerant leakage is now in the operational baseline

Correcting an earlier note in this file: the refrigerant data users enter
**was** already used — `_refrigerant_scope1_saving` on the Savings tab computes
the drop from switching to a natural refrigerant:

```
saving = Σ  qty_kg × leakage% ÷ 100 × (GWP_current − GWP_natural) ÷ GFA
```

But that saving was subtracted from an **electricity-only** baseline, so BEAT
credited a reduction against emissions it had never counted, and the reported
reduction percentage came out too generous.

Leakage now appears on both sides:

```
baseline  = electricity + Σ qty × leakage% × GWP          ÷ GFA
optimised = electricity × measures
          + Σ qty × leakage% × GWP_natural                ÷ GFA
```

Magnitudes are small against electricity — 0.1 to 3.4 kgCO₂e/m²/yr across the
cooled buildings in the database — so the reduction percentage moves by about a
point. The point is consistency, not size.

Under RICS WLCA refrigerant leakage is **B1**, not B6. It is folded into the
operational baseline because that is the figure the Savings tab reduces; the
Systems tab breakdown is unchanged and still shows electricity by system.

## Plug loads count toward the total

`total_kwh` summed `plug_load_kwh` only when the user had typed one. The screen
meanwhile showed BEAT's own estimate on its own row marked "ESTIMATED", so a
summary reading 8 + 0.6 + 2.15 totalled 8.6 — which looks like an arithmetic
error rather than a deliberate exclusion.

The estimate now counts, and the total carries a tooltip saying so whenever it
is being used. A metered bill total still overrides everything, as it always
did, since it already includes plug loads.
