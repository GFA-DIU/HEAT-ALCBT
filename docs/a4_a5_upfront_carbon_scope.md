# A4–A5 Upfront Carbon — Feature Scope (BEAT)

Status: **SCOPE / design — finalised, ready to build on approval.**
Branch: rohit-qa. Date: 2026-08.

## 1. Objective

Extend BEAT's embodied carbon (today **A1–A3 only**, hard-filtered in
`building_stats.py`) to full **upfront carbon**:

- **A4 — Transport to site**
- **A5w — Construction waste** (incl. end-of-life of the wasted material)

Reported as **Upfront Carbon = A1–A3 + A4 + A5w** (kg CO₂e/m²). Deferred to phase 2:
A5a site-activity energy; full C modules on installed (not wasted) materials.

## 2. Methodology basis — RICS WLCA 2nd ed (2023, v3 Aug 2024), EN 15978

Confirmed mechanics from the standard:
- **A4** = `mass × distance × transport EF` (**tonne-km method** — RICS/EN 15978/GHG Protocol
  Cat-4/GLEC default). RICS' `[CF_out + 0.5×CF_return]` form is for *per-vehicle-km* factors.
  **BEAT uses per-tonne-km intensities (GLEC/SFC/TGO), which already embed load factor + empty
  running — so we apply the EF once, no separate return term.**
- **Number of trips is NOT asked.** The trip / vehicle-km (fuel-based) method needs real
  logistics data (truckloads, vehicle size) that doesn't exist at early design, and trips are
  already embedded in the per-tonne-km EF; asking would add friction and risk worse estimates.
  A per-material trip override (for light/bulky "cube-out" materials) is noted as a possible
  future advanced option, not in v1.
- **A4 default transport scenarios** = RICS Table 17 (avg rigid HGV road; container ship sea).
  RICS explicitly says: *"similar default scenarios should be developed for different
  countries outside the UK"* → justifies our per-country tables.
- **A5w** = `waste_rate × ([A1–A3] + [A4] + disposal EF) of the wasted material`.
  Waste rates from RICS **Table 18** (BRE PCR / SmartWaste); disposal factor from
  **Table 19** (default = landfill/incineration, C2+C4).

## 3. Country transport emission factors (kg CO₂e/tonne-km)

| Country | Source | Road | Rail | Sea |
|---|---|---|---|---|
| India | **SFC/WRI India Default GHG Values v1.0 (May 2025)**, GLEC v3.1/ISO 14083, by GVW class | ~0.05–0.09 | ~0.006–0.011 | — |
| Thailand | **TGO** national EF database (same body as our TGO EPDs) | national value (lock at build) | — | — |
| Cambodia / Vietnam / Indonesia | **GLEC v3 default** (avg laden HGV, WTW, AR6) | ~0.10 | ~0.02–0.03 | ~0.008–0.015 |

Exact per-class India values and the Thailand TGO value are pulled into the seed table at
build. Sea leg (imports) = GLEC container-ship default everywhere.

## 4. Sourcing scenarios (how A4 distance is set) — RICS-style

Each material is auto-assigned a **sourcing scenario** (user-overridable dropdown). Each
scenario maps to a distance + mode + the country EF above:

| Scenario | Journey | Auto-assigned to (by MaterialCategory) |
|---|---|---|
| **Local** | ~50 km road | Concrete, aggregate, sand, cement, blocks/bricks/AAC, mortar/plaster |
| **National** | ~300 km over land, **split rail/road by country** | Reinforcement, timber, tiles, plasterboard, finishes |
| **Imported** | ~3,000 km sea + ~150 km inland road | Structural steel, aluminium, glass, specialised products |

Distances are country-tunable (RICS Table 17 as the template). User can switch any material's
scenario.

### A journey is a list of legs, not one averaged number

A scenario resolves to **one leg per transport mode**, each carrying its own
mode's emission factor, and A4 sums them. This replaced an earlier model that
collapsed each scenario into a single distance and a single *blended* factor.

