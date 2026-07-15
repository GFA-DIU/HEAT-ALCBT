# BEAT — Component & Technique Taxonomy Remap (DRAFT SPEC)

This is the working spec for consolidating building components (categories) and
construction techniques (subcategories). It drives the data migration.

**Rules applied:** Moderate trim · British + Title Case · blank → "Not specified".

**Legend:** ✓ keep · ✎ rename · ⇒ merge into · ✗ drop (0 uses, no data to move).
Numbers in (…) = materials currently using that technique.

**Data safety:** every technique with usage is either kept or *merged* (its materials
repointed) — never dropped. Only 0-use techniques are dropped. Each category keeps a
"Not specified" option (the current blank, relabelled — a display change, no data move).

---

## Family A — Substructure

### 1. Foundations  ← Foundation
| Old technique (uses) | Action | New name |
|---|---|---|
| In-Situ Reinforced Concrete Foundations (1701) | ✓ | In-Situ Reinforced Concrete Foundations |
| PCC for Footings (481) | ✎ | Plain Cement Concrete (PCC) Footings |
| Precast Reinforced Concrete Foundations (45) | ✓ | Precast Reinforced Concrete Foundations |

### 2. Basement & Retaining Walls  ← Basement
| Old technique (uses) | Action | New name |
|---|---|---|
| In-Situ Reinforced Concrete Slab (71) | ✎ | In-Situ Reinforced Concrete |
| Pre-cast Concrete (2) | ✎ | Precast Concrete |
| Masonry with Concrete (0) | ✓ | Masonry with Concrete *(standard option)* |

---

## Family B — Superstructure

### 3. Columns  ← Columns
| Old technique (uses) | Action | New name |
|---|---|---|
| In-Situ Reinforced Concrete Columns (599) | ✓ | In-Situ Reinforced Concrete Columns |
| Precast Reinforced Concrete Columns (15) | ✓ | Precast Reinforced Concrete Columns |

### 4. Beams & Slabs  ← Beams, Slabs **＋ Upper Floors (Intermediate Floor)**
| Old technique (uses) | Action | New name |
|---|---|---|
| In-Situ Reinforced Concrete Beams (991) | ✓ | In-Situ Reinforced Concrete Beams |
| Reinforced Concrete Slab (398) *[from Upper Floors]* | ✓ | Reinforced Concrete Slab |
| Precast Reinforced Concrete Beams (18) | ✓ | Precast Reinforced Concrete Beams |
| Concrete Filler Slab (6) | ✓ | Concrete Filler Slab |
| Light Gauge Steel Floor Cassette (4) | ✓ | Light Gauge Steel Floor Cassette |
| Precast Concrete Double Tee Floor Units (3) | ✎ | Precast Concrete Double Tee Units |
| Thin Precast Concrete Deck and Composite In-situ Slab (2) | ✎ | Thin Precast Concrete Deck & Composite In-Situ Slab |
| Timber Floor Construction (1) | ✓ | Timber Floor Construction |
| Hollow Core Precast Slab (0) | ✓ | Hollow Core Precast Slab *(standard option)* |
_The two blank joins (749 + 248) merge into one "Not specified" (997)._

### 5. Ground Floor  ← Bottom Floor Construction
| Old technique (uses) | Action | New name |
|---|---|---|
| Reinforced Concrete Slab (250) | ✓ | Reinforced Concrete Slab |
| Concrete Filler Slab (11) | ✓ | Concrete Filler Slab |
| Light Gauge Steel Floor Cassette (1) | ✓ | Light Gauge Steel Floor Cassette |
| Timber Floor Construction (1) | ✓ | Timber Floor Construction |
| Precast Concrete Double Tee Floor Units (0) | ✗ | drop |
| Hollow Core Precast Slab (0) | ✗ | drop |
| Thin Precast Concrete Deck and Composite In-situ Slab (0) | ✗ | drop |

