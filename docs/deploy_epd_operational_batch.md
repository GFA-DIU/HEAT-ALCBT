# Deployment runbook - EPD catalogue + operational carbon batch

> **This release was executed on 12 Oct 2026 (v170).** The commit counts and
> migration numbers below describe that release and are now historic: `qa` has
> been at **0060** since, and the six data commands have all been run. Do not
> re-run them expecting work to be left; they are idempotent but they are done.
>
> **Section 0 is not historic.** The backup procedure, the Supabase-not-Heroku
> point and the corrupt-dump trap apply to every release, and the next one is
> described in [`docs/CODEX_HANDOVER.md`](CODEX_HANDOVER.md).


For PR #593. **This is wider than it looks.** `qa` sits at migration
`0051`; `rohit-qa` carries **36 commits and nine migrations** (0052–0060),
including work from earlier sessions — the A4/A5 scope, the lighting space
types and the per-country EPD uniqueness key — not only the EPD catalogue
and operational carbon batch.

> **Merging this PR is a release.** `qa` is the live tool at
> beat-alcbt.gggi.org. There is no staging step after it. Treat the merge
> itself as the deploy button, not as a review gate.

Everything below is idempotent and every data command takes `--dry-run`.
Migrations run automatically — `Procfile` has
`release: python manage.py migrate --noinput`.

---

## 0. Before you touch anything

**Take the backup in Supabase, not Heroku.**

Django reads `SUPABASE_DATABASE_URL` (`django_project/settings.py:157`), so the
real data is in Supabase — `aws-0-eu-west-1.pooler.supabase.com`. The app also
has a `heroku-postgresql` addon attached, which sets `DATABASE_URL` and is
**unused**. `heroku pg:backups:capture` would back that empty database up and
give you false confidence.

Supabase dashboard → the project → **Database → Backups** → take a manual
backup, or note the PITR restore point. Confirm it exists before merging.

Or by hand. **Do not pipe `pg_dump` out of `heroku run`** — the dump arrives
truncated and `pg_restore --list` reports a corrupt TOC. Encode it in transit:

```bash
heroku run --app beat-qa --no-tty -- \
    bash -c 'pg_dump "$SUPABASE_DATABASE_URL" -Fc --no-owner --no-acl | base64 -w0' \
  2>/dev/null | tr -d '\r\n ' | grep -oE '[A-Za-z0-9+/=]{500,}' > dump.b64
base64 -d dump.b64 > beat_backup_$(date +%Y%m%d_%H%M).dump
```

**Then verify it, every time.** A file that exists is not a backup:

```bash
docker exec -i heat-alcbt-db-1 sh -c 'cat > /tmp/v.dump' < beat_backup_*.dump
docker exec heat-alcbt-db-1 sh -c 'pg_restore --list /tmp/v.dump' | grep -c 'TABLE DATA'
```

Expect **94**. Zero, or `entry ID ... out of range -- perhaps a corrupt TOC`,
means the transfer failed — take it again, do not merge.

Stronger still, restore into a scratch database and count rows against the
pre-flight snapshot. Three `supabase_vault` errors are expected and harmless:
that extension does not exist outside Supabase and holds no application data.

Two traps that cost an hour:

- `ls -l | awk '{print $5}'` reports a **constant 197121** under this Git Bash
  whatever the file's real size. Size files with `wc -c`.
- Git Bash rewrites container paths, so `docker cp ... :/tmp/x` lands at
  `C:\tmp\x`. Pipe through `docker exec -i ... sh -c 'cat > /tmp/x'` instead.

The dump is about **4.4 MB**, not 43 MB. 43 MB is the database's on-disk size
including indexes; the custom format is compressed and carries no indexes.

Do not continue without one. Nothing else in this runbook is irreversible, but
this is the only thing that makes that true.

**Take a snapshot you can compare against afterwards.** Read-only, writes
nothing:

```bash
heroku run python manage.py preflight_deploy_check --app <app> | tee before.txt
```

Run it again after the deploy and diff the two. If a number moves that this
runbook did not say would move, stop and find out why.

It also warns about any label outside the published AA–G scale, which would
render a broken image until `apply_gcca_concrete_labels --overwrite` has run.

**The app is `beat-qa`** (eu, one Eco web dyno). Confirmed as the live tool:
`heroku domains --app beat-qa` lists `beat-alcbt.gggi.org`.

**Expect a short outage.** Preboot is off and there is a single web dyno, so the
release restarts it — roughly 10–30 seconds of downtime.

