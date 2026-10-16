# Start here

You are picking up BEAT from a Claude session that ran out of credits. This
file assumes you remember nothing. Read it top to bottom before touching
anything; it takes about ten minutes and will save you a day.

Three files, three jobs:

| File | What it is |
|---|---|
| `AGENTS.md` | **The rules.** Ten of them, each written after something broke. Read it. |
| `docs/AGENT_HANDOVER.md` | **The state.** Everything in flight, every open decision, every known-but-accepted flaw. |
| **this file** | **The next two tasks**, and what you are and are not allowed to do. |

---

## The one thing that will hurt someone if you get it wrong

**`qa` is production.** It is the live tool at beat-alcbt.gggi.org, used by
real people in five countries. There is no staging environment behind it.

**Merging `rohit-qa` into `qa` does NOT deploy.** This file said the opposite
until 16.10.2026, and that cost a release: PR #595 was merged, everyone
believed it had shipped, and production carried on serving twelve-day-old code.
The app has no GitHub integration (the Heroku link returns `not_found`) and no
Actions workflow. A deploy is one manual command:

```bash
git push heroku origin/qa:refs/heads/main
```

`Procfile` carries `release: python manage.py migrate --noinput`, so migrations
run automatically **on that push** — not on the merge. Preboot is off, so every
deploy is 10 to 30 seconds of downtime.

**`heroku releases --app beat-qa` is the only proof.** A new version number
means it shipped; an unchanged one means it did not, however clean the merge
looked.

### Your authority, as set by Rohit on 15 Oct 2026

- **`rohit-qa`: yours.** Commit and push freely. Never merge to `qa`.
- **Production: prepare only.** Do every check, write the result down, then
  **stop** and hand Rohit the exact commands. He presses the button.
- **Production database: read-only.** Every single time, unless he says
  otherwise in that same message.
- **Never print, paste or commit a secret.** Mask connection strings as
  `postgres://***:***@host`.

This is not caution for its own sake. On 12 Oct the first production deploy
was **rejected at build time** by a `NameError` that no local run and no test
could see, and the first database backup taken that day was **corrupt** while
reporting a plausible file size. Both were caught only because each step was
verified by hand.

---

## Task 1 - prepare the release of 11 commits

`rohit-qa` is **11 commits and 4 migrations ahead of `qa`**: 50 files, about
4,700 lines. None of it has ever reached a user.

```
4fd43fe fix(ventilation): ask only for what is used, and in the unit it is sold in
aa8c1f2 feat(cooling): the boundary and fan-link UI, on one form, in one line
ef2db10 feat(cooling): link indoor fans to their parent, and say what a figure covers
061ef62 feat: three-stage whole-life donut, A4-A5 by material, and cooling fixes
55d8e87 fix(a5): make the bin work, drop the /yr label, and clarify the upfront table
1623616 feat(a5): add construction site energy (A5.2)
7889bcc docs: record the TGO comparison and the rounding issue, change no code
c880931 fix(a4): source India from SFC, repair the panel, drop the override boxes
e636495 feat(a4): add the Upfront Carbon tab
0885f7c fix(a4): model a journey as legs instead of one blended factor
1af4c9b docs(runbook): add the two data commands the first pass missed
```

**The runbooks are `docs/production_deployment_runbook.md` and
`docs/deploy_epd_operational_batch.md`. Read section 0 of the latter before
anything else** - it is where the corrupt-backup trap is written down. Do not
re-derive the backup procedure; it is already correct there, including the
base64 trick that works and the `heroku run | pg_dump` pipe that silently does
not.

### What the four migrations do

`qa` sits at **0060**. These are pending:

| Migration | Change | Risk |
|---|---|---|
| `0061_constructionproduct` | new table for A5.2 construction site energy | **none** - creates a table, touches no existing row |
| `0062_..._efficiency_metric` | widens the AC efficiency choice list to six metrics | **none** - a `choices` change; all 167 records are on `cop` |
| `0063_..._energy_boundary_and_more` | adds `energy_boundary` to AC and chiller, `cooling_parent_ac` / `cooling_parent_chiller` to ventilation | **none by default** - every existing row defaults to `unknown` / unlinked, which reproduces current behaviour exactly |
| `0064_ventilation_optional_...` | `baseline_efficiency_w_cmh` becomes nullable; `total_power_input_kw` becomes `numeric(12,4)` | **none** - dropping NOT NULL changes no data, and widening a numeric scale is lossless in PostgreSQL |

