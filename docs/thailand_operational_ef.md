# Thailand Operational Emission Factors (energy carriers)

Source: `Operational_EF_TH` sheet in `docs/TH_CFP_Final_Usable_Dataset_20260709.xlsx`
(TGO, CFO-based national emission factors). Applied 2026-07.

## How operational energy carriers are stored

- Model: generic EPDs, `source = GFA-HEAT`, `type = generic`, category under
  `9.2 Energy carrier - delivery free user`.
- **All carriers are stored per `kWh`** (declared_unit = kwh) at life-cycle stage
  **b6** (operational energy use). Impact = `gwp_b6` (kgCO2e per kWh).
- Data file: `pages/data/generic_operational_EPDs_v2.csv` (one row per carrier ×
  country). Loaded by `import_generic_operational_epds`.

## Per-country logic (investigated)

| | Behaviour |
|---|---|
| **Electricity** | **Country-specific** — grid mix differs (IN 0.705, ID 0.676, KH 0.418, TH 0.475, VN 0.410 kgCO2e/kWh). |
| **All fuels** | **One shared factor across all 5 ALCBT countries** — fuel combustion is ~country-independent (IPCC-based). |

## What was changed (Thailand)

Per data owner, generic carriers are placeholders and values were **updated in
place** (existing buildings reflect the new factors).

1. **Electricity (TH): 0.5607 → 0.475** kgCO2e/kWh (TGO 2022–2024 grid mix). Same
   unit, direct.
2. **Natural Gas (TH): 0.264 → 0.18072** kgCO2e/kWh. TGO gives 0.0502 kgCO2e/**MJ**;
   MJ→kWh is a pure unit conversion (×3.6 = 0.18072). No assumptions. **TH only** —
   the other 4 countries keep the shared 0.264.
3. **Names** cleaned to uniform Title Case, TGO-aligned, across all 5 countries
   (display only; does not affect any calculation):
   `cerosin → Kerosene`, `char coal → Charcoal`, `coal → Coal`, `diesel → Diesel`,
   `electricity → Electricity`, `fire wood (…) → Firewood (Log Wood / Wood Chips /
   Wood Pellets)`, `Heavy/Light fuel oil → Heavy/Light Fuel Oil`, `lignite → Lignite`,
   `Liquefied petroleum gas (LPG) → Liquefied Petroleum Gas (LPG)`,
   `natural gas → Natural Gas`.

## Deferred (needs a decision / more data)

- **Mass/volume fuels** (Diesel 2.7076/L, LPG 3.1133/kg, Kerosene 2.4911/L, Fuel
  Oil, Coal, Lignite, Charcoal, Fuel Wood …). TGO gives these per **liter/kg**, but
  the model stores per **kWh**. Converting requires **calorific values (kWh per
  L/kg)** which are NOT in the sheet. Scope agreed = **Thailand only** when done.
  Left unchanged for now to avoid baking in calorific assumptions.
- **Refrigerant GWP section** of the sheet was **NOT imported** — the data looks
  corrupted: English names are shifted vs the Thai names (e.g. Thai "R-410A" labelled
  English "Refrigerant R-143", GWP 328 which is wrong for R-410A) and the methodology
  column reads a non-existent "AR5…AR11". Needs the source file fixed first.

## Deployment note

The DB rename (old → Title Case names) was applied to the local DB directly. A
production DB still holds the old names, so before/with re-running the operational
loader on prod the same rename must be applied (else the new-name CSV rows insert
duplicates). Options: a one-off rename step, or a data migration.
