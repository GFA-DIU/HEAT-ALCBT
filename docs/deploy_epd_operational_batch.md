# Deployment runbook — EPD catalogue + operational carbon batch

For the work on `rohit-qa` in PR #593 (commits `0c36ccf`..`546c612`).

> **Merging this PR is a release.** `qa` is the live tool at
> beat-alcbt.gggi.org. There is no staging step after it. Treat the merge
> itself as the deploy button, not as a review gate.

Everything below is idempotent and every data command takes `--dry-run`.
Migrations run automatically — `Procfile` has
`release: python manage.py migrate --noinput`.

---

## 0. Before you touch anything

**Take a backup and confirm it restores.** Supabase dashboard → manual backup
or PITR snapshot, or:

```bash
pg_dump "$SUPABASE_DATABASE_URL" -Fc -f prod_backup_$(date +%Y%m%d_%H%M).dump
```

Do not continue without one. Nothing else in this runbook is irreversible, but
this is the only thing that makes that true.

**Know your app name:**

```bash
heroku apps
heroku info --app <app>        # confirm it serves beat-alcbt.gggi.org
```

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
| GCCA labels | Scale corrected to AA–F. Two EPDs lose a "G" that the scheme does not define. |

---

## 2. Merge and deploy

```bash
git checkout qa && git pull
git merge --no-ff rohit-qa
git push origin qa
```

Heroku deploys and runs migrations `0056`–`0060` in the release phase. Watch it:

```bash
heroku logs --tail --app <app>
```

Confirm the release phase succeeded before step 3. If it fails, the release is
rejected and the old code keeps serving — that is the behaviour you want.

```bash
heroku run python manage.py showmigrations pages --app <app> | tail -8
# 0056 … 0060 should all read [X]
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
| `apply_gcca_concrete_labels` | ~294 rated, 2 stale labels removed |

If a dry run reports something materially different from this, **stop** and
work out why before running it for real.

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
GCCA labels        294   bands B 3, C 196, D 22, E 32, F 41
any G labels         0
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

**Schema needs reverting.** The four migrations only add nullable columns and
choice-list entries:

```bash
heroku run python manage.py migrate pages 0055 --app <app>
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
