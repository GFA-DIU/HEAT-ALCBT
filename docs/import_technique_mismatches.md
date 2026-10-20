# Construction techniques: the template vs the catalogue

**Status: mapped. 123 of the template's 136 dropdown entries now resolve; the
remaining 13 are the migration's deliberate drops.**

Migration 0046 consolidated building components from 19 to 14 and renamed or
merged construction techniques at the same time. The categories were mapped in
`_LEGACY_CATEGORY_NAMES`; the techniques were not, so 42 of the 90 distinct
names the template offers no longer existed - including `Stones and Tiles`,
which the shipped example row uses.

`import_structural_components` looks a technique up by exact name. On a miss it
creates the assembly with `classification = None`, under what used to be a bare
`except ... : pass`. **The carbon figure is unaffected** - that comes from the
EPD and the quantity - so this was lost metadata rather than a wrong number,
which is why it went unnoticed.

## What was done

`_LEGACY_TECHNIQUE_NAMES` maps the old names onto the current ones. It is keyed
on **(category, old name)**, not the name alone, because the same string means
different things in different categories: `In-Situ Reinforced Concrete Slab`
was renamed under Basement and kept under Roof; `Aluminium` exists only under
Windows and Doors.

A miss is now logged rather than swallowed.

## The spec could not be trusted on its own

`docs/taxonomy_mapping.md` is a draft, and the migration did not follow all of
it. It proposes dropping the `Frame —` and `Glazing —` prefixes on Windows.
**They were kept.** The catalogue holds `Frame — Aluminium` and
`Glazing — Single`, not `Aluminium` and `Single Glazing`.

Mapping from the spec would have left all nine Windows techniques unresolved
while looking right. Every target in the map is therefore checked against
`AssemblyCategoryTechnique` by `test_import_technique_map.py`, and a warning
has been added to that section of the spec.

## The two merges

Both are recorded in the spec and already applied by the migration.

| Category | Old names | Becomes | Combined uses |
|---|---|---|---|
| Windows | `Aluminium Windows`, `Aluminum` | `Frame — Aluminium` | 83 |
| Doors | `Aluminium Doors`, `Aluminum` | `Aluminium` | 433 |

`Air Gap <100mm Wide` and `Air Gap >100mm Wide` likewise both become `Air Gap`.

## One mapping that is not a migration decision

`Precast Concrete Foundations` (template) to `Precast Reinforced Concrete
Foundations` (catalogue) is not recorded in the spec - the two were simply
always worded differently. Precast concrete foundations are reinforced by
definition and Foundations has no other precast option, so they are treated as
the same technique. Agreed with the user on 2026-10-20.

## The 13 left unmapped, by decision

These were dropped by the migration, each with zero recorded uses. A row naming
one **imports without a classification** rather than being refused: the
material, quantity and carbon are all still good, and only the technique label
is missing. Refusing would reject rows that succeed today. Agreed with the user
on 2026-10-20.

| Category | Technique |
|---|---|
| Ground Floor | Precast Concrete Double Tee Floor Units |
| Ground Floor | Thin Precast Concrete Deck and Composite In-situ Slab |
| Roof | Precast Concrete Double Tee Roof Units |
| Roof | Micro Concrete Tiles on Timber Rafters |
| Internal Walls & Partitions | Precast Concrete Sandwich Panel |
| Internal Walls & Partitions | Cement Fiber Boards on Timber Studs |
| Internal Walls & Partitions | Plasterboards on Timber Studs with Insulation |
| Internal Walls & Partitions | Plasterboards on Metal Studs with Insulation |
| Windows | Aluminum Clad Timber |
| Windows | Re-use of Existing Window Frames |
| Insulation | Cellulose |

(`Thin Precast Concrete Deck...` is mapped under Beams & Slabs and Roof, and
dropped only under Ground Floor. `Cellulose` appears under all three insulation
groups, which collapse into one category.)

## Still open

The template's List sheet still OFFERS the old names. They import correctly
through the map, so this is cosmetic rather than broken, but a user picking
from the dropdown is picking a name the catalogue no longer uses. Correcting
the sheet means editing the XML in place - openpyxl destroys the workbook's
x14 validations - and has not been done.