### 6. Roof  ← Roof Construction
| Old technique (uses) | Action | New name |
|---|---|---|
| In-Situ Reinforced Concrete Slab (225) | ✓ | In-Situ Reinforced Concrete Slab |
| Steel (Zinc or Galvanized Iron) Sheets on Steel Rafters (35) | ✎ | Metal Sheets on Steel Rafters |
| Clay Roofing Tiles on Steel Rafters (7) | ✓ | Clay Roofing Tiles on Steel Rafters |
| Concrete Filler Slab (3) | ✓ | Concrete Filler Slab |
| Micro Concrete Tiles on Steel Rafters (1) | ✓ | Micro Concrete Tiles on Steel Rafters |
| Thin Precast Concrete Deck and Composite In-situ Slab (1) | ✎ | Thin Precast Concrete Deck & Composite In-Situ Slab |
| Steel (Zinc or Galvanized iron) Sheets on Timber Rafters (1) | ✎ | Metal Sheets on Timber Rafters |
| Steel-clad Sandwich Panel (1) | ✓ | Steel-clad Sandwich Panel |
| Clay Roofing Tiles on Timber Rafters (0) | ✓ | Clay Roofing Tiles on Timber Rafters *(standard pair)* |
| Micro Concrete Tiles on Timber Rafters (0) | ✗ | drop |
| Hollow Core Precast Slab (0) | ✗ | drop |
| Precast Concrete Double Tee Roof Units (0) | ✗ | drop |

### 7. Staircases & Ramps  ← Staircases and Ramps
| Old technique (uses) | Action | New name |
|---|---|---|
| In-Situ Reinforced Concrete Staircases and Ramps (127) | ✎ | In-Situ Reinforced Concrete |
| Railings (15) | ✓ | Railings |
| Stainless Steel Guard Railing (6) | ✓ | Stainless Steel Guard Railing |

---

## Family C — Envelope & Openings

### 8. External Walls  ← Exterior Walls  (all used — spelling only)
| Old technique (uses) | Action | New name |
|---|---|---|
| Common Brick Wall with Internal & External Plaster (326) | ✓ | Common Brick Wall with Internal & External Plaster |
| Autoclaved Aerated Concrete Blocks (132) | ✓ | Autoclaved Aerated Concrete Blocks |
| Solid Dense Concrete Blocks (33) | ✓ | Solid Dense Concrete Blocks |
| Precast Concrete Panels (19) | ✓ | Precast Concrete Panels |
| Steel-clad Sandwich Panel (12) | ✓ | Steel-clad Sandwich Panel |
| Aluminum Profile Cladding (8) | ✎ | Aluminium Profile Cladding |
| Stone Blocks (7) | ✓ | Stone Blocks |
| Honeycomb Clay Blocks with Plaster on Both Sides (6) | ✓ | Honeycomb Clay Blocks with Plaster on Both Sides |
| Cored (with Holes) Bricks with Internal & External Plaster (3) | ✓ | Cored Bricks with Internal & External Plaster |
| Steel Profile Cladding (2) | ✓ | Steel Profile Cladding |
| Curtain Walling (Opaque Element) (1) | ✓ | Curtain Walling (Opaque Element) |
| Medium Weight Hollow Concrete Blocks (1) | ✓ | Medium Weight Hollow Concrete Blocks |

### 9. Internal Walls & Partitions  ← Interior Walls
| Old technique (uses) | Action | New name |
|---|---|---|
| Common Brick Wall with Plaster Both Sides (274) | ✓ | Common Brick Wall with Plaster Both Sides |
| Autoclaved Aerated Concrete Blocks (59) | ✓ | Autoclaved Aerated Concrete Blocks |
| In-Situ Reinforced Wall (18) | ✓ | In-Situ Reinforced Concrete Wall |
| Solid Dense Concrete Blocks (13) | ✓ | Solid Dense Concrete Blocks |
| Stone Blocks (8) | ✓ | Stone Blocks |
| Honeycomb Clay Blocks with Plaster on Both Sides (5) | ✓ | Honeycomb Clay Blocks with Plaster on Both Sides |
| Cored (with Holes) Bricks with Plaster Both Sides (2) | ✎ | Cored Bricks with Plaster Both Sides |
| Cement Fiber Boards on Metal Studs (1) | ✓ | Cement Fibre Boards on Metal Studs |
| Plasterboards on Metal Studs (1) | ✓ | Plasterboards on Metal Studs |
| Plasterboards on Timber Studs (1) | ✓ | Plasterboards on Timber Studs |
| Precast Concrete Panels (1) | ✓ | Precast Concrete Panels |
| Cement Fiber Boards on Timber Studs (0) | ✗ | drop |
| Precast Concrete Sandwich Panel (0) | ✗ | drop |
| Plasterboards on Metal Studs with Insulation (0) | ✗ | drop |
| Medium Weight Hollow Concrete Blocks (0) | ✗ | drop |
| Plasterboards on Timber Studs with Insulation (0) | ✗ | drop |

