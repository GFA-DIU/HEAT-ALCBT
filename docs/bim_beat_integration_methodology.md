# BIM → BEAT Integration — Methodology (v1, finalised before build)

Status: **methodology agreed, not yet built.** This is the design contract for
importing embodied-carbon quantities from BIM (IFC) into BEAT.

## 1. Decisions (locked)

| Decision | Choice |
|---|---|
| Architecture | **External converter** (standalone tool) that emits BEAT's existing import template. BEAT itself is unchanged. |
| Input format | **IFC** (ISO 16739). gbXML / operational deferred. |
| Scope (v1) | **Embodied carbon only** (structural quantities + materials). |
| Input assumption | IFC exports **carry materials + BaseQuantities** (NetVolume/NetArea/Length/Count), so no geometry engine needed in v1. |
| Material → EPD | **User review step**: the converter proposes an EPD per IFC material; the user confirms/overrides each before import. Unmatched → generic placeholder EPD. |

Rationale: lowest coupling and risk. BEAT already has a tested structural importer,
so we feed it rather than parse IFC inside the app. We can graduate to in-app upload
or a BIM plugin later once the mapping rules are proven.

## 2. The landing zone (why no new BEAT code is needed)

BEAT already imports `import_structural_components()` — the **"Structural Components
– By Component"** tab. The converter's only job is to produce rows in this shape:

| Column | Source in IFC |
|---|---|
| Building Component (→ AssemblyCategory) | element type / classification (IfcWall, IfcSlab, IfcColumn…) |
| Construction Technique (optional) | element predefined type / property |
| Dimension (area/volume/mass/length/pcs) | which BaseQuantity is used |
| Quantity + Units | IFC BaseQuantity value (NetVolume m³, NetArea m², Length m, Count) |
| Material: **EPD Name + Country** + Quantity + Units | IFC material → mapped to a BEAT EPD (looked up by name+country) |

Multiple material rows under one component = a multi-material assembly (e.g. concrete + rebar).

## 3. Pipeline

```
IFC ─▶ [1 Parse] ─▶ [2 Element→Component] ─▶ [3 Quantity→Dimension]
                                              │
                          [4 Material→EPD proposal] ─▶ [5 USER REVIEW] ─▶ [6 Emit BEAT template] ─▶ BEAT import
```

**1. Parse (IfcOpenShell, Python).** Read elements, their `IfcMaterial` / material
layer sets, `IfcElementQuantity` BaseQuantities, and classification refs. Walk the
spatial tree (Site→Building→Storey) for grouping/QA.

**2. Element → Building Component + Part.** Rule table (starter):
| IFC class (+ predefined type) | BEAT Building Part | BEAT Component |
|---|---|---|
| IfcFooting, IfcPile | Substructure | Foundation |
| IfcSlab (ground) | Substructure | Ground slab |
| IfcSlab (floor/roof), IfcColumn, IfcBeam, IfcMember | Superstructure | Floor slab / Column / Beam / Structural steel |
| IfcWall (load-bearing) | Superstructure | Wall |
| IfcWall (external), IfcCurtainWall, IfcRoof | Envelope & Openings | External wall / Roof |
| IfcWindow, IfcDoor | Envelope & Openings | Windows / Doors |
| IfcCovering | Finishes & Other | Finish |
The converter should read BEAT's **current** AssemblyCategory list (they were
consolidated to 14 with a Building-Part family) rather than hard-code names, since the
taxonomy can change. Use IFC classification (Uniclass/OmniClass) when present to refine.

**3. Quantity → Dimension + unit.** Prefer **NetVolume (m³ → VOLUME)** for structural
mass materials (most robust for embodied carbon; BEAT converts to the EPD's unit via
density). Use NetArea→AREA for sheet/finish elements, Length→LENGTH for linear-only,
Count→PCS for discrete. Map IFC SI units to BEAT units 1:1 (m³/m²/m).

**4. Material → EPD proposal.** For each IFC material: look up a mapping table
(material name/strength → BEAT EPD name+country). If no match → propose the **generic
placeholder EPD** for that material type + project country. Emit a *proposals* list.

