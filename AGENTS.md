# Working on BEAT

> **Current state of the work — what is in flight, what is deliberately
> not built, and the decisions waiting on a human — is in
> [`docs/AGENT_HANDOVER.md`](docs/AGENT_HANDOVER.md). Read it before
> starting a task. This file is the rules; that file is the state.**

Rules for any agent working in this repository. They are not style preferences —
each one is here because breaking it produced a wrong carbon number, lost work,
or broke the app.

BEAT reports carbon figures that people put in reports and make decisions with.
A plausible wrong number is worse than an obvious error, because nobody catches
it. Most of what follows is about not producing plausible wrong numbers.

---

## 1. Verify before you act

**Check a claim in the code before fixing it.** Reviews, issue reports and other
agents are often right, but not always, and acting on an unverified claim wastes
the fix and can break something that worked.

> A review reported that a form field was "required but unused". True — the
> formula ignored it. Another claim in the same review was that a bug "remains
> in the reviewed code"; it had been half-fixed, and the half that mattered was
> in a different file. Only reading both code paths showed which.

**Measure the blast radius before and after.** Before changing a calculation,
count the records it affects and record the numbers. Afterwards, prove they
moved the way you predicted.

> A chiller plant read 945,000 kWh/yr. The fix made it 63,000. That is a 15×
> change to a live figure — the only reason it was safe to make was that all
> four affected records were checked first, and each was wrong by exactly its
> own chiller count.

## 2. Never produce an unsourced number silently

If you must choose a value nobody published — a default, a factor, a threshold —
**say so in the code, in the UI, and in the docs**.

```python
HDV_PAYLOAD_TONNES = 16.0   # ⚠️ ASSUMPTION — 12 t gives 0.0614, 25 t gives 0.0295
```

Never present a derived figure as if it came from a source. If a study gives
kg CO₂ per vehicle-km and you need per tonne-km, the division is yours, and the
tonnage you divided by is an assumption that must be visible.

Prefer a sourced value with its provenance recorded over a better-looking value
with none. When only a placeholder exists, **label it a placeholder in the UI**
so nobody treats it as national data.

## 3. One calculation, one implementation

**If the same quantity is computed in two places, they will diverge.** Manual
entry and Excel import are the usual pair.

> A chiller formula existed twice: once in the form's JavaScript, once in the
> importer. The importer multiplied by the machine count; the form did not. Its
> docstring said "mirrors the frontend". It had not for some time, and the same
> building entered two ways gave answers a factor of 15 apart.

If you change one, change the other in the same commit, and add a test that
fails when they drift. The same applies to a value normalised on save but
converted on display: both paths must agree on the rule.

## 4. Don't round in a shared accessor

Round at display. An accessor used by every caller must return the declared
value.

> `round(value, 2)` inside a shared getter zeroed 415 impact rows (0.00223 →
> 0.00) and inflated 1,510 more (0.00505 → 0.01). Sand and aggregate were
> overstated 11% across 1,236 material rows.

> The same mistake in a form: `toFixed(2)` turned a 63 W fan coil into 0.06 kW
> and reported 120 kWh a year instead of 126.

## 5. Refuse rather than guess

When an input cannot be converted or resolved honestly, **return nothing and say
why**. Do not substitute a default and carry on.

```python
if density is None:
    return None, "%s is not sold by volume here - enter it in kg" % carrier
```

A figure that is absent is visible. A figure that is quietly wrong is not.
Likewise, if a feature cannot cover part of its scope, state the gap on screen —
"A5.1 and A5.4 are not included" — rather than letting a partial number look
complete.

## 6. Search the whole repo before building

Templates live in `/templates`, **not** `pages/templates`. Searching the wrong
directory and concluding a feature is missing is easy.

> An editor for a feature already existed in two places. A third was built
> because the search missed both, and all three then had to be reconciled.

Before adding a model, a form or a view: grep for the field names, the URL
names, and the user-facing words in `templates/`, `pages/`, `static/` and
`libs/`.

