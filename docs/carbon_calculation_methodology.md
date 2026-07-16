# BEAT — Carbon Calculation Methodology (Embodied & Operational)

Status: **for review.** Describes how BEAT currently computes whole-life carbon, the
standards basis, known limitations, and the agreed improvement roadmap. Grounded in the
current code (referenced inline).

## 1. Standards basis & scope

BEAT follows the building-LCA framing of **EN 15978** (life-cycle modules), with product
data from **EN 15804 / ISO 21930 EPDs** and impacts expressed as **GWP (kgCO₂e)**.

**Modules BEAT currently computes:**
| Module | Covered? | Notes |
|---|---|---|
| **A1–A3** Product (embodied) | ✅ | From EPDs × quantities. Headline embodied figure. |
| A4–A5 Transport / construction | ❌ | Not modelled. |
| B4 Replacement / maintenance | ❌ | Single service life assumed; no material replacement over RSP. |
| **B6** Operational energy | ✅ | Annual energy × emission factor × reference period. |
| B7 Operational water | ❌ | Not modelled. |
| C1–C4 End-of-life | ❌ (data present, not aggregated) | Some EPDs carry C3/C4; not summed into the headline. |
| D Beyond system boundary | ❌ (data present, not aggregated) | Some EPDs carry module D; not summed. |

So **whole-life carbon in BEAT = A1–A3 (embodied) + B6×RSP (operational)**. This is a
common simplified scope; the excluded modules are the main scope limitation (see §5).

## 2. Embodied carbon (A1–A3)

**Formula:** for each material in an assembly, `impact = quantity × EPD_impact_per_declared_unit`,
after resolving units. Logic in `pages/views/building/impact_calculation.py`.

- **Dimensions:** AREA / VOLUME / MASS / LENGTH / PCS / TON. `ton` is normalised to kg
  (÷1000). BoQ mode infers the dimension from the input unit.
- **Unit resolution:** direct match when the assembly unit equals the EPD's declared unit;
  otherwise conversion via the EPD's density/geometry factors (volume density kg/m³, area
  density kg/m², linear density kg/m, layer thickness, conversion-to-1kg). If no conversion
  path exists, the material cannot be added (the UI blocks it and explains why).
- **Aggregation** (`building_dashboard/utility.py`): embodied uses **`gwp a1a3`** only, and
  **negative values are clamped to 0** (`gwp a1a3 pos`) — i.e. biogenic/credit negatives are
  not netted into the embodied headline (a conservative choice; document if that should change).
- **Categorisation is display-only.** `EPD.category` (via the shared resolver
  `pages/scripts/epd_categorization.py`) drives the material dashboard grouping and the
  library chips; it does **not** affect the calculation.
- **GCCA A–G concrete ratings** are computed from GWP + strength class
  (`pages/scripts/Label_mapping/gcca_rating.py`) — informational, not part of the total.

**EPD data sources:** Ökobaudat (Germany, reference set), TGO (Thailand), ECO-Platform
distributed nodes (environdec, EPD Norway, …), and **generic "GFA-HEAT" placeholder EPDs**
used when a country lacks a real EPD.

**Embodied limitations:** A1–A3 only (no A4/A5/B4/C/D); reliance on generic placeholders where
coverage is thin; category is not used in the maths (so a mislabel is cosmetic, not a calc error).

## 3. Operational carbon (B6)

**Formula** (`building_dashboard/utility.py` `prep_operational_df`):
`operational_GWP = annual_energy × emission_factor × reference_period`, with
`gwp_b6` held **constant** across the reference period (`building.reference_period`, default **50** yr).

- **Annual energy** is modelled from the building's equipment inputs (cooling, ventilation,
  lighting, hot water, etc.) — a single representative annual figure, not year-by-year metered data.
- **Emission factors** are per-carrier at stage B6 (per kWh): **electricity is country-specific**
  (grid mix); **fuels use one shared factor** across the ALCBT countries (combustion ≈ physics).
- **Current electricity factors (kgCO₂e/kWh):** TH 0.475, VN 0.659, KH 0.588, ID 0.78, IN 0.705.
  (VN and KH were corrected 2026-07 from understated 0.410/0.418 to MONRE 2023 / EAC 2023.)
- **Building age:** BEAT uses a **timeless design assessment** — the RSP is assessed from the
  assessment year with the representative annual energy; the building's actual age/construction
  year is **not** an input and does not change the result.

**Verdict:** annual × RSP (constant) is the standard EN 15978 B6 approach and in line with One
Click LCA and peers. It is a valid, if conservative, baseline.

**Operational limitations:** the constant factor ignores grid decarbonisation (overestimates
electricity carbon over 50 yr); no operational water; mass/volume fuels are stored per-kWh
(calorific conversion pending); the envelope's thermal performance does not feed operational
energy (see §5).

## 4. Whole-life result
`Total = Σ embodied(A1–A3) + operational(B6) × RSP`, shown as the embodied/operational split
(e.g. the "Whole Life Carbon" donut).

## 5. Known limitations & improvement roadmap

1. **Grid decarbonisation (designed, not built).** Make the electricity factor **decline** over
   the RSP instead of staying constant — **optional per-building toggle** (constant ↔ declining),
   **electricity-only**, linear anchor→target, data-driven. Locked dataset:

   | Country | Anchor kgCO₂/kWh | Source | Net-zero yr | Residual | Eff. 50-yr factor | vs constant |
   |---|---|---|---|---|---|---|
   | Thailand | 0.475 | TGO 2022–24 | 2050 | 0.05 | ~0.152 | −68% |
   | Vietnam | 0.659 | MONRE 2023 | 2050 | 0.05 | ~0.196 | −70% |
   | Cambodia | 0.588 | EAC 2023 | 2050 | 0.05 | ~0.179 | −70% |
   | Indonesia | 0.78 | national published | 2060 | 0.05 | ~0.298 | −62% |
   | India | 0.705 | CEA/IEA ~0.71 | 2070 | 0.05 | ~0.338 | −52% |

   Report constant vs declining side by side. Upgrade path: swap in IEA WEO/APS year-by-year values.

2. **Embodied ↔ operational thermal trade-off (not feasible now).** A low-embodied material can
   insulate poorly → higher operational energy. BEAT cannot flag this because **thermal
   conductivity λ is not in the EPD data** (0 of 1,279 envelope EPDs carry it; λ is a performance
   property, not an EN 15804 impact). Proper fix needs an envelope U-value→energy link (an energy
   model), which belongs with the future gbXML/energy-simulation work using an **ISO 10456** λ
   reference table by material type — not EPD data.

3. **Module scope.** Adding A4/A5 (transport/construction), B4 (replacement over the RSP), and
   C/D (end-of-life, already partly in EPD data) would move BEAT toward full EN 15978 coverage.

4. **Operational fuels.** Diesel/LPG/etc. are stored per-kWh; converting the TGO per-litre/kg
   factors needs calorific values (deferred, Thailand-scoped).

## 6. References
- EN 15978 (building LCA), EN 15804 / ISO 21930 (EPDs), ISO 14040/44.
- Grid EFs: TGO (Thailand), MONRE 2023 (Vietnam), Electricity Authority of Cambodia 2023, IEA
  Emissions Factors, CEA (India). Net-zero pledges (national NDCs). ASEAN trajectory ~0.54→0.18
  kgCO₂/kWh by 2050 (S&P Global / ScienceDirect).
- GCCA concrete Low Carbon Ratings — see `docs/` GCCA notes / gccaepd.org/blog/lcr.
