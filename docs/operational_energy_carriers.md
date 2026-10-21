# Energy carriers, the systems, and what each must account for

Decisions taken 2026-10-21, after a test building reported two different
operational carbon figures at the same time.

## What went wrong

A building's page headline read **588.0 kgCO2eq/m2 over 50 years**. Its
Systems tab read **1,494.30 kgCO2eq/m2/yr**. Both were correct arithmetic:

| Shown | Source | Calculation |
|---|---|---|
| 588.0 /m2 over 50 yr | energy **carriers** | 48,000 x 0.588 x 50 / 2,400 |
| 1,494.30 /m2/yr | energy **summary** | 6,099,192 x 0.588 / 2,400 |

Two independent data sources, different time bases, and nothing on the page
said so. The carriers held 48,000 kWh because that is what the imported file
stated; the systems modelled 4.6 million.

## What the carriers must now account for

`EnergySummary.entered_systems_kwh` - and **both** checks use it, the import's
and the data-entry page's. It is:

- the four measured systems (cooling, ventilation, lighting, hot water)
- plus lift, when its figure is real rather than the 7.5% estimate
- plus plug load, when it was **metered**

Nothing BEAT assumes is in it. A plug load that is a percentage, a default or
a difference stays out: asking a bill to match one would make the assumption
the thing being tested.

Before this, the page compared against `total_kwh` and the import against the
entered systems. On the test building those were 432,432 and 326,364 - a gap
of 106,068 kWh that was entirely a 7.5% lift guess and a 25% plug guess. The
carriers could not satisfy both, and whichever they matched, the other screen
called them wrong.

**Entering a real lift or plug figure moves it into the target.** That is the
intended way to make the target larger, and it is tested, because it changes
which files import.

## The rules

| | |
|---|---|
| Tolerance | 5%, matching the carriers-against-bill check in `views/building/building.py` |
| Import | **refuses** outside tolerance, naming both totals and the per-system breakdown |
| Data entry | **shows** the gap, does not block - entry is iterative and the total is only right after the last carrier |
| No carriers at all | allowed; a modelled building has no bills and its carbon comes from the systems |
| Carriers not in kWh | check skipped, and said so in the log - a calorific conversion invented to make a comparison pass is exactly the guess this importer refuses elsewhere |

## How strict this is, measured

In the **developer** database, of 216 buildings holding kWh carriers:

| | count |
|---|---|
| agree within 5% | 69 |
| carriers short of systems | 64 |
| carriers over systems | 1 |
| no modelled systems to compare | 82 |

**65 of the 134 comparable buildings would be refused** if re-imported today.
Existing buildings are untouched - the check runs at import only - but
carriers and systems routinely disagree in real data, including the Cambodia
250-building set, where operational energy came from a master file while the
systems were modelled separately. Confirmed as intended: a building whose bill
and systems disagree by more than 5% is reporting two different carbon figures,
which is the thing being stopped.

Production is a separate database and was not queried.

## Still open: should carriers define the plug load?

Not built, and it is the more correct model.

Today the plug load is **25% of the four systems** unless someone enters a
figure. On the test building that was 81,591 kWh - 19% of the building's
energy, assumed rather than measured. When a user supplies carriers covering
the whole building, the plug load could be derived as
`carriers - modelled systems`, so a measurement replaces the guess instead of
sitting beside it.

Deliberately deferred: it moves the operational carbon of **every existing
building that has carriers**, and that is production data. It needs its own
before-and-after count and its own decision.

If it is taken up:

1. Decide what happens when carriers come in BELOW the modelled systems. The
   agreed answer for the import is to refuse and name the systems that exceed
   the bill, which the message already does. A derivation would need the same
   rule or it would produce a negative plug load.
2. Decide whether a 25% default should remain for buildings with no carriers.
3. Count the affected production buildings and the direction each moves before
   changing anything.