## 7. Respect the boundaries of your task

**Build what was asked. If a bigger change is needed, write it up and stop.**

> A redesign was deliberately scoped into a document rather than built, because
> it needed a migration over 273 live records and a decision about buildings
> whose reported energy would change. It was then built anyway, applied to the
> developer's database, and had to be unapplied and removed.

Specifically:

- **Do not revert or rewrite another agent's fix** to make your own tests pass.
  If their change conflicts with yours, stop and say so.
- **Do not edit files you did not create** unless the task requires it — and
  never another agent's tests. A test you did not write encodes a decision you
  may not know about.
- **Do not create test data in the developer's database.** Use the test suite,
  fixtures, or in-memory objects. Rows left behind block migrations: two stray
  records once made a rollback impossible until they were found and deleted.
- **Do not implement an option the user explicitly did not choose.** If asked to
  label a factor as an assumption, label it; do not remove it instead.

## 8. Run the suite, and report it honestly

```
.venv/Scripts/python.exe -m pytest -q          # about 10 minutes, ~620 tests
.venv/Scripts/python.exe manage.py check       # fast sanity check
```

Never claim something works without running it. If tests fail, say so with the
output. If you fixed the test rather than the code, say that too — and be sure
it was the test that was wrong.

**A test that cannot fail is worse than no test.** After writing one, verify it
fails against the broken code — `git stash`, run, `git stash pop`.

## 9. Write the reason, not the restatement

Comments and commit messages explain **why**, especially why an obvious
alternative was rejected.

```python
# ISEER does NOT convert. India's BEE defines it as CSTL ÷ CSEC, both in Wh, so
# it is already dimensionless W/W: a 5-star split AC is >= 5.30. Dividing it
# made the unit consume 3.4x too much.
```

Not `# convert the efficiency`.

## 10. Project specifics

| | |
|---|---|
| Branch | work on `rohit-qa`; **never merge to `qa` unless asked** |
| `qa` | this **is** production — beat-alcbt.gggi.org. Merging deploys to real users |
| Production DB | read-only unless explicitly directed |
| Secrets | never print, paste or commit; mask connection strings |
| Python | `.venv/Scripts/python.exe` |
| Database | local Postgres in Docker, container `heat-alcbt-db-1` |
| Templates | `/templates`, not `pages/templates` |
| Migrations | run automatically on deploy via `Procfile` release phase |

### Two local traps

- `ls -l | awk '{print $5}'` returns a **constant** under this Git Bash
  whatever the file. Size files with `wc -c`.
- Git Bash rewrites container paths: `docker cp x :/tmp/x` lands at `C:\tmp\x`.
  Pipe instead: `docker exec -i <container> sh -c 'cat > /tmp/x' < x`.

### Django specifics

- `{# #}` comments **only reach the end of their line**. A multi-line block
  renders onto the page as text. This shipped twice;
  `test_template_comments.py` now fails on it.
- `data-icon` names are not validated. Ten did not exist and rendered as empty
  boxes. The valid set is `static/js/icons.js`.
- The material picker passes a dataclass, not EPD instances. A template field
  that dataclass lacks renders empty rather than raising.
- `settings.py` assigns `DEBUG` in both branches of `if not IS_HEROKU_APP`. It
  used to assign only one, so any module-level reference to `DEBUG` raised
  `NameError` **on a dyno only** — invisible to every local run and every test.

---

## The short version

1. Verify the claim in the code before you act on it.
2. Count what you are about to change, before and after.
3. An unsourced number must say it is unsourced.
4. The same quantity must not be computed in two places.
5. Round at display, never in a shared accessor.
6. Refuse honestly rather than guess silently.
7. Search `/templates` as well as `pages/`.
8. Build what was asked; write up the rest and stop.
9. Don't touch another agent's files, tests or fixes.
10. Run the suite and report what it actually said.
