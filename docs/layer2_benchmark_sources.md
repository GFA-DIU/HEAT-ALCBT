# Layer 2 benchmarks: what each country actually publishes

Layer 2 of the Savings tab asks what replacing a building's equipment with
efficient units would save. That needs a target to replace *towards*, and a
target is only worth having if someone published it.

This file records what was found when the sources were read, including where
nothing exists. A gap recorded is a gap someone can close; a gap filled by
guesswork is a wrong number nobody catches.

Companion to `docs/Operational_Carbon_Savings_Methodology_and_Logic_v1.1.docx`,
which specified Layer 2 and deferred it from v1.

---

## Why the workbook alone was not enough

`Operational_Carbon_Benchmark_restructured.xlsx` is the source for Layer 1 and
was the starting point here. Reading the underlying codes found two errors in
it, both of which would have produced confident wrong savings.

**India's lighting densities were shifted one row.** The base column was
right; ECBC+ and Super had slipped one row down ECSBC Table 7.2/7.3. Shopping
Mall carried Hospital's figures, Hospital carried Hotel's, Hotel carried
Shopping Mall's. The tell is Hotel: ECBC+ 11.3 against a base of 9.5, a tier
that tightens being laxer than the one it tightens. Corrected 19.10.2026.

**The split-unit row gives LEED 1.36 kW/RT**, against national baselines of
0.80 to 0.85 - "best practice" 60% worse than average, which is COP 2.59
against COP 4.14. Vietnam's own split baseline of 1.35 sits one cell away and
is 60% worse than every neighbour. Both look like copy errors. Neither is
corrected, because unlike the lighting case there is no source here that says
what they should be. `_best_practice_is_credible` refuses them instead.

---

## India - commercial

**Energy Conservation and Sustainable Building Code 2024 (ECSBC 2024)**,
`ESCBC_Commercial.pdf`. Note this supersedes the ECBC 2017 the workbook was
built from. Three tiers: ECSBC, ECSBC Plus, Super ECSBC.

| Quantity | Where | Form |
|---|---|---|
| Interior lighting power | Tables 7.1-7.3, pp. 77-78 | absolute W/m2, three tiers, by building type |
| Lifts | Table 8.11, p. 90 | energy class A-G via IS 17515 Part 2 |
| Escalators | Table 8.11, p. 90 | energy performance ratio, classes A+++ to E, via IS 17515 Part 3 |
| Cooling equipment | Tables 6.1, 6.2, 6.12, pp. 72-83 | **values do not extract** - see below |
| AHU fans | Tables 6.9-6.11, p. 83 | mechanical efficiency % + motor class, by tier |

### The chiller table will not come out of the PDF

Table 6.12 (Minimum Efficiency Requirements for Chillers for ECSBC, ECSBC+
and Super ECSBC) exists and is referenced in the text, but its values are not
in the PDF's text layer - pypdf returns the table captions and numbering
(6.13, 6.14 ...) and none of the figures. The same is true of Tables 6.1
(unitary AC) and 6.2 (VRF).

They need reading by eye, or a tool that can reach the table graphics. Until
then India's cooling benchmarks stay on the workbook, marked unverified.
Chillers are additionally required to be rated at full and part load per
IS 16590.

### AHU fans: a real figure, but not the one BEAT stores

ECSBC does publish fan requirements by tier:

| Tier | Mechanical efficiency | Motor |
|---|---|---|
| ECSBC | 65% | IE 3 |
| ECSBC Plus | 70% | IE 4 |
| Super ECSBC | 75% | IE 4 |

**This is not specific fan power.** BEAT stores W/CMH; converting mechanical
efficiency into W/CMH needs the fan's pressure rise, which BEAT does not
collect:

```
SFP (W/CMH)  =  pressure rise (Pa)  /  (efficiency x 3600)
```

Assuming a pressure rise to make the two comparable would manufacture exactly
the kind of number this review exists to catch, so ventilation stays on the
workbook's W/CMH, marked unverified. Collecting fan static pressure would make
the code figure usable.

### Lifts are the interesting one

BEAT has no lift benchmark and this is why that is fixable. ECSBC classifies a
lift by its daily energy against the **ISO 25745-2** formula, adopted in India
as IS 17515 Part 2:

```
Ed  <=  k x Q x nd x Sav / 1000  +  c x tnr        (Wh per day)

  Q    rated load, kg
  nd   starts (trips) per day
  Sav  average travel distance, m
  tnr  non-running time, hours
```

| Class | k | c | ECSBC tier |
|---|---|---|---|
| A | 0.72 | 50 | Super ECSBC |
| B | 1.08 | 100 | ECSBC Plus |
| C | 1.62 | 200 | ECSBC |
| D | 2.43 | 400 | |
| E | 3.65 | 800 | |
| F | 5.47 | 1600 | |
| G | 5.47 | 1600 | extracts identically to F; suspected PDF artefact, verify against IS 17515 |

**BEAT collects none of Q, nd, Sav or tnr.** The lift form has a count and two
checkboxes. Using this method is a four-field form change, not a table entry,
and that is why the current estimate is still 7.5% of the other systems.

---

## India - residential

