# The generic EPD refresh of 14 July 2026, and what it means for published reports

**Who needs to read this:** anyone who has published, or is checking, a
building carbon figure produced by BEAT. This is not specific to one country
team. It is why differences are showing up across all of them at once.

**The short version.** On 14 July 2026 the generic (GFA-HEAT) emission
factors were replaced with a new version, in place, including on buildings
that had already been assessed. Any BEAT figure published before that date
and re-checked after it will differ, with no change to the building, the
quantities or the EPD chosen. For India the factors roughly halved. For
Vietnam they rose. The new values are the better ones, and the old ones were
systematically too high.

---

## 1. What actually changed

Commit `9f0a37d`, 14 July 2026, "Refresh generic (GFA-HEAT) EPDs from v2
dataset". All **305** generic rows received new GWP values, and ten
structural steel rows were re-based from kg to tonnes. The commit records the
decision explicitly: *"Per data owner: generic EPDs are country placeholders,
so refreshed values apply in place (including where already used)."*

That decision is the whole story. The EPD record a building points at is
shared, so rewriting its value changes every building already using it. No
building was edited. No quantity moved. The number underneath moved.

Only generic EPDs changed. The commit verified that every other source
(Okobaudat, IFC India, TGO, environdec, manufacturer EPDs) stayed
byte-identical. This is why some buildings in the same spreadsheet moved and
others did not: it depends entirely on which dataset their materials came
from.

### The India factors, for the materials most used

| Material | Before | After | Change |
|---|---|---|---|
| Ready-mix concrete C25/30 | 610.43 | 322.59 | -47% |
| Ready-mix concrete C30/37 | 709.55 | 374.97 | -47% |
| Cement mortar | 866.50 | 457.91 | -47% |
| Sand-lime brick | 858.24 | 442.70 | -48% |
| Concrete masonry brick | 630.53 | 333.21 | -47% |
| Facing brick, clay-based | 1528.69 | 484.89 | -68% |
| Roof tile | 45.68 | 14.49 | -68% |
| Primer emulsion paint | 2.55 | 1.09 | -57% |
| Reinforcement steel wire | 1.77 | 2.67 | **+51%** |
| Structural steel, sections | 1542.73 | 2380.64 | **+54%**, and kg to ton |

Steel moved the other way from everything else, so a building heavy in steel
and light in concrete may show almost no change, or an increase.

### It is not one country, and not one multiplier

| Country | Rows | Median new/old | Range |
|---|---|---|---|
| India | 59 | 0.52 | 0.28 to 1.51 |
| Indonesia | 59 | 0.60 | 0.32 to 1.16 |
| Thailand | 59 | 0.67 | 0.54 to 1.67 |
| Cambodia | 59 | 0.72 | 0.51 to 1.98 |
| Vietnam | 59 | **1.33** | 0.80 to 3.47 |

Vietnam went up. Anyone assuming "the factors fell" will get Vietnam wrong.

## 2. The evidence, from Haryana

105 buildings from the Haryana deep-dive were re-run against production with
the pre-14-July factors put back. Nothing else was altered.

| Outcome | Buildings |
|---|---|
| Already match BEAT today (median gap 0.10%) | **53** |
| Land on the April 2026 report once the old factors are restored | **44** |
| Move toward the report but do not reach it | 2 |
| Not explained by the refresh at all | 6 |

For those 44 buildings the gap against BEAT today has a median of **40.4%**
and a worst case of **50.0%**. After restoring the old factors the median gap
is **0.0%** and the worst is **0.1%**. That is an exact reproduction, not a
pattern that looks about right.

An independent check on the same set: across 39 buildings the April report's
implied brick factor is 1526.7 to 1527.9. The pre-refresh value of the EPD
those buildings use, `Facing brick; clay- based`, is **1528.69**. Same record,
old value.

**The 8 buildings the refresh does not explain are real findings** and should
be looked at on their merits. They are the last-minute edits and typos the
reviewing consultant already identified, and they are now separable from the
factor change instead of buried in it.

## 3. Which value is right

The new ones. BEAT holds independent published datasets for the same
materials, so the India generic value can be checked against its German
Okobaudat twin. India's grid and clinker route are more carbon-intensive than
Germany's, so a credible India figure sits above the German one by a sensible
margin.

| | India / Germany |
|---|---|
| Old values, 18 materials | 2.55 to 2.92, median 2.75 |
| New values, same 18 | 0.81 to 1.53, median 1.45 |

A ratio of 2.75 for ready-mix concrete is not defensible. Concrete carbon is
dominated by clinker chemistry rather than grid electricity, so it cannot be
nearly three times the German figure. The old dataset was inflated by roughly
1.9x. The new one is in the range a localization should produce.

**One caveat, stated rather than hidden.** Three materials now sit *below*
their German twin: facade clinker 0.90, facing bricks 0.81, lime plaster
1.05. Those are the weakest values in the new set and are worth checking
against a published Indian EPD before being quoted on their own.

## 4. What to do

1. **Any BEAT figure published before 14 July 2026 should be treated as
   superseded** where the building used generic EPDs. It is not wrong in the
   sense of a mistake made at the time. It is computed on factors that have
   since been corrected.
2. **Check before re-quoting an old figure.** If a building's materials came
   from a manufacturer EPD, Okobaudat, IFC India or TGO, nothing changed and
   the old number still stands.
3. **Do not apply a blanket correction factor.** The change is
   material-specific and country-specific, and steel moved the opposite way.
   Re-read the building in BEAT instead.
4. **When a report is reissued, say which date's factors it used.** This will
   happen again the next time a dataset is improved, and a report that names
   its vintage is one nobody has to re-litigate.

## 5. The underlying issue, for the record

Refreshing a shared EPD in place silently changes every building that already
used it, including buildings whose results are printed in a published report.
BEAT keeps no record of what a building's carbon figure was at the time it was
assessed, so there is no way inside the tool to see that a number moved or
why.

Nothing here argues the refresh should not have happened. The old values were
wrong and correcting them was right. The gap is that the correction was
invisible: the first anyone knew of it was a consultant noticing that an
unusual number of projects disagreed with their report, across every team at
once.

Worth considering, in rough order of cost:

- Record the factor version against each building assessment, so a figure can
  say which dataset produced it.
- When a dataset refresh lands, produce the list of affected buildings and
  the size of the move, rather than discovering it months later.
- Decide deliberately whether a refresh applies to existing assessments or
  only to new ones. On 14 July the answer was "in place", which was a
  defensible choice but was not communicated to the people holding the
  published numbers.

---

*Sources: commit `9f0a37d`; `pages/data/generic_EPDs.csv` before and after;
production EPD records as at 29 October 2026; 105 Haryana buildings re-run
against production with pre-refresh factors.*
