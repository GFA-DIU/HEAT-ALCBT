> Local implementation update (14 October 2026): energy coverage, FCU parent links,
> fan W/kW precision, raw efficiency metrics and server-side screening calculations
> are now implemented on rohit-qa. The broader circuit/auxiliary/seasonal design
> below remains a proposal. See operational_carbon_methodology.md for current behaviour.

# Cooling system redesign — scope, not yet built

Written 2026-10-14 after a source-and-datasheet review of BEAT's cooling
inputs. **No code here has been written.** Three bugs the review found were
fixed separately and are listed at the end; this document covers the structural
change, which is its own piece of work and needs a decision before any code.

## The problem

BEAT stores cooling equipment as flat, unrelated records:

- air conditioners in `CoolingSystemAirConditioner`
- chillers in `CoolingSystemChiller`
- **fan coil units under *ventilation***, in `VentilationSystem`

Nothing connects an outdoor unit to the indoor units it serves. That makes two
opposite errors possible on the same building, and neither is visible:

**Double counting.** A single split AC entered as a 5 kW outdoor unit and a
5 kW indoor unit is not a 10 kW system; it is one 5 kW system. If the matched
system's total electrical input is entered against the outdoor unit and the
indoor fan is also entered, the fan is counted twice.

**Omission.** A chilled-water FCU's fan electricity is real and separate from
the chiller's. If the user assumes the chiller figure covers it, it is lost.

The same applies to refrigerant: a connected DX system holds **one** charge
across the outdoor unit, the indoor coils and the pipework. Recording the full
charge against each indoor unit multiplies it.

## Proposed shape

```
CoolingSystem                      identity + energy boundary + refrigerant circuit
├── outdoor equipment              condensing unit, VRF module group, or chiller
├── indoor equipment               DX indoor units, or chilled-water FCUs
└── auxiliaries                    pumps, cooling-tower fans
```

Two things make it work:

1. **An explicit energy boundary on the parent.** The user states what the
   entered figure already covers — matched-system total, outdoor unit only,
   compressor only — and BEAT adds the rest or does not, accordingly. This is
   the field that prevents both the double count and the omission.
2. **One refrigerant charge per circuit**, held on the parent, not per indoor
   unit.

A simple user enters one complete split system and never sees the structure. An
advanced user describes a VRF installation or a chiller plant without
duplicating energy or refrigerant.

### Arrangements that must be representable

| Arrangement | Representation | Electricity |
|---|---|---|
| Single split: one outdoor, one indoor | one system, optionally two linked records | matched system's total input, once. Add indoor fan only if excluded from it |
| Multi-split / VRF | one refrigerant system, linked outdoor + indoor | declared system total, or outdoor-unit electricity plus separately excluded indoor-unit electricity |
| Chilled water | chiller + FCUs + auxiliaries on one plant | chiller + FCU fans + pumps + tower fans, respecting the boundary |

**Capacities must not be summed across the link.** A 5 kW outdoor unit serving
a matched 5 kW indoor unit is a 5 kW system. For VRF, even summing the indoor
capacities does not give the outdoor capacity: Daikin's VRV S permits a
connected indoor capacity index between **50% and 130%** of the outdoor index,
so BEAT cannot infer plant capacity by addition.

## Three calculation routes

The route should follow what the user actually has, and the result should carry
the method, source and assumptions with it:

| Route | Basis | For |
|---|---|---|
| **Measured** | recorded kWh for a stated boundary and period | existing buildings with suitable metering |
| **Engineering estimate** | average electrical input × operating hours, or a performance model across loads | audits and detailed assessments |
| **Screening estimate** | rated input × an explicitly justified equivalent full-load hours figure | early assessments |

A user who knows their measured cooling electricity should not have to invent a
COP, a refrigerant charge and a leakage rate to get a B6 figure. Missing
refrigerant data should be reported as an **incomplete B1 assessment**, not as
a blocker on B6.

Rated power × every occupied hour is not annual consumption, particularly for
inverter equipment. A seasonal calculation needs a seasonal thermal demand, not
nameplate capacity × opening hours.

## Fields to revise