**Two commits that are not yours go live with this.** The current release is
`v169 = c43eb06a` from 02 August; `qa` has since gained PR #592's BOQ classifier
keyword fallback, merged but never released. It is covered by the test run, but
tell its author before you ship it.

No ECO Platform token is needed for this batch — the 250 EPD values are
committed at `pages/data/environdec_epds.csv`.

---

## 1. What real users will see change

Be ready to explain these, because they are visible immediately:

| Change | Effect |
|---|---|
| Cassette ACs re-attributed | **66 buildings** change their cooling/ventilation split. **No building total changes** — verified across all 267 energy summaries. |
| Plug loads count toward the total | Buildings with an estimated plug load show a **higher** total annual energy. |
| Refrigerant leakage in the baseline | Operational carbon baseline rises **0.1–3.4 kgCO₂eq/m²/yr** on cooled buildings; reduction percentages move ~1 point. |
| Savings tab no longer claims 100% | Buildings whose energy is mostly plug load previously showed a 100% reduction. They now show the honest figure, often 0%. |
| EPD names | The picker shows a composed label (material · product · maker). The original title is on hover and in `source_name`. |
| 250 new EPDs | Catalogue grows; existing selections are untouched. |
| GCCA labels | The missing **AA** near-zero band is added. G is unchanged — GCCA defines it as the open-ended band above F. |

---

## 1.5 Post-deploy walkthrough — what to click

Numbers first, from the pre-flight diff:

| Check | Expect |
|---|---|
| EPDs total | **+250** |
| GCCA labels | every score inside **AA–G**; the pre-flight warns on any outside |
| EPDs failing `get_gwp_impact_sum` | **0** |
| Cassette records | unchanged count; they simply report as cooling now |

Then four screens, each chosen because this batch changes what a user sees:

1. **Material picker** — search `Saint-Gobain`. Returned **0** before this release,
   about **35** after. Also try `SCG`, `CPAC`, `Cylence`.
2. **Systems step**, on a building with a cassette AC — cooling and ventilation
   figures move between the two lines. **The building total must not change.**
3. **Savings tab → Operational Carbon Savings** — on a plug-load-only building the
   headline must *not* read 100%. Flip a measure toggle: the headline, the
   percentage and the Baseline/Optimised pair should all move together.
4. **Cooling form** — open the COP / EER / ISEER dropdown: it must be opaque, not
   see-through over the field beneath. Hover any ⓘ: every one of the 72 icons now
   has a tip.

If (2) changes a building total, stop and restore the backup — that is the one
outcome this release is not supposed to produce.

## 2. Merge and deploy

```bash
git checkout qa && git pull
git merge --no-ff rohit-qa
git push origin qa
```

Heroku deploys and runs migrations `0052`–`0060` in the release phase. Watch it:

```bash
heroku logs --tail --app <app>
```

Confirm the release phase succeeded before step 3. If it fails, the release is
rejected and the old code keeps serving — that is the behaviour you want.

```bash
heroku run python manage.py showmigrations pages --app <app> | tail -8
# 0052 … 0060 should all read [X]
```

---

## 3. Run the data commands, in this order

Each one first with `--dry-run`. Read the output. Then run it for real.

```bash
# 1. fill the new nomenclature fields for existing EPDs
heroku run python manage.py backfill_epd_nomenclature --dry-run --app <app>
heroku run python manage.py backfill_epd_nomenclature --app <app>

# 2. repair 399 dead source links
#    needs outbound network from the dyno; add --no-verify if blocked
heroku run python manage.py fix_epd_source_urls --dry-run --app <app>
heroku run python manage.py fix_epd_source_urls --app <app>

# 3. import the 250 verified environdec EPDs
heroku run python manage.py import_environdec_epds --dry-run --app <app>
heroku run python manage.py import_environdec_epds --app <app>

# 4. re-rate concrete on the corrected AA–F scale
heroku run python manage.py apply_gcca_concrete_labels --overwrite --dry-run --app <app>
heroku run python manage.py apply_gcca_concrete_labels --overwrite --app <app>
```

### What each dry run should say

| Command | Expect |
|---|---|
| `backfill_epd_nomenclature` | ~5,460 updated; ~11 left blank and listed |
| `fix_epd_source_urls` | 399 URLs, all verified 200, 0 skipped |
| `import_environdec_epds` | 250 created (first run), 12 rejected |
| `apply_gcca_concrete_labels` | ~296 rated, 0 stale labels removed |

If a dry run reports something materially different from this, **stop** and
work out why before running it for real.

### Two more commands the first pass missed

