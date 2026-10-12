# Lower-carbon material alternatives — scope

A proposal to replace the dead "Read LCA Guidelines" / "Read Energy Guidelines"
buttons with something that uses the EPD catalogue: for each material a building
used, show the lowest-carbon equivalent **available in that country**, and what
switching would save.

Nothing is built yet. This note exists to be agreed first, because the obvious
implementation gives dangerous advice.

## Why the obvious version is wrong

Grouping by material category and recommending the lowest GWP produces
substitutions that are not substitutions:

| Group | Spread | Cheapest option |
|---|---|---|
| Thailand, "Cement" /kg | 13.7× | **BF Slag at 0.070** — a supplementary cementitious material, not a cement you can swap one-for-one |
| Thailand, "Coverings" /m² | 376× | paint, against structural cladding |
| Thailand, "Building services" /pcs | 74× | unrelated components sharing a category |

A tool that suggests replacing Portland cement with slag, or cladding with
paint, is worse than one that says nothing.

## What is actually safe to compare

Grouped on `material_name` (from the nomenclature work) **plus declared unit**,
and for concrete additionally on strength class via the existing
`strength_to_mxx` parser. Only families where a swap is genuinely a swap:

```
Ready mixed concrete /m3      matched on M-class
Steel sheet /kg
Structural steel /kg
Steel long product /kg
Prestressing steel strand /kg
Mortar /kg
Tile adhesive /kg
Gypsum plasterboard /m2
Fibre cement board /m2
Glass wool insulation /m2
```

## What the data gives, per country

Best versus worst within a like-for-like group, from the catalogue as it stands:

| Country | Group | Options | Best | Worst | Saving |
|---|---|---|---|---|---|
| India | Steel sheet /kg | 12 | 2.460 | 5.230 | −53% |
| India | Structural steel /kg | 8 | 2.110 | 5.510 | −62% |
| India | Fibre cement board /m² | 8 | 6.470 | 11.500 | −44% |
| Thailand | Mortar /kg | 17 | 0.121 | 0.482 | −75% |
| Thailand | Gypsum plasterboard /m² | 13 | 0.880 | 4.350 | −80% |
| Thailand | Glass wool insulation /m² | 8 | 0.530 | 6.990 | −92% |
| Thailand | Ready-mix concrete M30 /m³ | 6 | 202 | 347 | −42% |
| Vietnam | Tile adhesive /kg | 10 | 0.260 | 1.010 | −74% |
| Indonesia | Gypsum plasterboard /m² | 7 | 1.190 | 3.380 | −65% |
| Indonesia | Steel sheet /kg | 5 | 1.800 | 3.230 | −44% |

**Cambodia has no like-for-like group with two or more options.** Of its 186
EPDs, 179 are generics and the 7 official ones are all cement — and cement is
on the unsafe list. The panel would be empty there, and should say so rather
than appear broken. This is an argument for the environdec shortlist work:
Cambodia only has 6 products in the entire EPD International library.

## Proposed presentation

The dark insight box becomes a list, scoped to the user's country:

```
Lower-carbon options in Thailand

  Ready-mix concrete M30
    you used      271 kgCO₂e/m³
    best local    202   (named product, links to the EPD)
    −69 kgCO₂e/m³        = −X kgCO₂e/m² GFA at your quantity

  Gypsum plasterboard
    you used     3.09 kgCO₂e/m²
    best local   0.88
    ...

  Total if all swapped: −N kgCO₂e/m²
```

Every row links to the source EPD, so the user can confirm the substitution is
technically valid before trusting it. BEAT suggests; it does not decide.

## Checked again: material_name is still too coarse to recommend a swap

The groups above look reasonable until you read their contents. Three examples,
all official EPDs, all one country, one material name and one declared unit:

**Thailand, gypsum plasterboard /m²**

```
0.880  Standard Board 9mm          <- "best"
1.630  Standard Board 12mm
2.820  MultiWall 15mm
2.970  GlassBloc 12.7mm
4.350  MultiWall MR 15mm           <- "worst"
```

A 9 mm standard board is not a substitute for a 15 mm moisture-resistant
multi-layer wall board. Different thickness, different fire, acoustic and
moisture ratings. The 80% "saving" is mostly the difference between two
different products doing two different jobs.

**Thailand, glass wool insulation /m²**

```
0.530  SCG Encapsulated Insulation
0.650  SCG Green Batts
6.990  SCG Cylence Zandera          <- an acoustic product
```

**India, structural steel /kg**

```
2.110  Optigal (metallic colour coated steel)
2.420  Finished Long Products
5.510  Steel Flange
```

Coated sheet against a forged flange. Not a swap.

The one family where matching is rigorous is **concrete**, because strength
class is a real equivalence and BEAT already parses it. Those rows hold up:
M25 271 → 209, M30 347 → 202.

There is also the occasional genuine pair — Thailand has `Standard Board 9mm`
from two different EPDs at 0.880 and 1.330, which is a real like-for-like 34%
difference. But finding those needs thickness and type parsed out of product
names, and the naming is inconsistent between manufacturers.

## Decided direction: show the local range, prescribe nothing

Rather than "switch to X", report where the building's material sits among what
is actually declared in its country:

> Gypsum plasterboard in Thailand ranges **0.88 – 4.35 kgCO₂e/m²** across 13
> official EPDs. Yours is 3.09 — in the upper quartile.

This is true without claiming substitutability. It tells a designer their
specification is carbon-heavy for its class and leaves the engineering
judgement where it belongs. It is the same shape as the EUI benchmark banner
already on the Savings tab.

Rules agreed:

- **official EPDs only** — generics excluded. This costs nothing: of the 130
  EPDs in these families, 125 are already official, 1 official-non-standard and
  only 4 generic.
- **concrete matched on strength class**; a concrete whose strength cannot be
  parsed is excluded rather than compared against an unknown mix.
- **savings below 10% are noise** and not worth showing — that drops
  prestressing strand at 1% and ready-mix M50 at 5%.
- **cross-country availability belongs on its own tab**, not here.
- **Cambodia will be empty and must say why**: 179 of its 186 EPDs are generic
  and the 7 official ones are all cement, which is not comparable like-for-like.
  The panel should state that rather than render blank.

## Open questions for GT

1. Should a suggestion be withheld when the alternative is from a different
   manufacturer in a different part of the country — i.e. is availability a
   procurement question BEAT should not assume?
2. Concrete is matched on strength class, but exposure class (XC, XD, XS) also
   constrains the mix. Match on that too, or state the caveat?
3. Does the "best local" option need a minimum data quality — official EPD
   only, excluding generics?