**No stored carbon figure should move.** That is the claim to test, not to
assume. Local counts for comparison (production will differ; the *shape*
should not):

```
ventilation rows      152     ventilation efficiency set   152
  under 1 kW           84     AC cooling records           167
chiller records         4     buildings                   1559
```

### Pre-flight, in order

Do not skip a step because the last one passed. Write down each number.

1. **Backup.** `docs/deploy_epd_operational_batch.md` section 0. The real data
   is in **Supabase**, not the attached heroku-postgresql addon, which is empty
   and unused. `heroku pg:backups:capture` backs up the wrong database and
   gives false confidence.
2. **Verify the backup.** A file that exists is not a backup. Restore it into a
   scratch database and compare row counts. Section 0 has the commands.
3. **Full suite, locally.** `.venv/Scripts/python.exe -m pytest -q`. About
   8 minutes. The last run, on `4fd43fe`, was **666 passed, 0 failed**.
   Anything less than 666 passing means something regressed; find out what
   before going further.
4. **Production settings check.** `pages/tests/test_production_settings.py`
   runs `manage.py check` and `collectstatic` in a subprocess with `DYNO` set.
   This test exists because the 12 Oct build failed on a `NameError` that only
   appears on a dyno. Run it and watch it pass.
5. **Count the blast radius on production, read-only.** Record these before:

   ```sql
   select count(*), count(baseline_efficiency_w_cmh),
          count(*) filter (where total_power_input_kw < 1),
          sum(total_power_input_kw)
     from pages_ventilationsystem;
   select count(*) from pages_coolingsystemairconditioner;
   select count(*) from pages_coolingsystemchiller;
   ```

6. **Write the pre-flight up and stop.** Give Rohit the backup location, the
   suite result, the before-counts, and **both** commands — the merge *and*
   the `git push heroku` that actually ships it. Do not run either.

   Do not report a release as done because a PR merged. Read
   `heroku releases --app beat-qa` and quote the version number.

### Immediately after the deploy, once he has pressed it

Re-run the step 5 queries. Every count must be identical and
`sum(total_power_input_kw)` must match to four decimal places. If a count
moved, say so immediately. Do not explain it away.

### One thing to tell him, not to fix

Two ventilation records lost their power to the old two-decimal column and
report less energy than they should:

```
record 267  building "1st project"  7 fans, 300 CMH each  ->  0.00 kW, 0 kWh/yr
record 1    building "KBC"          2 FCUs                ->  0.00 kW
```

The column is wide enough now, but **the numbers people originally typed are
gone**. Do not reconstruct them from the stored airflow and efficiency. That
would mean applying the AHU formula (`airflow x efficiency x units / 1000`) to
equipment it was never meant for, and it would produce a plausible figure that
nobody could tell was invented. Those two owners re-enter the nameplate watts,
or the records stay as they are.

---

## Task 2 - rotate the production secrets

Outstanding since before the 12 Oct deploy. Rohit pasted Heroku config vars
into a chat window, so treat all of these as compromised:

```
DJANGO_SECRET_KEY      FIELD_ENCRYPTION_KEY    Supabase password
REPORT_API_KEY         Mailgun credentials     Honeybadger
New Relic              Papertrail
```

He chose "deploy first, rotate after" on 12 Oct. The deploy happened. This is
now the oldest open item in the repository.

**`FIELD_ENCRYPTION_KEY` is the hard one, and it gets harder every week.** It
encrypts stored fields, user email among them. Rotating it is not a config
change; it is a re-key, which means reading every encrypted row with the old
key and writing it back with the new one, inside a migration or a management
command, with a verified backup taken first and a tested rollback. Attempting
it casually will lock people out of their own data.

The others are ordinary `heroku config:set` rotations, but each has a blast
radius worth checking first - `REPORT_API_KEY` is used by an external caller,
and rotating it without warning breaks whatever is calling.

**Scope this one before building it.** Write the plan, name what breaks, get
Rohit's agreement. The re-key in particular is exactly the kind of change
`AGENTS.md` rule 7 is about: write it up and stop.

---

## What was just finished, so you do not undo it

All on `rohit-qa`, all tested, none deployed.

### A4 transport and A5 construction carbon

