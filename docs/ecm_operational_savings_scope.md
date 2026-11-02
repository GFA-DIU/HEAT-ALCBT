# Operational carbon savings: adding the Cambodia ECMs to BEAT

**Status: scope only. Nothing here is built.**

Source: *Deep-Dive Assessment of 250 Buildings in Cambodia*, Table 8 (summary),
Table 9 (energy saving by building type), Table 10 (investment by building
type) and Appendix IV (per-measure methodology, cost, saving, payback and CO2).

The report carries twelve Energy Conservation Measures, each with a worked
calculation, a capital cost and a payback period, applied across 250 real
buildings. BEAT today carries nine measures with a saving percentage and no
money at all. This document says what could be taken across, where it attaches,
and what it would cost us to be wrong.

---

## 1. What BEAT has today

Three layers, all in `pages/views/building/`:

| Layer | Where | What it answers |
|---|---|---|
| 1 | `embodied_benchmark_data.py`, `savings_tab.html` | How does this building compare with its peers? |
| 2 | `equipment_savings.py` | What if the equipment itself were replaced with efficient units? |
| 3 | `building_stats.get_operational_savings_measures` | What does a control bolted onto the existing equipment save? |

Layer 3 holds the measure catalogue, in `_system_measures()`:

| System | Measure | BEAT % |
|---|---|---|
| Cooling | VSD on compressors and fans | 20 |
| Cooling | Heat recovery system | 30 |
| Ventilation | Demand-controlled ventilation | 30 |
| Ventilation | VSD on AHU and FCU fans | 20 |
| Lighting | LED retrofit on fluorescent zones | 40 |
| Lighting | Occupancy and daylight sensors | 20 |
| Hot water | Heat-pump water heater | 50 |
| Lift | Regenerative drives | 20 |
| Lift | VVVF drive and sleep mode | 40 |

Plus a whole-building BMS measure and a refrigerant transition that is additive
and Scope 1 rather than Scope 2.

Each measure has an `installed` flag read from the building's own equipment
records, so a building that already has VSDs is not told to fit them. That
pattern is the main thing worth preserving: a measure BEAT cannot tell is
already present will be offered to every building forever.

## 2. What the report has that BEAT does not

| Report ECM | Report saving | Payback | Cases / 250 | Investment USD | In BEAT? |
|---|---|---|---|---|---|
| ECM1 Raise AC setpoint by 3 °C | up to 20% | immediate | 6 | none | **no** |
| ECM2 Inverter AC retrofit | up to 40% | up to 4 yr | 57 | 5,084,110 | partly, layer 2 |
| ECM3 BLDC fans | up to 50% | up to 2 yr | 6 | 5,312 | **no** |
| ECM4 LED tubes | up to 50% | up to 2 yr | 66 | 181,463 | yes, at 40% |
| ECM5 Occupancy sensors | up to 60% | up to 2 yr | 82 | 36,580 | yes, at 20% |
| ECM6 VSD / VFD | up to 30% | up to 2 yr | 1 | 139,860 | yes, at 20% |
| ECM7 Sun-control window film | up to 30% | up to 4 yr | 25 | 1,032,628 | **no** |
| ECM8 Timer switch, water dispenser | up to 50% | up to 1 yr | 43 | 10,170 | **no** |
| ECM9 Rooftop solar PV | n/a | n/a | n/a | 3,331,274 | partly, see 4.3 |
| ECM10 Cool paint | n/a | n/a | n/a | 8,192 | **no** |
| ECM11 Daylight optimisation | n/a | none | n/a | none | **no** |
| ECM12 Air curtain motion sensor | up to 20% | up to 1 yr | 2 | 140 | **no** |

Total modelled saving across the 250 buildings is about **20.2 million kWh/yr**
against roughly **188 million kWh/yr** of reported consumption, for about
**9.8 million USD** of investment.

## 3. The three measures BEAT and the report disagree on

These have to be settled before anything new is added, because today the same
building gets a different answer depending on which document you read.

| Measure | BEAT | Report | Note |
|---|---|---|---|
| LED retrofit | 40% | up to 50% | Report compares a 36-40 W fluorescent tube against an 18 W LED, which is 50 to 55% |
| Occupancy sensors | 20% | up to 60% | 60% is a corridor or toilet, where the lights were on all day. 20% is a whole building |
| VSD | 20% | up to 30% | Report's single case is a mixed-use pumping application |

The gap is not that one side is wrong. It is that the report quotes **the best
case for the zone the measure is applied to** and BEAT applies **one number to
the whole system**. Whichever is adopted, the basis has to be stated on screen,
because "up to 60%" against a building's entire lighting load is a figure
nobody can hit.

**Recommendation:** keep BEAT's whole-system percentages, and add the report's
figure as the stated best case in the measure's description rather than as the
number that drives the calculation.