That blend was the source of a real complaint: for India it reported
**0.070 kgCO₂e/tonne-km over 50 km and 0.01286 over 3,150 km**, which reads as
the emission factor falling as the distance grows. The arithmetic was right — a
3,150 km import is 95% sea, and sea freight is roughly seven times cleaner per
tonne-km than road, so an average dominated by the sea leg sits near the sea
figure — but the number shown was a weighted mean of two different vehicles and
was not a property of anything. The carbon it stood for had been rising all
along (3.5 → 21 → 40.5 kgCO₂e/tonne).

Nothing now reports a blended factor. `effective_ef()` survives for exactly one
job: filling in the missing half when a user overrides a distance but not a
factor, or the reverse. Setting either by hand replaces the journey with a
single explicit leg, because someone who types "400 km" means one trip of
400 km, not a reshuffle of the legs behind it.

### Rail

`rail` was defined for every country and **used by no code path**. It is now the
line-haul portion of the national scenario:

| Country | National rail share | Why |
|---|---|---|
| India | 60% | dedicated freight corridors; cement and steel move by rail |
| Thailand | 30% | rail freight exists but road dominates |
| Vietnam | 20% | north–south line used for bulk, limited capacity |
| Indonesia | 10% | archipelago; rail freight is Java-only and marginal |
| Cambodia | 0% | negligible rail freight — treated as all road |

⚠️ **These shares are an assumption, not sourced**, and they are the least
defensible numbers in the file. They are also consequential: India's rail factor
(0.008) is about a ninth of its road factor (0.070), so introducing the split
moved India's national haul from 21.0 to **9.84 kgCO₂e/tonne**. Replace them
with real modal-split data before any published figure relies on them.

## 5. Construction waste rates (A5w) — RICS Table 18 defaults

Auto-assigned per **MaterialCategory**, shown and editable. Representative defaults
(final values from RICS Table 18 at build):

| Material category | Waste % |
|---|---|
| Concrete / screed | 5 |
| Reinforcement / structural steel | 1–5 |
| Cement / mortar / render / plaster | 10–12 |
| Masonry blocks / bricks / AAC | 15 |
| Timber | 10 |
| Ceramic / tiles | 10 |
| Plasterboard / gypsum | 20 |
| Insulation | 10 |
| Glass / aluminium (windows) | 5 |
| Default (unlisted) | 8 |

Disposal factor (Table 19 default = landfill): `A4-to-disposal + C2+C4`, a small
country/material default (inert vs non-inert), calibrated at build.

## 6. Input flow & UI (finalised)

**Principle: adding a material does NOT gain a new mandatory prompt. A4/A5 are
auto-assigned and shown; overriding is optional and inline.**

Current add-material flow (unchanged): open Structural editor → filter/search EPD list →
click EPD → material row inserted → enter **quantity** → Save (`StructuralProduct`).

A4/A5 layers onto that as follows:

1. **Building-level defaults are automatic from the building's country** — no new settings
   screen. Distances, freight EFs, waste rates and disposal factor derive silently from the
   country already on the building. A read-only "A4–A5 assumptions" summary is available.
2. When a material row is added, it is **auto-assigned** by its **MaterialCategory**:
   a **sourcing scenario** (Local / National / Imported) and a **waste rate** (RICS Table 18).
3. Each material row shows a **live module split: `A1–A3 | A4 | A5w`**, recomputing as the
   quantity or scenario changes.
4. Each row has a **collapsible "Transport & waste (A4–A5)"** section (closed by default):
   editable **sourcing-scenario dropdown**, editable **waste %**, and (if Imported) an
   editable sea distance. "Reset to country default" per row.
5. Official EPDs carrying real A4/A5 use those; estimates only fill gaps.
6. Dashboard & report: `A1–A3 | A4 | A5w | Upfront A1–A5` + an assumptions appendix.

Flow in one line: **add material → quantity only (as today) → A4/A5 auto-computed & shown
live → optional inline override.**

**Delivery:** built and tested locally on **rohit-qa** only; never pushed to main (PRs to qa
only when explicitly requested).

## 7. Formulas (final)

