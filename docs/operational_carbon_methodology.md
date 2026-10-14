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

## Outdoor units (CDU) and indoor units (FCU): how BEAT counts them

**The base rule: BEAT adds every record once and deducts nothing.** Everything
below is the one exception to it.

```python
cooling_kwh     = Σ air conditioners + Σ chillers + Σ cassette ACs
ventilation_kwh = Σ everything else under ventilation   ← fan coil units sit here
total_kwh       = cooling_kwh + ventilation_kwh + lighting + …
```

### The problem this creates

Two opposite errors were possible on the same building, and neither was visible:

- **Double counting.** A matched split system's energy is derived from cooling
  capacity ÷ efficiency, and the manufacturer's capacity and COP/EER describe
  the *whole* system, indoor fan included. Entering that indoor unit again as a
  fan coil counted the fan twice.
- **Omission.** A chilled-water FCU's fan is genuinely separate from its
  chiller's electricity. Assuming the chiller figure covered it lost that load.

From the data the two look identical — a cooling record and a ventilation
record on the same building. The difference is in what the entered number
already includes, which only the user knows.

### So BEAT asks

Every cooling record carries **what its electricity figure covers**:

| Boundary | Meaning | A linked fan is |
|---|---|---|
| **Not specified** (default) | nobody has said | **added**, exactly as before |
| **Complete system, including indoor fans** | matched split or packaged unit | **not added** — already inside the figure |
| **Outdoor unit / chiller only** | VRF outdoor module, or a chiller | **added** — separate electricity |

And a fan coil or cassette row can name its parent, through
`cooling_parent_ac` or `cooling_parent_chiller` on `VentilationSystem`.

**A fan is skipped only when both are true** — it is linked, *and* its parent
says it covers the complete system:

```python
# EnergySummary.recalculate
for v in other_vent_qs:
    if v.fan_energy_already_counted:   # linked AND parent covers the system
        continue
    vent_total += v.total_energy_consumption_kwh_per_year or 0
```

### Nothing that already existed moved

All 273 cooling records and 154 ventilation rows predating the field default to
**not specified** and are unlinked, so they sum exactly as they always did.
Verified on a real building: linking a fan changed nothing; only setting the
parent to *complete system* removed it, and unsetting restored the original
figure.

Removing a fan also reduces the **estimated** plug load, which is a fraction of
system energy — so a 40 kWh fan moved the building total by 48 kWh. That is
intended.

### What this does and does not do

It **removes the ambiguity for users who fill it in**. It does **not** detect
anything on its own: an unlinked fan beside a complete-system AC record is
still double counted, and BEAT cannot know. Entering each unit of electricity
once is still the user's responsibility.

Not built, deliberately:

- no requirement to state coverage before linking
- no warning when a building has a complete-system record and unlinked fans
- no reconnection of links when a building is cloned
- no auxiliary inventory — pumps and cooling-tower fans still need separate
  accounting unless the entered plant figure already includes them

### Measured exposure, when the field was added

Of the 5 buildings with fan coil rows: **2** had a chiller (adding both is
correct), **2** had an AC record and no chiller (the real exposure), **1** had
neither. The 67 buildings with cassette rows are not in this category — a
cassette is standalone cooling equipment, already counted as cooling and
excluded from the ventilation line.

### Capacities and refrigerant

**Do not add indoor and outdoor capacities.** A 5 kW outdoor unit serving a
matched 5 kW indoor unit is a 5 kW system. For VRF, even summing the indoor
capacities does not give the outdoor capacity: Daikin's VRV S permits a
connected indoor index between **50% and 130%** of the outdoor index.

FCU fan inputs are **electrical** W or kW, not thermal capacity. The fan
calculation is power per unit × count × annual hours.

A connected DX system holds **one** refrigerant charge across the outdoor unit,
the indoor coils and the pipework — record it once on the cooling record.
A chilled-water FCU has water in its coil; Daikin's FWMJCC2BV1 lists
refrigerant as "N/A". The refrigerant belongs to the chiller.

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

## Efficiency metrics: raw value, units and rating basis

The numeric rating and selected metric are stored together and restored on edit.
COP and EER in W/W can derive full-load input as capacity / rating.
EER in Btu/h per W converts to W/W by division by 3.412 during calculation only.
ISEER, CSPF and SEER are seasonal ratings; they are retained as reference data
and cannot substitute for full-load COP. With a seasonal rating, electrical
input is required for the current screening calculation. SEER offers separate
W/W and Btu/h per W choices.

Known electrical input takes precedence over an efficiency-derived estimate.
The server recalculates annual energy rather than trusting the browser total.
These are screening estimates, not seasonal simulation: operating hours at
constant input still require a documented usage assumption or metered validation.

Chiller energy is plant cooling load (RT) x efficiency (kW/RT) x annual hours.
The whole-plant load is not multiplied by chiller count. VSD and heat-recovery
flags no longer apply automatic 20% and 30% energy discounts. This rule applies
to form calculation, save, import and the explicit recalculation command.
Existing saved estimates are not silently rewritten by the schema migration.

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

## The Savings tab reported 100% reductions it had not earned

`get_operational_savings_measures` walked the per-system carbon breakdown and
skipped any label without an entry in `_SYSTEM_STYLE`:

```python
style = _SYSTEM_STYLE.get(label)
if not style:
    continue          # baseline silently dropped
```

Only five labels have optimisation measures. The breakdown also carries plug
and equipment loads and the fuel carriers — Electricity, Natural Gas, Diesel,
Light and Heavy Fuel Oil, Firewood. Those were counted in `electricity_total`,
which is the baseline, and then skipped here, so they contributed **nothing**
to the optimised figure. A real building in the database read:

```
baseline   64.40 kgCO₂eq/m²/yr
optimised   0.00
reduction  100.0%          with an empty list of systems
```

Systems without measures now carry their baseline into the optimised total
unchanged — no saving claimed, none lost — and are listed in the strategies
panel under "No optimisation measures available", so the panel accounts for the
whole baseline instead of appearing to cover only part of it. The same building
now reads 64.40 → 64.40, 0.0%, which is the honest answer: BEAT has no measure
for plug load.

### BMS applies only to what a BMS controls

It was applied to the whole electricity total. It now applies to the systems
with measures, and the unoptimisable baseline is added afterwards — a building
management system does not switch off desk equipment or a boiler's gas supply.

### The toggles did not move the headline

`recomputeOperationalSavings()` computed a new optimised total and returned it
to nothing. Flipping a measure updated its own "Saves ~X" text while the Carbon
Reduction headline, the reduction percentage and the Baseline/Optimised pair
stayed at their server-rendered values. The return is now written back into all
four, and the client mirrors the server on refrigerant and on the unoptimisable
carry-through.