**5. User review (required).** User sees each IFC material with the proposed EPD and
confirms or overrides (picking a specific BEAT EPD). This guarantees every emitted EPD
name resolves in BEAT's `_lookup_structural_epd` and that the LCA is intentional. This
step is where accuracy is won — material mapping is never fully automatic.

**6. Emit BEAT template** (Excel/CSV matching the Structural Components tab) → user
imports into BEAT as today.

## 4. Preconditions (validate up front, fail loudly)
- IFC schema IFC2x3 or IFC4; SI units.
- Elements carry an assigned material (or material layer set).
- Elements carry BaseQuantities (else flag element for manual quantity — v1 does not
  compute geometry; that is a later enhancement).

## 5. Edge cases & QA
- **Multi-layer walls/slabs**: expand each layer into its own material row (layer
  material + layer thickness × area → volume).
- **Missing material/quantity**: list as warnings; do not silently drop — user decides.
- **MEP / non-LCA elements**: excluded by the element-mapping rules (only structural /
  envelope classes are mapped).
- **Double counting**: one row per element-material; verify element counts vs the IFC.
- **Round-trip QA**: sum volumes per material from the converter vs an independent IFC
  QTO; sanity-check total GWP after import against expectations.

## 6. Build phases (after this methodology is signed off)
1. Converter core: IfcOpenShell parse → elements + materials + BaseQuantities (prove on a real sample IFC first).
2. Mapping layer: element→component rules + material→EPD proposals (+ generic fallback).
3. Review UI/step + BEAT-template emit; end-to-end round-trip into a test building.
4. Later: in-app upload or BIM plugin; geometry computation when QTO absent; **gbXML → operational/envelope**; growing the specific-EPD mapping library.

## 7. Open items to confirm before Phase 1
- Which BIM authoring tools + IFC version(s) users actually export (Revit/ArchiCAD/Tekla; IFC2x3 vs IFC4).
- Get **one real sample IFC** to characterise material naming and BaseQuantity coverage — this drives the mapping tables.
- Confirm the BEAT EPD naming/country convention the converter must emit so `_lookup_structural_epd` resolves.


---

# Addendum — the template reviewed against IFC (2026-10-26)

Reviewed the **shipped** template against the IFC schema, after the template
changed considerably: the metric column, the consolidated 14-category
taxonomy, corrected dropdowns, and the guards added to the importer. The
methodology above is still sound; this records what the landing zone can and
cannot carry, so the converter is written against the file as it is.

Checked against `static/docs/import-template.xlsx` as deployed in v176.

## A. What the landing zone actually accepts

The "Structural Components - By Component" sheet, column by column:

| Col | Field | Accepts |
|---|---|---|
| 0 | Title | free text — **unused today** |
| 1 | Building Component | one of the **14** consolidated AssemblyCategory names (old names still resolve via `_LEGACY_CATEGORY_NAMES`) |
| 2 | Construction Technique | one of **84** AssemblyTechnique names, or blank |
| 3 | Dimension | Area, Volume, Mass, Length, Pieces |
| 4-5 | Quantity + Units | kg, ton, m2, m3, m, pcs |
| 6 | Comment | free text — **unused today** |
| 8-9 | EPD Name + Country | EPD name, and one of India, Indonesia, Cambodia, Thailand, Vietnam, Global |
| 10-11 | Material Quantity + Units | as above |

## B. Where IFC maps cleanly — the quantity half

One to one, same SI units, no conversion:

| IFC base quantity | IFC type | BEAT dimension | Unit |
|---|---|---|---|
| `NetVolume` | IfcQuantityVolume | Volume | m3 |
| `NetArea`, `NetSideArea` | IfcQuantityArea | Area | m2 |
| `Length` | IfcQuantityLength | Length | m |
| `NetWeight` | IfcQuantityWeight | Mass | kg |
| element count | IfcQuantityCount | Pieces | pcs |

**NetVolume is the right default, as the methodology says.** buildingSMART
defines it as the total net volume "taking into account possible processing
features (cut-outs) or openings and recesses" — openings subtracted, which is
what embodied carbon needs. Gross would double-count.

`ton` is offered as a unit but no IFC quantity is expressed in tonnes; the
converter emits kg and lets BEAT convert. (`AssemblyDimension` also carries a
`ton` member that the dropdown does not offer — ignore it.)

