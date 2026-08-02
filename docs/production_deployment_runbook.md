# Production Deployment Runbook — rohit-qa EPD/taxonomy work

Covers every data/code change made on `rohit-qa` and how to roll it out to production
(Heroku + Supabase) **safely and in order**. Nothing here runs automatically — each
step is deliberate. Read §0 and §1 before starting.

> Scope note: writing/committing this runbook and the migration is confined to the
> `rohit-qa` branch. Production is only affected when you merge, deploy, and run the
> steps below against the prod database.

---

## 0. What is being deployed

| # | Change | Reaches prod via |
|---|---|---|
| A | Assembly taxonomy consolidation (19→14) + family + dimension/ton | migrations `0045`–`0048` |
| B | Operational energy-carrier **rename** (cerosin→Kerosene, Title Case) | migration `0049` |
| C | TGO Thailand EPD refresh + categorization | `load_thailand_epds` |
| D | ECO-Platform EPD import/refresh (186 new) | `load_ecoplatform_epds` |
| E | Generic structural EPD refresh (GWP/PENRT, steel→tonne) | `load_local_epds -f generic_EPDs` |
| F | Generic operational EF update (TH electricity 0.475, natural gas) | `load_local_epds -f generic_operationaL_EPDs` |
| G | Centralized categorization (shared resolver) | code only (used by C–F) |
| H | IFC grid-localized generic EPDs (98 materials × ID/VN/KH/TH: binders, aluminium, glass, tiles…) | `load_local_epds -f IFC_localized_generic_EPDs` |

**In-use safety:** C and D never modify EPDs already used in a building (copy-on-change).
E and F update in place **by design** (generic placeholders) — verified during dev that
only generic in-use EPDs change; all other sources stay byte-identical.

---

## 1. Prerequisites (do first)

1. **Rotate the exposed secrets.** Production secrets were pasted in chat earlier and
   must be considered compromised: `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`
   (⚠️ rotating this re-keys encrypted fields — coordinate carefully), Supabase DB
   password, `REPORT_API_KEY` (OpenAI), Mailgun/`EMAIL_HOST_PASSWORD`, Honeybadger,
   New Relic, Papertrail. Rotate in Heroku config vars.
2. **Fresh ECO-Platform token** for step D — tokens are short-lived (~24h). Set
   `ECO_PLATFORM_TOKEN` in Heroku config just before running D. (No Norton CA-bundle
   workaround needed on Heroku — that was a local-machine issue only.)
3. Confirm the deploy branch flow (this repo: `rohit-qa` → `qa` → `main`, Heroku deploys
   `main`). Merge cleanly, no force-push.

---

## 2. Back up production FIRST

```
# Supabase: take a manual backup / PITR snapshot in the dashboard, OR pg_dump:
pg_dump "$SUPABASE_DATABASE_URL" -Fc -f prod_backup_$(date +%Y%m%d_%H%M).dump
```
Do not proceed until you have a restorable backup.

---

## 3. Deploy the code

Merge `rohit-qa` into the deploy branch and deploy as usual. Migrations A + B run in the
release phase (`release: python manage.py migrate` in the Procfile, if configured).
If migrations are **not** in the release phase, run §4 manually.

---

## 4. Run migrations (schema + rename)

```
heroku run python manage.py migrate --app <your-app>
```
This applies `0045`–`0049`. **`0049` must run before step F** (it renames the operational
carriers so the loader updates them in place instead of inserting duplicates).
`0049` is idempotent and collision-safe (skips any name already taken).

Verify:
```
heroku run python manage.py showmigrations pages --app <your-app>   # 0045–0049 = [X]
```

---

## 5. Run the data loaders (in this order)

Each is idempotent (safe to re-run). Run on the prod dyno:

