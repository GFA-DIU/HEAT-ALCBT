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
| Indonesia | 0.676 | IEA / national ~0.68 |
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
| Indonesia | 0.676 | IEA ~0.68 | 2060 | 0.05 | ~0.263 | −61% |
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