### 10. Windows  ← Window Frames **＋ Window Glazing**
| Old technique (uses) | Action | New name |
|---|---|---|
| *Frame —* UPVC (67) | ✓ | UPVC |
| *Frame —* Aluminium  Windows (43) | ✎ | Aluminium |
| *Frame —* Aluminum (40) | ⇒ | **merge → Aluminium** (combined 83) |
| *Frame —* Timber (14) | ✓ | Timber |
| *Frame —* Wood Shutters (8) | ✓ | Wood Shutters |
| *Frame —* Steel (8) | ✓ | Steel |
| *Frame —* Ventillators (3) | ✎ | Ventilators |
| *Frame —* Aluminum Clad Timber (0) | ✗ | drop |
| *Frame —* Re-use of Existing Window Frames (0) | ✗ | drop |
| *Glazing —* Single Glazing (70) | ✓ | Single Glazing |
| *Glazing —* Double Glazing (34) | ✓ | Double Glazing |
| *Glazing —* Triple Glazing (0) | ✓ | Triple Glazing *(standard option)* |

### 11. Doors  ← Door Frames  (renamed — it's more than frames)
| Old technique (uses) | Action | New name |
|---|---|---|
| Aluminium Doors (400) | ✎ | Aluminium |
| Aluminum (33) | ⇒ | **merge → Aluminium** (combined 433) |
| Wood Shutters (36) | ✓ | Wood Shutters |
| Timber (17) | ✓ | Timber |
| Steel (9) | ✓ | Steel |
| Fire Doors (8) | ✓ | Fire Doors |
| Aluminum Clad Timber (6) | ✎ | Aluminium Clad Timber |
| UPVC (6) | ✓ | UPVC |
| Re-use of existing Door Frames (5) | ✎ | Re-use of Existing Doors |

---

## Family D — Finishes & Other

### 12. Finishes  ← Finishes **＋ Floor Finish**
| Old technique (uses) | Action | New name |
|---|---|---|
| Surface layers (600) | ✎ | Surface Layers |
| Paint and Coatings (252) | ✎ | Paint & Coatings |
| Surface preparation and Treatments (52) | ✎ | Surface Preparation & Treatments |
| Cladding (37) | ✓ | Cladding |
| Additives (9) | ✓ | Additives |
| Ceramic Tiles (132) *[Floor Finish]* | ✓ | Ceramic Tiles |
| Stones and Tiles (86) | ✎ | Stone & Tiles |
| Vitrified Tiles (60) | ✓ | Vitrified Tiles |
| Others (22) | ✎ | Other Floor Finishes |
| Granites (12) | ✎ | Granite |
| Teak Wood (0) | ✓ | Teak Wood *(kept as a distinct option)* |
| Woods (0) | ✎ | Timber Flooring *(generic wood option)* |

### 13. Insulation  ← Floor **＋** Roof **＋** Wall Insulation  (location dropped; material = technique)
| Old technique (uses, summed across the 3) | Action | New name |
|---|---|---|
| Glass Wool (2) | ✓ | Glass Wool |
| BRICKBAT COBA (2) | ✎ | Brickbat Coba *(traditional roof insulation — regionally relevant)* |
| Woodwool (2) | ✎ | Woodwool |
| Polystyrene (1) | ✓ | Polystyrene (EPS/XPS) |
| Cork (1) | ✓ | Cork |
| Mineral Wool (0) | ✓ | Mineral Wool *(standard option)* |
| Polyurethane (0) | ✓ | Polyurethane (PIR) *(standard option)* |
| Cellulose (0) | ✗ | drop |
| No Insulation (0) | ✓ | No Insulation |
| Air Gap <100mm Wide / >100mm Wide (0) | ✎ | Air Gap *(the two merged into one)* |
_The three blank joins (10 + 12 + 2 = 24) merge into one "Not specified" (24)._

### 14. Miscellaneous  ← Miscellaneous  (catch-all, kept)
| Old technique (uses) | Action | New name |
|---|---|---|
| Cement Mortar for Tiles (100) | ✓ | Cement Mortar for Tiles |
| Lintel, Sunshade and Sill Beam (49) | ✎ | Lintel, Sunshade & Sill Beam |
| Construction chemical (31) | ✎ | Construction Chemicals |

---

## Decisions (resolved)
1. **Floor Finish "Others" (22 uses):** → renamed "Other Floor Finishes".
2. **Timber flooring:** keep "Teak Wood" as a distinct option; rename "Woods" → "Timber Flooring" (generic).
3. **Insulation:** keep "No Insulation"; merge the two air gaps into one "Air Gap".
4. **Windows:** frame vs glazing options prefixed — "Frame — …" / "Glazing — …".