Multi-material rows under one component match `IfcMaterialLayerSet` and
`IfcMaterialConstituentSet` directly.

## C. Where it does not map — the identity half

**1. No element identity.** Every IFC element carries a `GlobalId`, the only
stable key. Without it a BEAT row cannot be traced to the element that
produced it, and re-importing a revised model duplicates rather than updates.

**2. No storey.** `IfcBuildingStorey` is always present in IFC. BEAT has no
per-row level, so a 20-storey tower collapses into one list and the most
useful QA check — quantities per floor — is unavailable. Worth weight: the
Cambodia 250-building import needed exactly this kind of per-element check to
find that rebar was overstated 30-50%.

**3. The mapping inputs are not recorded.** `Pset_WallCommon.IsExternal` and
`.LoadBearing` are what separate External Walls from Internal Walls &
Partitions, and Ground Floor from Beams & Slabs. The converter must read them,
but only the resulting category is stored, so a wrong mapping leaves no trace
of why.

**4. Gross vs Net is not recorded.** Two converters could disagree and nothing
would show which was used.

**5. Country is always the converter's assumption.** IFC has no concept of an
EPD country. Injecting the project country is right, but it is an assumption
and must be visible as one.

## D. Decisions taken 2026-10-26

### D.1 Traceability goes in Title and Comment

Both columns are unused and the importer ignores them, so this needs no
template change and no import-code change — it works with the file already in
production.

| Column | Carries | Example |
|---|---|---|
| Title | IFC class + GlobalId | `IfcSlab 2O2Fr$t4X7Zf8NOew3FNrX` |
| Comment | storey, quantity source, classification | `Level 03; Qto_SlabBaseQuantities.NetVolume; Uniclass Ss_20_10_30` |

The Comment field is also where a converter-computed quantity must announce
itself once geometry computation arrives — a figure derived by the converter
must never be indistinguishable from one the model stated.

### D.2 Construction Technique: map what IFC supports, leave the rest blank

This is the weakest join. BEAT's 84 technique names are a construction
taxonomy; IFC's `PredefinedType` enums are coarser and differently shaped
(`IfcBeam`: BEAM, JOIST, HOLLOWCORE, LINTEL, SPANDREL, T_BEAM). Most elements
will not determine a BEAT technique.

- Map only where IFC genuinely determines it.
- Leave blank otherwise. **Do not infer from material plus element type** —
  precast versus in-situ is usually not in the model, and guessing asserts a
  construction method nobody stated.
- The converter **must report** how many rows had no technique.

Why the report matters: `import_structural_components` creates the assembly
with `classification = None` when a technique does not resolve. It now logs a
warning (`fix(import): an unknown technique no longer disappears without
trace`), but nothing appears on screen. A BIM import would produce that at
scale and silently, so the count belongs in the converter's own output.

### D.3 What the converter must validate up front

Beyond the preconditions in section 4 above:

- Every emitted Building Component resolves against BEAT's **current**
  category list, read at runtime, never hard-coded.
- Every emitted EPD Name + Country resolves through
  `_lookup_structural_epd` — and is **not** a cross-country match. That
  function returns a `CROSS_COUNTRY` marker when it had to cross a border for
  the EPD, which means the localised GWP is the wrong one.
- Units are among the six the template offers.
- Quantity > 0. The importer refuses zero and says so.
- The sum of material quantities per component is reconcilable against the
  component quantity — the converter should state both and let the user see
  them, as the template already carries both.

## E. Not changed, and why

No template columns were added. The workbook has been broken three times by
three different editing approaches (openpyxl destroying the x14 validations,
ElementTree renaming namespace prefixes so Excel offered to repair the file,
and a regex that swallowed a self-closing tag and deleted six building types).
Adding columns for a converter that does not yet exist would risk the file in
production for no present benefit. Title and Comment carry everything v1 needs.

If round-trip updates are built later — matching a revised model against an
existing BEAT building — dedicated GlobalId and Storey columns become worth
the risk, because parsing them out of free text is not a foundation for
matching.

## Sources

- Qto_SlabBaseQuantities / Qto_WallBaseQuantities, IFC 4.3.2 (IFC4X3_ADD2),
  buildingSMART: https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/Qto_SlabBaseQuantities.htm
- NetVolume and NetArea semantics quoted above are from those pages.
