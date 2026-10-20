# Construction techniques the import template offers that no longer exist

**Status: written up, not fixed. A decision is needed before it can be.**

Migration 0046 consolidated building components from 19 to 14. It renamed and
merged construction techniques at the same time. The categories were mapped in
`_LEGACY_CATEGORY_NAMES`; the techniques were not.

## What happens today

`import_structural_components` looks the technique up by exact name. On a miss
it creates the assembly with `classification = None`. That used to be a bare
`except ... : pass`; it now logs a warning, so it is at least visible in the
dyno log.

**The carbon figure is unaffected** - that comes from the EPD and the quantity,
not the classification - so this is lost metadata, not a wrong number. That is
why it went unnoticed, and why it is lower priority than the faults fixed
around it.

## The scale

90 distinct techniques in the List sheet; **42 do not resolve**.

The template's own example rows use six techniques. Five resolve. The sixth,
`Stones and Tiles`, does not - so even the shipped example loses its
classification on one row.

## Why this was not mapped the way the categories were

`docs/taxonomy_mapping.md` marks each technique keep, rename, merge or drop.
The renames are mechanical, but the table also contains:

- **merges**, where two techniques become one - `Frame - Aluminum` and
  `Aluminum` both fold into `Aluminium`, combining their usage counts
- **drops**, 14 of them, for techniques with no recorded uses
- **prefix changes** - the old `Frame - X` and `Glazing - X` names lost their
  prefixes when Window Frames and Window Glazing merged into `Windows`

A merge or a drop is a decision about what a record means, not a spelling
change. Applying them from a draft spec without review would put a wrong
technique on an imported assembly silently, which is the failure mode this
project cares about most. So the mapping is written up here rather than
guessed at in code.

## The 42 that do not resolve

| Template offers | In the catalogue? |
|---|---|
| Air Gap <100mm Wide | no |
| Air Gap >100mm Wide | no |
| Aluminium Doors | no |
| Aluminium Windows | no |
| Aluminum | no |
| Aluminum Clad Timber | no |
| Aluminum Profile Cladding | no |
| Cellulose | no |
| Cement Fiber Boards on Metal Studs | no |
| Cement Fiber Boards on Timber Studs | no |
| Construction chemical | no |
| Cored (with Holes) Bricks with Internal & External Plaster | no |
| Cored (with Holes) Bricks with Plaster Both Sides | no |
| Double Glazing | no |
| Granites | no |
| In-Situ Reinforced Concrete Staircases and Ramps | no |
| In-Situ Reinforced Wall | no |
| Lintel, Sunshade and Sill Beam | no |
| Micro Concrete Tiles on Timber Rafters | no |
| Others | no |
| PCC for Footings | no |
| Paint and Coatings | no |
| Plasterboards on Metal Studs with Insulation | no |
| Plasterboards on Timber Studs with Insulation | no |
| Polystyrene | no |
| Polyurethane | no |
| Pre-cast Concrete | no |
| Precast Concrete Double Tee Floor Units | no |
| Precast Concrete Double Tee Roof Units | no |
| Precast Concrete Foundations | no |
| Precast Concrete Sandwich Panel | no |
| Re-use of Existing Door Frames | no |
| Re-use of Existing Window Frames | no |
| Single Glazing | no |
| Steel (Zinc or Galvanized Iron) Sheets on Steel Rafters | no |
| Steel (Zinc or Galvanized iron) Sheets on Timber Rafters | no |
| Stones and Tiles | no |
| Surface preparation and treatments | no |
| Thin Precast Concrete Deck and Composite In-situ Slab | no |
| Triple Glazing | no |
| Ventillators | no |
| Woods | no |

## What a fix would involve

1. Walk `docs/taxonomy_mapping.md` technique by technique and confirm each
   rename, merge and drop against the current `AssemblyTechnique` rows.
2. Add a `_LEGACY_TECHNIQUE_NAMES` map beside `_LEGACY_CATEGORY_NAMES`, built
   from that review rather than from string similarity.
3. Correct the List sheet so new files offer names that exist, keeping the
   legacy map for files already saved.
4. Decide what a dropped technique should do: refuse the row, or import it
   without a classification as today. Refusing is the honest default
   everywhere else in this importer, but it would reject rows that currently
   succeed, so it is the user's call.

Until then the warning in the log is the only signal.
