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