**Eco-Niwas Samhita 2024 (ENS 2024)**, `ENS_Residential.pdf`.

The important finding is a negative one, and it vindicates the blank in the
workbook rather than contradicting it.

**ENS regulates lighting only in common areas.** Table 10 gives corridor
3.0 W/m2 and basement/stilt parking 1.0 W/m2; Table 11 covers outdoor zones.
There is no published Indian lighting power density for the inside of a
dwelling. So `LPD_BENCHMARKS["Residential"]["India"]` stays `None`, and the
common-area figures are held separately as `ENS_COMMON_AREA_LPD` precisely so
nobody mistakes a corridor limit for a living-room target.

ENS offers an alternative compliance route throughout: lamps of at least
95 lm/W instead of meeting the density. A building over the density is
therefore not automatically non-compliant.

**Residential cooling is a star level, not a number.** Section 5.2.3 B:
unitary 5 star, split 3 star, chiller 3 star, VRF 3.28 EER or 4.36 IEER. Only
the VRF line is absolute; the rest defer to the BEE Standards and Labelling
Program, whose ISEER thresholds per star are published separately and are not
in this document. A residential split cannot be benchmarked from ENS alone.

Converting the one absolute figure for comparison: 3.28 EER is 1.072 kW/RT,
which is **laxer** than the 0.86 the workbook carries as India's VRV national
baseline. A code minimum should not be stricter than typical stock. One of the
two is wrong and it is worth resolving before either becomes a target.

**Lifts in ENS are prescriptive only** - IE3 motors, lamps at 95 lm/W,
auto switch-off - with no energy classification. The ECSBC method above does
not carry over to residential.

---

## Other countries

**Not yet verified against any source.** Thailand, Vietnam, Indonesia and
Cambodia currently rest on the workbook alone, which the India review has just
shown can be wrong in ways that survive a plausibility check.

The figures in use are in `system_efficiency_data.py`. Until each is traced to
its national code they should be treated as provisional, and the UI says so.

Known gaps regardless of source:

- **window and packaged AC** - no row in any country. 20 units in production.
- **Thailand VRV** - blank in the workbook.
- **Indonesia hot water** - blank for heat pump, solar and boiler alike.
- **ventilation** - one figure per country, with no variation by building
  type, so a hospital AHU and an office AHU are judged identically.

---

## How provenance is recorded

Every benchmark carries a citation and a status, returned by
`benchmark_source()` and surfaced on the Savings tab:

| Status | Meaning |
|---|---|
| `verified` | someone read the figure in its own national code and recorded the table |
| `unverified` | it came from the workbook and has not been traced to a source |

Today exactly one entry is verified: India lighting, against ECSBC 2024
Tables 7.1-7.3. Everything else is unverified, which is the worklist.

This exists because the India lighting error was invisible to inspection - the
figures were real ECBC numbers attached to the wrong building types, and only
opening the code found it. The difference between "ECSBC 2024 Table 7.3" and
"a spreadsheet" is the difference between a target a user can check and one
they have to trust.

## Why there is no EUI benchmark for most of the region

Searched 19.10.2026. The finding is structural rather than a gap in the
search: **no ALCBT country publishes a whole-building EUI in its building
code.** All five are prescriptive, setting envelope performance, lighting
density and equipment minimums rather than a kWh/m2/yr target.

| Code | Sets | Whole-building EUI |
|---|---|---|
| Vietnam QCVN 09:2017/BXD | envelope, LPD 11 W/m2 offices, COP/CSPF minimums | no |
| Indonesia SNI 6389:2020 | envelope design criteria | no |
| India ECSBC 2024 | LPD, equipment minimums, lift classes | no |
| India ENS 2024 | RETV envelope, common-area LPD | no |
| Thailand BEC | not located | - |

A national-average EUI is a **measured statistic, not a code value**. India's
rows in `NATIONAL_AVG_EUI` come from the BEE 1,160-building survey, which is a
study. The equivalent surveys for the other four either do not exist or are
not published per m2.

What was found:

* **Indonesia offices, 160 kWh/m2/yr** mean across 33 buildings, with under
  115 treated as high performance and over 190 as inefficient.
  **Not applied** - the workbook carries 250 for the same cell, 586 production
  buildings are benchmarked against it, and the two may not cover the same end
  uses. Recorded in `operational_benchmark_data.py` for a decision.
* **Household surveys** for Bangkok (16.2 GJ), Hanoi (18.2), Ho Chi Minh City
  (18.8) and Phnom Penh (13.2) are per household, not per m2. Converting them
  needs a typical dwelling floor area, which would be an assumption driving
  the entire result.
* **Vietnam office LPD 11 W/m2** from QCVN 09 matches the workbook exactly.
  That cell is now marked verified - the one thing a prescriptive code can
  confirm.

So residential EPI stays blank across the region, and that is a data gap for
ALCBT to fill rather than one BEAT should paper over.

## The rule that kept this honest

From the workbook's own `0_README`, and worth repeating because the India
review turned entirely on it:

> Blank = no benchmark published; do not synthesise.

A blank is a finding. The India residential row is blank because India has not
published that number, and writing a plausible figure there would have buried
the very thing a methodology review is for.
