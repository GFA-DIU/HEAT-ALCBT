# beat-qa Hotfix — `AssemblyCategory.family` migration error

**Symptom (beat-qa, live):**
```
django.db.utils.ProgrammingError: column pages_assemblycategory.family does not exist
```
Every page that queries `AssemblyCategory.family` returns 500.

## Root cause
The `Procfile` had **no release phase**, so Heroku never ran migrations on deploy. qa
shipped code that expects `AssemblyCategory.family` (migration **0047**) while migrations
**0046–0049 were never applied** to the beat-qa database → the column doesn't exist.

An initial manual `migrate` also failed: migration **0046** (taxonomy 19→14) hit a data
guard on a qa-only building using `Bottom Floor Construction / Thin Precast Concrete Deck
and Composite In-situ Slab` (a technique that combo was set to drop). It aborted and rolled
back cleanly (no partial state).

## Fix (already on `rohit-qa`)
- **Procfile:** added `release: python manage.py migrate --noinput` — deploys now auto-run
  migrations (a failed migration safely aborts the release).
- **0046 made data-safe:**
  - the qa "Thin Precast …" material is **remapped** to the cleaned kept technique →
    lands on `Ground Floor / Thin Precast Concrete Deck & Composite In-Situ Slab`
    (technique preserved, not blanked);
  - any *other* retired-technique-with-materials case is repointed to the category's
    "Not specified" join instead of crashing (generic fallback).
- Verified: `manage.py check` clean, no un-generated migrations, migration completes with
  zero classified-material loss (`before == after`).

Commits on `rohit-qa`: `f3e978e` (Procfile), `3cab523` + `dab7fa2` (0046). Part of PR #575.

## Deploy to beat-qa WITHOUT touching the qa branch
Run in the deployment terminal (Heroku CLI + beat-qa access). This deploys the `rohit-qa`
ref directly to the beat-qa app; the `qa` git branch is left alone.

### 1. Back up the DB first (0046 changes taxonomy data)
```bash
heroku config -a beat-qa | grep -i database        # Heroku Postgres vs Supabase?
heroku pg:backups:capture -a beat-qa               # Heroku PG
# or Supabase: dashboard snapshot / pg_dump "<SUPABASE_DATABASE_URL>" -Fc -f beat_qa_backup.dump
```

### 2. Point a Heroku git remote at beat-qa
```bash
git fetch origin
heroku git:remote -a beat-qa -r beatqa
```

### 3. Deploy rohit-qa straight to beat-qa
```bash
git push beatqa origin/rohit-qa:main
```
Heroku builds, then the release phase runs `migrate --noinput`. Watch for a clean migration
(`[taxonomy] classified materials before=N after=N …`) and successful completion. If the
migration fails, the release aborts and beat-qa keeps the old code (safe).

### 4. Fallback if the release phase didn't migrate
```bash
heroku run python manage.py migrate --noinput -a beat-qa
```

### 5. Verify
```bash
heroku run python manage.py showmigrations pages -a beat-qa     # 0045–0049 = [X]
heroku run python manage.py shell -c "from pages.models.assembly import StructuralProduct as S; print('moved:', S.objects.filter(classification__category__name='Ground Floor', classification__technique__name='Thin Precast Concrete Deck & Composite In-Situ Slab').count())" -a beat-qa
heroku logs -a beat-qa --tail
```
Reload the previously-500ing page — the `family` error should be gone.

### 6. Rollback (only if needed)
- Failed migration → auto-rolled back, deploy aborted; nothing to undo.
- Bad data after a successful deploy → restore the step-1 backup
  (`heroku pg:backups:restore <id> -a beat-qa`, or the Supabase snapshot).

## Notes
- This deploys `rohit-qa` code to beat-qa, so beat-qa diverges from the `qa` branch until
  you merge PR #575 (`rohit-qa → qa`). A later qa deploy will then match.
- Going forward, the release-phase Procfile means deploys can't ship code ahead of their
  migrations again.