```
A4_material   = (mass_kg / 1000) × Σ( leg_km × leg_EF )     over the journey's legs
A5w_material  = mass_kg × waste_rate × ( GWP_A1A3_per_kg + A4_per_kg + disposal_EF_per_kg )
Upfront       = Σ(A1A3 + A4 + A5w) / GFA        [kg CO₂e/m²]
```
mass_kg reused from the existing A1–A3 resolution (density/thickness/cross-section).

## 8. Architecture & data model

- Compute A4/A5w inside `calculate_impacts` (reuse resolved mass); return `gwp_a4`, `gwp_a5w`
  next to `gwp_a1a3`. `building_stats.py` aggregates and adds an **Upfront (A1–A5)** total.
- New model `A4A5CountryDefault` (seeded via a management command like the EPD loaders):
  road/rail/sea EF, local/national/import distances, disposal EF, source label — per country.
- `StructuralProduct` gains nullable `sourcing_scenario` + `waste_rate` (null → category/country
  default). Optional building-level override record.
- Real EPD A4/A5 (official EPDs) take precedence over estimates.
- Dashboard & report: A1–A3 | A4 | A5w | Upfront A1–A5 breakdown + an assumptions appendix
  (scenario, distance, EF, waste %, source) for auditability.

## 8a. Editability & data governance (what can be changed, where, by whom)

| Data | Editable? | Where / how | Who |
|---|---|---|---|
| **Sourcing scenario** (Local / National / Imported) per material | ✅ Yes | Inline in the material row's collapsible "Transport & waste (A4–A5)" override | End user |
| **Waste rate %** per material | ✅ Yes | Same collapsible row section (pre-filled RICS Table 18 default) | End user |
| **Sea distance** (Imported scenario only) | ✅ Yes | Same row section (shown when scenario = Imported) | End user |
| **Quantity + unit** | ✅ Yes (already today) | Material row | End user |
| **Country default distances** (local/national/import km) | ⚙️ Config, not in-app v1 | `A4A5CountryDefault` seed CSV + management command (like EPD loaders); or Django admin | Admin/dev |
| **Country freight EFs** (road/rail/sea, kg CO₂e/t-km) | ⚙️ Config, not in-app v1 | Same seed table / Django admin | Admin/dev |
| **Waste-rate defaults per MaterialCategory** (RICS Table 18) | ⚙️ Config, not in-app v1 | Seed table / admin (end user overrides per material instead) | Admin/dev |
| **Disposal EF** (A5w end-of-life default) | ⚙️ Config, not in-app v1 | Seed table / admin | Admin/dev |
| **Real A4/A5 from an official EPD** | 🔒 No | Read from the EPD's impact data; used instead of the estimate | — (source data) |

Design intent: **country/methodology defaults are auditable config** (seeded + version-controlled,
not silently changeable per session), while the **end user adjusts at the material level**
(scenario + waste %) — which is enough to fully control the A4/A5 result for their project.
If a per-building "assumptions panel" to edit country defaults in-app is wanted later, it can be
added (was offered, not selected for v1).

## 9. v1 limitations (flagged in report)

- A5a site-activity energy excluded (phase 2).
- Full C modules on *installed* materials excluded; only *wasted* material carries a default
  disposal factor (phase 2 = full end-of-life).
- Non-India/Thailand countries use GLEC regional freight EFs (no national study found).
- Distances are default sourcing scenarios unless the user overrides — not project-actual.

## 10. Sources
- WRI India GHG Program — Transport EFs: https://indiaghgp.org/transport-emission-factors
- SFC India Default GHG Emission Values v1.0 (May 2025): https://smart-freight-centre-media.s3.amazonaws.com/documents/India_Default_GHG_Emission_Values_V1_SFC_INDIA_latest.pdf
- RICS WLCA 2nd ed (Sept 2023, v3 Aug 2024): https://www.rics.org/content/dam/ricsglobal/documents/standards/Whole_life_carbon_assessment_PS_Sept23.pdf
- GLEC Framework v3 (Smart Freight Centre).
