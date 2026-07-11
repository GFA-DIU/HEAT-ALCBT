# Front-end Duplication Audit — Component / BoQ / Material editors

Status: **documented, no deletions made** (2026-07-11, branch `rohit-qa`).
Purpose: map the duplicated structural-component editing UIs, classify LIVE vs LEGACY,
and record exactly what can be removed later (with evidence + a safe plan).

---

## TL;DR

There are two parallel editors for structural components / BoQ:

- **NEW (LIVE):** the add-building **wizard** UI. Keep.
- **OLD (LEGACY):** the **"Simulation"** feature and its crispy editors. Appears unlinked
  from the live app — a removal candidate, but it's one big interconnected feature, and
  the `/building/<id>/simulation` route still exists, so confirm it's retired before deleting.

The live building **detail** page (`building.html`) uses **neither** cluster for editing —
it renders its own charts/tabs; structural editing happens in the wizard.

---

## Cluster A — NEW / LIVE (keep)

Used by the add-building wizard and edit flow.

| Kind | Path |
|------|------|
| Template | `templates/pages/add-building/components/building-structural-components/building-structural-components.html` |
| Template | `.../building-structural-components/_selected_material.html` (BoQ/material row) |
| Template | `.../building-structural-components/_epd_list.html` + `partials/` |
| View | `pages/views/building/building_step_structural.py` |
| View | `pages/views/building/add_building_steps.py` (`handle_structural_components_step`) |
| URL | `building_step_structural` → `/building/step/structural` |

## Cluster B — OLD / LEGACY (removal candidate)

Reachable only through the **Simulation** page; the live `building.html` has **zero**
`simulation` references (evidence below), so this whole chain looks retired.

Chain: `building_simulation` view → `building_simulation.html` → `building_core.html`
→ `structural_info.html` → `assemblies_list.html` → `component_edit`/`boq_edit` → `assembly.html`/`boq.html`.

| Kind | Path / name |
|------|-------------|
| View | `pages/views/building/building_simulation.py` (`building_simulation`) |
| View | `pages/views/assembly/assembly.py` (`component_edit`) |
| View | `pages/views/assembly/save_to_assembly.py` |
| View | `pages/views/boq/boq.py` (`boq_edit`) |
| Form | `pages/forms/assembly_form.py` (`AssemblyForm`) |
| Form | `pages/forms/boq_assembly_form.py` (`BOQAssemblyForm`) |
| URLs | `building_simulation`, `component`, `component_edit`, `boq`, `boq_edit` (urls.py lines ~118–133) |
| Templates | `templates/pages/building/building_simulation.html`, `building_core.html` |
| Templates | `templates/pages/building/structural_info/` (`structural_info.html`, `assemblies_list.html`) |
| Templates | `templates/pages/assembly/` (`assembly.html`, `boq.html`, `epd_list.html`, `selected_epd.html`, `modal_step_1.html`, `modal_step_2.html`, `editor_own_page.html`) |

## Reachability evidence

- `structural_info.html` is included **only** by `building_core.html:241`.
- `building_core.html` is included **only** by `building_simulation.html:30`.
- `building.html` (live detail page, rendered by `building()` in `building.py:112`) contains
  **no** `simulation` string → the old chain is not linked from the detail page.
- Every `{% url 'building_simulation' %}` / `component` / `boq` link lives **inside** old-cluster
  templates (`assembly/*`, `structural_info/*`) — no live entry point found.
- `AssemblyForm`/`BOQAssemblyForm` are imported only by `assembly.py`, `save_to_assembly.py`, `boq.py`.

---

## ⚠️ Before deleting — must-check / shared dependencies

1. **The `/building/<id>/simulation` route still exists.** Static analysis can't prove no one
   reaches it via a bookmark/external link. **Confirm with the team that "Simulation" is retired.**
2. **Operational templates share the `simulation` flag.** `templates/pages/building/operational_info/*`
   (operational_products.html, operational_product_list.html, selected_operational_product.html)
   contain `{% if simulation %}` branches pointing at `building_simulation`. These files are ALSO
   used in the live (non-simulation) flow — only the `simulation` branches would be removed, not
   the files. Handle carefully; don't delete these files.
3. `assemblies_list.html` also has a `{% if simulation %}` delete branch — it's old-cluster, safe to
   remove with the cluster, but verify no live include.
4. `select_lists` view is shared by both clusters — **keep**.
5. Removing views requires also removing their imports + URL patterns in `pages/urls.py`.

## Suggested removal plan (later, its own PR — NOT with the taxonomy deploy)

Do it staged, re-running the app + full test suite after each step:

1. Confirm Simulation is retired (team check).
2. Delete old templates: `templates/pages/assembly/`, `templates/pages/building/structural_info/`,
   `building_core.html`, `building_simulation.html`.
3. Delete old views: `assembly.py`, `save_to_assembly.py`, `boq.py`, `building_simulation.py`
   (+ their dirs if empty).
4. Remove URL patterns + imports in `pages/urls.py`: `building_simulation`, `component`,
   `component_edit`, `boq`, `boq_edit`.
5. Delete forms: `assembly_form.py`, `boq_assembly_form.py`.
6. Remove the `{% if simulation %}` branches from the operational templates (edit, don't delete).
7. `python manage.py check`, run pytest, click through the wizard + building detail page.

## Note

The Building-Part work added to `assembly.html`/`AssemblyForm` earlier is part of this legacy
cluster; if the cluster is removed, that edit simply goes away (the live editors that matter —
the wizard, the BoQ modal, and the reusable-templates modal — were updated separately and stay).
The reusable-templates editor (`templates/pages/home/templates.html`) is **LIVE** and unrelated
to this legacy cluster — keep it.