```
# C — TGO Thailand (selective replace; protects in-use EPDs)
heroku run python manage.py load_thailand_epds --app <your-app>

# D — ECO-Platform (needs ECO_PLATFORM_TOKEN set; ~383 fetches, a few minutes)
heroku run python manage.py load_ecoplatform_epds --app <your-app>

# E — generic structural EPDs (update-in-place; verified no duplicates)
heroku run python manage.py load_local_epds -f generic_EPDs --app <your-app>

# F — generic operational EPDs (electricity/natural-gas + names; needs 0049 applied)
heroku run python manage.py load_local_epds -f generic_operationaL_EPDs --app <your-app>

# H — IFC grid-localized generic EPDs (the ~216 new localized rows for ID/VN/KH/TH).
#     NOTE: the loader is invoked through load_local_epds with the -f key below — there is
#     NO standalone `import_ifc_localized_epds` manage.py command (that is an internal
#     importer function). Idempotent: update_or_create keyed on (name, country, source).
heroku run python manage.py load_local_epds -f IFC_localized_generic_EPDs --app <your-app>

# G — GCCA A–G concrete Low Carbon Ratings (dynamic; run AFTER C so the Thai ready-mix
#     concretes exist). --overwrite recomputes ALL m³ concrete labels from the formula,
#     which also CORRECTS the ~19 mis-assigned static generic-placeholder labels from
#     the old CSV. Rates ready-mix/precast only; skips off-table / non-structural.
heroku run python manage.py apply_gcca_concrete_labels --overwrite --app <your-app>
```
(Note the capital "L" in `generic_operationaL_EPDs` — that is the actual file key.)

---

## 6. Optional — re-categorize pre-existing library EPDs

The loaders (C–F) categorize their own rows via the shared resolver. Pre-existing library
EPDs that were mislabeled ("Primer for paints and plasters" / "Unknown") can be corrected
in one pass:
```
heroku run python manage.py shell --app <your-app> -c "
from django.db.models import Q
from pages.scripts.epd_categorization import resolve_by_name
from pages.models.epd import EPD
qs = EPD.objects.filter(Q(category__isnull=True) | Q(category__name_en__in=['Unknown','Primer for paints and plasters']))
n=0
for e in qs.iterator():
    new = resolve_by_name(e.name)
    if new and e.category_id != new.id:
        e.category = new; e.save(update_fields=['category']); n+=1
print('re-categorized', n)
"
```

---

## 7. Verification (post-deploy)

```
heroku run python manage.py shell --app <your-app> -c "
from pages.models.epd import EPD
print('total EPDs:', EPD.objects.count())
print('TGO:', EPD.objects.filter(source='TGO').count())
print('generic:', EPD.objects.filter(source='GFA-HEAT').count())
# operational carriers should be Title Case, no old names:
bad = EPD.objects.filter(source='GFA-HEAT', declared_unit='kwh', name__in=['cerosin','char coal','coal','diesel','electricity','natural gas']).count()
print('old-name carriers remaining (want 0):', bad)
# TH electricity factor:
e = EPD.objects.filter(source='GFA-HEAT', declared_unit='kwh', name='Electricity', country__code2='TH').first()
from pages.models.epd import EPDImpact
print('TH electricity gwp_b6:', EPDImpact.objects.filter(epd=e, impact__impact_category='gwp', impact__life_cycle_stage='b6').values_list('value', flat=True).first())
"
```
Expected: 0 old-name carriers; TH electricity `0.475`. Then smoke-test a building in the UI
(EPD library chips populated, dashboard groups, a calculation runs).

---

## 8. Rollback

- **Code/migrations:** `0049` and `0045` are reversible (`migrate pages 0048` reverts the
  rename). Taxonomy migrations should be reverted only via the backup if data was
  consolidated.
- **Data:** restore the §2 backup. The loaders themselves are not auto-reversible; the
  backup is the safety net. This is why §2 is mandatory.

---

## Known follow-ups (not in this deploy)

- Mass/volume **fuel** operational factors (Diesel/LPG/Kerosene/…) still per-kWh from the
  old source — deferred pending calorific values (TH-only scope). See
  `docs/thailand_operational_ef.md`.
- **Refrigerant** GWP data in the TGO sheet is corrupted — not imported.
- `import_generic_operational_epds` still hardcodes `Unit.KWH` and uses `get_or_create`
  for categories — fine for current data; tidy up when fuels are done.