A4 is modelled as **one leg per transport mode**, not one blended factor. The
old model collapsed each scenario into a single distance and a weighted-mean
emission factor, so India showed 0.070 kg/t-km over 50 km and 0.01286 over
3,150 km: the factor appeared to *fall* as distance rose, because sea freight
is roughly seven times cleaner per tonne-km than road. The arithmetic was
right and the presentation was indefensible. **Nothing reports a blended
factor now, and a test enforces it.**

India's road and rail factors come from **Smart Freight Centre / TCI-IIMB,
ISO 14083**, published as kg CO2e per tonne-km well-to-wheel with measured
empty running and utilisation. Local journeys use HCV-1 (0.0902), national and
inland use HCV-2 (0.0823), rail is 0.0106. Sea stays GLEC 0.010 everywhere
because SFC covers road and rail only. Other countries use GLEC v3 proxies and
**say so in the panel**.

A5.2 is construction site energy. `ConstructionProduct` is a third
`BaseProduct` subclass alongside `StructuralProduct` and `OperationalProduct`.
Fuel conversion uses **IPCC 2006 Vol 2 Ch 1 Table 1.2 net calorific values**;
the **densities are typical trade values, not IPCC, and the screen says so**.
It refuses rather than guesses: LPG entered in litres returns "enter it in kg"
instead of inventing a density. Enter nothing and it reports zero **and states
that the total is understated**. A5.1 demolition and A5.4 worker transport are
not modelled, and the UI says that too.

### Cooling

Three verified bugs, each fixed and each measured first:

- **The chiller import multiplied plant energy by the machine count** and the
  manual form did not. A 15-chiller plant imported at 945,000 kWh/yr against
  63,000 entered by hand. All four stored records were wrong by exactly their
  own chiller count. `manage.py recalc_chiller_energy` repairs them, is
  idempotent, and takes `--dry-run`.
- **ISEER was divided by 3.412 on save** but not in the on-screen calculation,
  so 5.30 entered became 1.55 stored and reopened 3.4x too high. No record was
  affected; all 167 are on `cop`.
- **`toFixed(2)` turned a 63 W fan coil into 0.06 kW**, reporting 120 kWh a
  year instead of 126.

`EnergyBoundary` (`unknown` / `complete_system` / `equipment_only`) now records
what a cooling figure covers, and a fan coil can name its parent. **A fan is
excluded from the ventilation sum only when it is linked AND the parent says
complete system.** The base rule, written in
`docs/operational_carbon_methodology.md` and pinned by four tests, is:

> BEAT adds every record once and deducts nothing. It does **not** detect
> anything on its own.

An unlinked fan beside a complete-system cooling record is still double
counted. That is deliberate and documented. Do not make it clever.

### Ventilation (15 Oct, the last thing done)

Airflow and baseline efficiency were **required on the FCU, cassette and fan
forms and read by none of them**; those forms compute energy from
`power x units x hours`. 149 of 152 stored rows are on those three forms, so
almost every value in that column was invented to satisfy a validator. Both
fields are optional there now and labelled "Reference only" on screen.

**AHU and DOAS still require both, and a test holds that line.** There, power
genuinely *is* `airflow x efficiency x units / 1000`. Do not tidy that into
consistency.

`total_power_input_kw` went from `numeric(10,2)` to `numeric(12,4)`, and the
three direct-entry forms now offer **W or kW, defaulting to W**. That also
closed a divergence: the import template has always stated that column in
watts while the form asked for kilowatts.

---

## Running it locally

```bash
.venv/Scripts/python.exe manage.py runserver 8000
.venv/Scripts/python.exe -m pytest -q          # ~8 min, 666 tests
.venv/Scripts/python.exe manage.py check       # fast
```

Django 5.1, Python 3.11, local Postgres in Docker container
`heat-alcbt-db-1`. Production is Heroku app **`beat-qa`** (eu, one Eco web
dyno) reading **Supabase** via `SUPABASE_DATABASE_URL`
(`django_project/settings.py:157`).

**Templates live in `/templates`, not `pages/templates`.** More than one agent
has concluded a feature was missing by searching the wrong directory.

Buildings to test against. Rohit owns these; a 404 saying "No Building matches
the given query" means it belongs to someone else, because the view filters on
`created_by=request.user`:

