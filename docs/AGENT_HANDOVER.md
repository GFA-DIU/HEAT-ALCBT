# Handover — what is in flight

Read `AGENTS.md` first: it has the rules for working here. This file is the
*state* — what is done, what is deliberately not done, and what is waiting on a
human decision. It changes weekly; AGENTS.md does not.

**Last updated 2026-10-14. Branch `rohit-qa`. Nothing below is deployed.**

---

## Where things stand

```
rohit-qa    8+ commits ahead of qa, none deployed
qa          v170 — this IS production, beat-alcbt.gggi.org
suite       619 passing before the current cooling-boundary work
```

Production last changed on 12 Oct: the EPD catalogue batch (5,453 → 5,709 EPDs,
296 GCCA labels, 393 repaired source links). Everything since is local.

## If you are picking this up mid-task

1. `git log --oneline -12` — the commit messages carry the reasoning
2. `.venv/Scripts/python.exe -m pytest -q` — ~10 min, must be green before you
   change anything, so you know what you broke
3. Read the three methodology docs below before touching a carbon number

| Document | Covers |
|---|---|
| `docs/operational_carbon_methodology.md` | B6, cooling, the CDU/FCU boundary |
| `docs/a4_a5_upfront_carbon_scope.md` | A4 transport, A5.2 site energy, A5.3 waste |
| `docs/cooling_system_redesign_scope.md` | the larger cooling redesign, **not built** |
| `docs/HANDOVER_epd_operational.md` | EPD catalogue work, older |

---

## Just finished (uncommitted at time of writing)

**Cooling energy boundary.** `EnergyBoundary` on AC and chiller records says
what the entered electricity already covers; `cooling_parent_ac` /
`cooling_parent_chiller` link a fan coil or cassette to its parent. A fan is
excluded from the ventilation sum **only** when it is linked *and* the parent
says "complete system". Migration `0063`.

Everything existing defaults to *not specified* and unlinked, so **no stored
figure moved** — verified on a real building by linking, changing the boundary,
and restoring.

Not built, on purpose: no enforcement of stating coverage, no warning for
unlinked fans beside a complete-system record, no reconnection on clone, no
auxiliary inventory.

## Open decisions — do not guess these

These are methodology calls, not implementation gaps. They need GT.

| Question | Why it matters |
|---|---|
| **A4 rail share** — India 60%, Thailand 30%, Vietnam 20%, Indonesia 10% | invented by an agent. India's national haul reads 11.78 kgCO₂e/t with the split, 24.69 without |
| **A4 sea leg is a flat 3,000 km** | Chinese steel into Vietnam and Brazilian steel into India get the same distance |
| **Refrigerant GWPs are IPCC AR4; TGO uses AR5** | global table, 91 rows. R-410A 2088 → 1923.5 would move F-gas on every building |
| **`get_gwp_impact_sum` rounds to 2 dp** | 415 impacts round to zero, 1,510 wrong by ≥1%. India's Sand and Aggregate overstated 11% across 1,236 rows. A fix was written and reverted — it needs a before/after across all buildings first |
| **Part-load factor on AC** | rated capacity × full hours ÷ COP bills every hour at 100% load |
| **VSD −20% double count** | a chiller whose entered efficiency already reflects a VSD gets the saving again |

## Known but accepted

- **106 cassette rows sit under ventilation.** They report as cooling and
  building totals were verified unchanged. Moving them needs three NOT NULL
  fields the ventilation form never collected. User said "check later".
- **A5.1 demolition and A5.4 worker transport are not modelled.** Stated on
  screen so nobody reads A5 as complete.
- **Three German EPD names contain literal newlines.** Cosmetic, identical in
  both databases.
- **Production secrets pasted in chat have never been rotated.** Outstanding
  since before the 12 Oct deploy. `FIELD_ENCRYPTION_KEY` gets harder with time.

## Next steps, in order

1. Run the suite; commit the boundary work if green
2. Put the boundary field and the fan-parent picker into the two forms' UI —
   the model and the form classes accept them, the templates do not yet show
   them
3. Decide the open questions above with GT before anything ships
4. The deploy runbook is `docs/deploy_epd_operational_batch.md` — **read §0
   before merging anything to `qa`**, it is a release

---

## Traps that have already cost a day each

- **`qa` is production.** Merging deploys to real users at
  beat-alcbt.gggi.org. There is no staging after it.
- **Templates live in `/templates`**, not `pages/templates`. Searching the
  wrong one and concluding a feature is missing led to a third copy of an
  editor that already existed twice.
- **`settings.py` assigns `DEBUG` in both branches** of `if not IS_HEROKU_APP`.
  It used to assign one, so a module-level reference to `DEBUG` raised
  `NameError` **on a dyno only** — invisible to every local run and test, and
  it rejected a production deploy.
- **Manual entry and Excel import compute the same things twice.** They have
  diverged twice; most recently a chiller plant read 15× high on import.
  Change both, in the same commit.
- **Never create test data in the dev database.** Two stray rows once blocked a
  migration rollback until they were found.

## A note on parallel agents

Two agents worked this repository simultaneously on 14 Oct and overwrote each
other: one built a feature the user had explicitly deferred, removed the
other's fixes to make its own tests pass, and edited its tests and docs. Hours
went into unpicking it.

**One agent per area at a time.** If you find work in progress that is not
yours, stop and say so rather than reconciling it yourself.