## 4. What each new measure needs

### 4.1 Straightforward: data already in BEAT

**ECM1, raise AC setpoint.** `Building.cooling_temp` and `cooling_temp_unit`
already exist. The report uses 6% per °C, from the Indian BEE recommendation,
capped at 3 °C for 18%. The `installed` equivalent is a building already at or
above 25 °C, which should be offered nothing. This is the cheapest measure to
add and the only one in the report with no capital cost.

**ECM3, BLDC fans.** No fan record exists in BEAT today. The report's basis is
an induction fan at 60-70 W against a BLDC at 25-30 W. This needs either a new
equipment record or a plug-load split, so it is **not** straightforward despite
appearing so; see 4.3.

**ECM6, VSD.** Already present. Only the percentage question in section 3.

### 4.2 Needs an envelope input BEAT does not hold

**ECM7 sun-control film, ECM10 cool paint, ECM11 daylight optimisation.** All
three act on the envelope, and all three need the window-to-wall ratio, the
glazing type and the orientation. BEAT holds glazing as an embodied material
with an area, not as an envelope property with a U-value, a solar heat gain
coefficient or a facade direction.

Offering these without that data would mean applying a flat 30% to the cooling
load of any building with glass in its material list, which is exactly the kind
of plausible wrong number this codebase exists to avoid. **These three should
be deferred** until the envelope is modelled, and the deferral said out loud in
the UI rather than left as a silent absence.

### 4.3 Needs a new equipment record

**ECM3 BLDC fans, ECM8 timer switches, ECM12 air curtain sensors.** Each acts
on equipment BEAT does not model: ceiling fans, water dispensers, air curtains.
Together they are 51 of the report's 250 cases and 15,622 USD of investment,
which is 0.16% of the total. The engineering cost of three new equipment forms
is not repaid by the saving they would surface.

**Recommendation:** fold these into a single optional "small plug loads"
measure with a user-entered count, or leave them out and say so.

**ECM9 rooftop solar.** Different in kind: it is generation, not a saving.
`Building.renewable_energy_kwh`, `renewable_energy_percent` and
`renewable_input_mode` already exist and already feed
`renewable_carbon_saved_per_year` in `building_stats`. What is missing is the
**investment side**, not the energy side. At 3.33 million USD it is a third of
the report's whole investment case, so this is where money in BEAT would pay
for itself first.

## 5. The money question

This is the real gap, and it is bigger than the seven missing measures.

BEAT reports a percentage saving and stops. The report reports a cost, a saving
in USD per year, a payback and a return on investment, and that is what made it
usable for the investment pipeline in its section 5. Appendix IV gives, per
measure, the capital cost per unit, the tariff used (0.182 USD/kWh) and the
payback arithmetic.

Adding cost to BEAT means three decisions, none of them technical:

1. **Whose prices?** Appendix IV's costs are Cambodian, from 2025 site visits.
   They are not valid for India, Indonesia or Thailand. Either cost becomes a
   per-country table with a visible source and date, or it is entered by the
   user per project, or it is not added at all. A single hard-coded USD figure
   applied across four countries would be the worst of the three.
2. **Whose tariff?** 0.182 USD/kWh is Cambodia's. BEAT holds no tariff today.
3. **How stale is too stale?** A capital cost with no date on screen will be
   quoted in 2030. Whatever is stored needs its year shown next to it.

**Recommendation:** add cost as an **optional, user-entered** figure per
measure, with the report's Cambodian values offered as a labelled default that
the user can accept or overwrite. That keeps BEAT honest across four countries,
gets the payback column onto the screen, and does not commit us to maintaining
a price book.

## 6. Proposed order of work

| Step | Measure | Why first |
|---|---|---|
| 1 | Settle the three disputed percentages (section 3) | Nothing else is safe while BEAT and the report disagree on measures they share |
| 2 | ECM1 setpoint | Data already exists, no capital cost, largest no-cost saving in the report |
| 3 | Optional cost and payback per measure (section 5) | Unlocks the investment case for every measure, present and future |
| 4 | ECM9 solar investment side | Energy side already built, a third of the report's investment total |
| 5 | Envelope model, then ECM7, ECM10, ECM11 | Largest remaining saving, but blocked on real envelope data |
| 6 | Small plug loads, or a stated exclusion for ECM3, ECM8, ECM12 | Smallest value, highest cost per measure |

## 7. What this does not solve

The report's saving percentages are applied to **measured** consumption from
utility bills. BEAT applies them to **modelled** system energy. For the 251
Cambodian buildings now in BEAT those two are not the same number, and a
building whose metered consumption is implausible (see
`Cambodia_EPI_outliers_for_GT.csv`, 16 records, 20% of all reported
electricity) will produce an implausible saving however good the measure is.

Fixing the measures does not fix the inputs.