```
Charts    /building/fc79bbc6-d6e6-4cc7-bc06-bb7675faa7ca/   Brown Roastery Khalandale
Chiller   /building/af45d5c3-2aeb-4cc4-98aa-caf260f1bc26/   Test Kerala, 15 chillers
Cooling   /building/cefd2bfc-0d89-4826-962b-a305fc6f2516/   #78 Borey Chip Mong
```

### Traps that have cost real time

- `ls -l | awk '{print $5}'` returns a **constant 197121** under this Git Bash
  whatever the file. Size files with `wc -c`. This is how a corrupt backup
  passed a size check.
- Git Bash rewrites container paths: `docker cp x :/tmp/x` lands at
  `C:\tmp\x`. Pipe instead:
  `docker exec -i heat-alcbt-db-1 sh -c 'cat > /tmp/x' < x`.
- Django `{# #}` comments **only reach the end of their line**. A multi-line
  block renders onto the page as text. This shipped twice;
  `test_template_comments.py` fails on it now.
- `data-icon` names are not validated. Ten did not exist and rendered as empty
  boxes. The valid set is `static/js/icons.js`.
- `.claude/` and `HANDOVER.md` are gitignored. That is why the state file is
  `docs/AGENT_HANDOVER.md` and not `HANDOVER.md`.

---

## Decisions that are not yours to make

`docs/AGENT_HANDOVER.md` has the full table. These are waiting on **GT**, not
on an agent:

- **A4 rail share** (India 60%, Thailand 30%, Vietnam 20%, Indonesia 10%,
  Cambodia 0%) was **invented by an agent** and is flagged as such in the code,
  the docs and the on-screen output. India's national haul reads 11.78
  kgCO2e/t with the split and 24.69 without. It needs real modal-split data.
- **The A4 sea leg is a flat 3,000 km** regardless of origin. Chinese steel
  into Vietnam and Brazilian steel into India get the same distance.
- **Refrigerant GWPs are IPCC AR4 while TGO uses AR5.** 91 rows; R-410A would
  go 2088 to 1923.5 and move F-gas on every building.
- **`get_gwp_impact_sum` rounds every impact to 2 dp.** 415 impacts round to
  zero, 1,510 are wrong by 1% or more, India's sand and aggregate is overstated
  11% across 1,236 material rows, and Thailand's grid reads 0.470 when 0.475 is
  stored. **A fix was written and Rohit said "revert it, change nothing."** It
  needs a before/after across all buildings first. Do not fix it on your own
  initiative; the exact change required is recorded in the handover.
- **Part-load factor on AC** - rated capacity x full hours / COP bills every
  hour at 100% load.
- **VSD -20% double count** - a chiller whose entered efficiency already
  reflects a VSD gets the saving applied again.
- **106 cassette rows sit under ventilation.** Rohit said "check later".

There is also a loose end nobody has decided: **`main` is 646 commits behind
`qa` and carries 14 commits `qa` has never had** - a CSV export for buildings,
template management CRUD, an assembly list view, a clear-filters button. Real
feature work that was never released. Flagged, not acted on.

---

## How to work here

The full list is `AGENTS.md`. The four that get broken most often:

1. **Verify the claim in the code before acting on it.** A review that is right
   about one thing is often wrong about the next.
2. **Count the records before and after.** "It should be fine" is not a
   measurement.
3. **An unsourced number must say it is unsourced** - in the code, in the UI,
   and in the docs.
4. **Build what was asked. If it needs to be bigger, write it up and stop.**

That last one has history. In October another agent was asked to *scope* the
cooling redesign and built it instead, in the same working tree, while a second
agent was editing the same files. It removed a fix it had not written in order
to make its own tests pass, left the importer and the form disagreeing again,
and created two test buildings in the development database that then blocked a
migration rollback until someone found and deleted them. Its **design was
sound** and close to what the scope document already said. The damage was
entirely in building something deferred, in a shared tree, over someone else's
work.

So: one agent per area at a time. Do not create test data in the developer's
database. Do not edit another agent's tests.

**And before you write a test, check that it can fail.** `git stash`, run it
against the unfixed code, `git stash pop`. A test that passes against the bug
is worse than no test, because it certifies the bug. Of the 28 tests added on
15 Oct, 23 were confirmed to fail against the pre-change code; the five that
did not are the ones asserting that AHU and DOAS kept their required fields,
which was correct and unchanged.