These were already deployed and had simply never been run on production. Both
are idempotent and both take `--dry-run`:

```bash
# 5. the 6 official Cambodian cement EPDs (KCC Kampot + Chip Mong INSEE)
heroku run python manage.py load_cambodia_official_epds --dry-run --app <app>
heroku run python manage.py load_cambodia_official_epds --app <app>

# 6. strip the pre-0055 workaround whitespace from EPD names
heroku run python manage.py normalise_epd_names --dry-run --app <app>
heroku run python manage.py normalise_epd_names --app <app>
```

| Command | Expect |
|---|---|
| `load_cambodia_official_epds` | 6 created, 1 renamed; Cambodia goes 1 official -> 7 |
| `normalise_epd_names` | 140 trimmed + 1 renamed, 0 collisions |

`normalise_epd_names` also resolves India's two identically-named
`Cement mortar` records - one official per kg, one generic per m3, 3,000x
apart - by qualifying the first. Both rename steps keep the record id, so
materials pointing at them are unaffected.

**How to tell whether a data command still needs running.** Deploying code
and loading data are separate acts: a migration changes the shape of the
database and never fills it. Compare the two catalogues by (country, name)
rather than by counts, and do **not** `.strip()` the names on the way out -
that masks exactly what `normalise_epd_names` fixes, which is how 141 untidy
names first went unnoticed here.

Three German EPD names contain a literal newline from their source data.
`normalise_epd_names` trims spaces, not line breaks, so they are left as they
are in both databases.

---

## 4. Verify

```bash
heroku run python manage.py shell --app <app> -c "
from pages.models.epd import EPD, EPDLabel
from django.db.models import Count
A=['India','Thailand','Vietnam','Indonesia','Cambodia']
print('EPDs total       ', EPD.objects.count())
print('EPDs ALCBT       ', EPD.objects.filter(country__name__in=A).count())
print('environdec       ', EPD.objects.filter(source__icontains='environdec.com/library').count())
print('GCCA labels      ', EPDLabel.objects.count())
print('bands            ', dict(EPDLabel.objects.values_list('score').annotate(n=Count('id'))))
print('any G labels     ', EPDLabel.objects.filter(score='G').count(), '(must be 0)')
bad=[e for e in EPD.objects.all() if e.declared_amount and e.get_gwp_impact_sum('a1a3') is None]
print('EPDs failing GWP ', len(bad), '(must be 0)')
"
```

Local figures for comparison — production will differ because its catalogue
starts from a different place, but the shape should match:

```
EPDs total        5710
EPDs ALCBT        2809
environdec         298
GCCA labels        296   bands B 3, C 196, D 22, E 32, F 41, G 2
EPDs failing GWP     0
```

Then open the live site and check:

- a building's **Systems** step — cooling and ventilation figures
- the **Savings** tab, Operational — headline is not 100% on a plug-load-only
  building, and the measure toggles move the headline
- the material picker — search `Saint-Gobain` (0 results before this release,
  ~35 after)

---

## 5. If it goes wrong

**Release phase failed.** Heroku rejects the release and keeps serving the old
code. Fix forward on `rohit-qa`, or:

```bash
heroku releases --app <app>
heroku releases:rollback vNNN --app <app>
```

**Schema needs reverting.** `qa` is currently at `0051`, so this merge brings **nine** migrations,
0052 through 0060. They add nullable columns, choice-list entries and a
few new tables:

```bash
heroku run python manage.py migrate pages 0051 --app <app>
```

**A data command did the wrong thing.** All four are idempotent, so re-running
after a code fix is safe. The imported EPDs are identifiable:

```sql
SELECT count(*) FROM pages_epd WHERE source LIKE '%environdec.com/library%';
```

**Something worse.** Restore the backup from step 0.

---

## 6. Known gaps going in

None of these are introduced by this release; they are pre-existing and
documented so nobody is surprised:

- **5 test failures** predate this branch —
  `test_operational_carbon_by_system` ×4 and `test_operational_savings_measures`
  ×1. They assert label lists that changed when plug load entered the breakdown.
- **9 EPDs have `declared_amount = 0`.** They return `None` rather than raising
  now, so selecting one no longer 500s. None is used by a building.
- **Production secrets pasted in chat have not been rotated.** Unrelated to this
  release, still outstanding: `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`
  (⚠️ re-keys encrypted fields), Supabase password, `REPORT_API_KEY`, Mailgun,
  Honeybadger, New Relic, Papertrail.
- **34 buildings hold stale `EnergySummary` values** from earlier fixes. A
  `recalculate()` pass would correct them; not required for this release.