| Field | Change |
|---|---|
| Manufacturer / model | add; record indoor and outdoor where relevant |
| System configuration | **ask first**: single split, multi-split/VRF, packaged, chilled water |
| Equipment count | "number of units" is ambiguous — count complete systems, outdoor modules, indoor units, chillers |
| Rated cooling capacity | keep kW/BTU/RT; state whether per machine or whole system |
| Rated electrical input | make it a **primary entry route**; ask what it covers |
| COP / EER | require only when needed to derive power |
| Seasonal ratings | ✅ done — see below |
| Operating hours | allow fractional and seasonal variation |
| Average load | advanced input or clearly-labelled estimate; never a generic percentage presented as measured |
| Annual electricity | direct-entry route with period, source and boundary |
| Refrigerant charge | distinguish factory charge, additional piping charge, total installed |
| Annual leakage | service records where available; allow **unknown** |
| Refrigerant GWP | look up automatically with source and version |
| Energy label | optional; record country, scheme and year — a bare A–G or 1–5 is not enough |

## Chiller specifics

`total_cooling_load` currently conflates four different quantities:

- installed capacity — what the plant can deliver
- design peak load — what the building is designed to need
- actual operating load — what it needs at a moment
- annual cooling demand — thermal energy over a year

These are not interchangeable. Simple entry should ask for **rated cooling
capacity per chiller, number installed, duty/standby arrangement, and rated
total electrical input per chiller**.

Also outstanding:

- entered COP, IPLV, total power and load factor **do not drive** the active
  formula
- IPLV needs a unit and rating standard; it is a standardised part-load rating,
  not the installed plant's annual efficiency
- pumps and cooling-tower fans should be added only where excluded from the
  entered plant total
- efficiency ranges should be **plausibility warnings with an override**, not
  limits that prevent recording genuinely inefficient existing equipment

## FCU specifics

The form requires airflow and a "baseline efficiency" in W/CMH, but the formula
uses neither — it is `count × power per unit × hours`. Two routes would fit
what users actually have:

| Route | Needs |
|---|---|
| Electrical power known (preferred) | count, input per unit, fan speed/condition, hours |
| Power unknown | count, airflow, specific fan power at a stated condition, hours |

the second deriving `P(W) = airflow(m³/h) × SFP(W per m³/h)`.

Also: offer **W as well as kW** (small FCUs are specified in watts); replace the
"e.g. 8 kW" placeholder, which reads as a cooling capacity; ask whether the FCU
is chilled-water or DX; link it to its parent system; and **do not treat an FCU
as fresh-air ventilation** — a recirculation fan is not outdoor air.

## Already fixed, separately

Three bugs the review found were verified and fixed on `rohit-qa`:

1. **Chiller import ≠ manual entry.** The importer multiplied plant energy by
   the chiller count; the form does not, and the form is right. A 15-chiller
   plant imported at 945,000 kWh/yr against 63,000 entered by hand. All four
   stored records were inflated by exactly their chiller count and were
   repaired with `manage.py recalc_chiller_energy`.
2. **ISEER divided on save.** The save routine divided ISEER by 3.412 while the
   on-screen calculation did not, so a user entering 5.30 saw the right energy,
   had 1.55 stored, and on reopening read 3.4× the energy. No stored record was
   affected — all 167 were on `cop`.
3. **FCU precision.** Power was rounded to two decimals, turning 63 W into
   0.06 kW and reporting 120 kWh a year instead of 126.

And the efficiency metrics were widened to **COP, EER (W/W), EER (Btu/h per W),
ISEER, CSPF, SEER**, keeping unit and basis distinct — only Btu/h-per-watt EER
converts, and seasonal ratings are never treated as full-load COPs. That closes
a localisation gap: Indonesia and Vietnam label CSPF, Thailand labels SEER.

The VSD (−20%), heat recovery (−30%) and 7-year leakage-switch factors now
**declare themselves as BEAT assumptions** on the form rather than appearing to
come from the equipment specification. The review's deeper point stands and is
not addressed: a chiller whose entered efficiency already reflects a
variable-speed machine has the saving applied twice.
