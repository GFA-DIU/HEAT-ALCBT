# TGO (Thailand) EPD Data — Issues Report

**Date:** 2026-07-11 · **Branch:** rohit-qa · **Scope:** what was wrong with the TGO
(Thailand Greenhouse Gas Management Organization) EPD data and its handling in BEAT, and
what was fixed. TGO EPDs are `pages_epd` rows with `source = "TGO"`, country Thailand.

---

## Summary

Five distinct problems affected the TGO data and the code that consumes it:

1. **The `ton` unit broke the carbon calculation** (crash + no conversion logic).
2. **Stale / bloated dataset** — ~4,131 TGO EPDs in the DB vs a cleaned 1,162-row source.
3. **Duplicate identities** in the source file (19 rows un-disambiguatable).
4. **Structural data loss on import** — several useful fields dropped; no material-category link.
5. **Merge-only import** — old data never cleaned up, so stale rows accumulated over time.

---

## 1. The `ton` functional unit broke the calculation  🔴 (most severe)

TGO data declares many products per **ton** (76 EPDs — steel rebar, deformed bars, etc.).
The code did not handle this:

- **Crash:** `pages/views/building/impact_calculation.py` (`_fetch_dimension_for_boq`)
  referenced `Unit.TONES`, but that enum member was **renamed to `Unit.TON` in migration
  0045**. Result: `AttributeError: TONES` — **every BoQ carbon calculation crashed**, not
  just ton ones. (This also showed up as failing `test_impact_calculation_boq` tests.)
- **No conversion logic:** even past the crash, a `ton`-declared EPD had no handling in the
  factor-resolution steps, so it fell through to `"Unsupported combination"` and errored.
  → Any TGO material declared in tons could not be calculated at all.

**Impact:** steel/rebar (high-carbon, structurally important materials) were uncomputable,
and the underlying crash affected BoQ calculations generally.

**Fixed:** `ton` treated as a mass unit (1 ton = 1000 kg); resolved via the existing kg
logic then ÷1000, except when the quantity is entered directly in tons (BoQ). Added the
`Unit.TON` BoQ label and two regression tests (`test_boq_ton`, `test_mass_ton_component`).

## 2. Stale / bloated dataset  🟠

- The database held **~4,131** TGO EPDs, imported from an older, larger file
  (`TH_CFP-TGO_Data_final(18Feb2026).xlsx`, ~1.9 MB).
- The current cleaned source (`TH_CFP_Final_Usable_Dataset_20260709.xlsx`) has only
  **1,162 rows**.
- So **~2,937 EPDs were stale** — leftovers not present in the cleaned dataset, cluttering
  the EPD library and search results.

**Fixed:** selective refresh removed the 2,937 stale *unused* entries; DB now holds **1,194**
TGO EPDs (1,143 from the cleaned file + 51 in-use legacy records kept for safety).

## 3. Duplicate identities in the source file  🟠

- **19 rows** in the source sheet have a `Canonical_Name_EN` or `Certificate_No.` that is
  **not unique within the file**. There is no reliable way to tell such rows apart, so the
  importer **skips them** (neither imported nor updated).
- These need to be disambiguated **upstream by the data owner** (the raw file), not in code.

**Status:** flagged and skipped by the importer (reported in its run summary); not yet fixed
in the source file.

## 4. Structural data loss on import  🟡

The importer only maps a subset of the source columns; useful information is dropped or not
structured:

- **No material-category link.** TGO `Category` / `Subcategory` (e.g. "Envelope and
  Finishing" / "Flooring") are stored only inside a free-text `comment` string — **not** the
  structured `MaterialCategory` foreign key. So TGO products are **not classified** in the
  app's material taxonomy (mapping files `tgo_subcategory_mapping.json` /
  `material_category_mapping.json` exist but aren't wired into this import).
- **Only GWP / A1–A3.** Each TGO EPD carries a single impact — Global Warming Potential for
  life-cycle stage A1–A3 (production). No other indicators, no transport/use/end-of-life
  stages. Carbon results for TGO materials therefore cover production only.
- **Dropped columns:** `Date_of_Approval`, `Product_size_normalize`, `Canonical_Name_TH`
  (Thai name), and `Category` are read but not stored on the model.

**Status:** documented; not changed (out of scope for this pass — candidates for a follow-up).

## 5. Merge-only import let stale data accumulate  🟡

The previous importer was **update-or-create only** — it never removed anything. Re-running
it (or importing a newer, smaller file) left all prior rows in place, which is how the DB
grew to ~4,131 while the source shrank to 1,162.

**Fixed:** the importer now does a **selective replace** — it deletes stale *unused* rows
while never touching EPDs referenced by a building (see below).

---

## Cross-cutting risk: cascade deletes

`StructuralProduct.epd` (and the operational product models) reference `EPD` with
`on_delete=CASCADE`. **66 TGO EPDs are used by real buildings.** Deleting an EPD therefore
**cascade-deletes those buildings' materials** — so any cleanup must protect in-use records.

**Handled:** the new importer never deletes or modifies a used EPD. If a used EPD's value
matches the new file it's left as-is; if it differs, the original is kept and a copy named
`<name> (TGO 2026 update)` is added. Only *unused* stale rows are deleted.

---

## What was fixed vs. still open

| Issue | Status |
|-------|--------|
| 1. `ton` crash + missing conversion | ✅ Fixed (code + tests) |
| 2. Stale/bloated dataset | ✅ Fixed (selective refresh → 1,194) |
| 3. Duplicate names/certs in source | ⚠️ Skipped by importer; fix needed **in the source file** |
| 4a. No MaterialCategory link | ⏳ Open (follow-up candidate) |
| 4b. Only GWP / A1–A3 | ⏳ Open (limited by source data) |
| 4c. Dropped fields | ⏳ Open (follow-up candidate) |
| 5. Merge-only import | ✅ Fixed (selective replace) |

## Reproduction / references

- Importer: `pages/scripts/csv_import/import_thailand_epds.py` (run via
  `python manage.py load_thailand_epds`).
- Calc fix: `pages/views/building/impact_calculation.py`.
- Source data: `docs/TH_CFP_Final_Usable_Dataset_20260709.xlsx`, sheet `CFP_TGO_TH`.
- Local DB snapshot before the refresh: container `/tmp/pre_tgo.dump` (reversible).
