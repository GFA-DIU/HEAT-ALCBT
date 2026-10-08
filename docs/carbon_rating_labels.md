# Carbon rating labels in BEAT

What BEAT rates, what it deliberately does not, and why. Written so these
decisions do not get re-opened from memory.

## Concrete — GCCA Low Carbon Ratings — implemented

Source: <https://gccaepd.org/blog/lcr> (Table 1)

Seven bands, **AA to F**. AA is "near zero emissions concrete". There is no G.
Thresholds are the upper bound of each band in kgCO₂e/m³, keyed to the
concrete's **cylinder** strength class:

| Top of | M20 | M25 | M30 | M35 | M40 | M50 |
|---|---|---|---|---|---|---|
| AA | 21 | 23 | 26 | 29 | 32 | 36 |
| A | 68 | 75 | 83 | 94 | 101 | 113 |
| B | 115 | 127 | 141 | 159 | 171 | 190 |
| C | 161 | 179 | 199 | 224 | 241 | 268 |
| D | 208 | 231 | 256 | 288 | 310 | 345 |
| E | 255 | 283 | 314 | 353 | 380 | 422 |
| F | 302 | 335 | 372 | 418 | 450 | 500 |

The bands are equally spaced above AA — the step is ~47 kgCO₂e/m³ for M20 —
which is what GCCA means by "equally spaced carbon footprint values".

Computed by `pages/scripts/Label_mapping/gcca_rating.py`, applied by
`manage.py apply_gcca_concrete_labels`. Currently rates 294 EPDs.

A product above the top of F is reported as **unrated**, not given a letter.
An earlier version of this table omitted AA and invented a "G" for exactly
that case; two EPDs carried it until the scale was corrected.

Strength classes outside the six published columns (C12/15, C45/55, Thai 180
and 210 KSC) are left unrated, as are strength *ranges* — "200–300 KSC" cannot
be assigned to one column.

## Cement — GCCA Low Carbon Ratings — deliberately not implemented

Source: <https://gccassociation.org/lcr-cement/>

GCCA does publish cement ratings, AA–F, in kgCO₂e per tonne. They are **not**
implemented, and this is a decision rather than an omission.

The ratings have no single global table. Each country makes a *"one-off choice
of clinker/cement ratio"* and derives its own values from it; GCCA's worked
example uses 0.706, the ratio Germany adopted for its VDZ carbon classes.
Choosing that ratio for India, Cambodia, Indonesia, Vietnam and Thailand is a
national policy matter, not something a tool can assume.

GCCA's own guidance supports stopping at concrete:

> Indications are that some countries will choose to only adopt concrete
> ratings rather than cement ratings, as concrete is the final product. This
> approach aligns with the thinking behind the GCCA roadmap to achieving
> net-zero concrete which is a whole life roadmap.

For the record, the near-zero line is reconstructable from the IEA anchors
quoted by GCCA — 125 kgCO₂e/t at 100% clinker and 40 at 0%, so
`AA = 40 + 85 × clinker_ratio`, which gives exactly 100.0 at Germany's 0.706.
The A–F spacing is not derivable from the published text; it sits inside
Figure 2, an image. Implementing cement ratings without that would mean
shipping HEAT's own numbers under a GCCA name.

**If this is revisited:** ask GCCA for nationally adapted values
(info@gccassociation.org). Their page states they have already worked, or will
work, with national associations to produce them.

## Steel — LESS — not implemented, input data missing

Sources: <https://lowemissionsteelstandard.org/faq>,
<https://www.iea.org/reports/definitions-for-near-zero-and-low-emissions-steel-and-cement-and-underlying-emissions-measurement-methodologies/executive-summary>

The Low Emission Steel Standard classifies steel as Near Zero and A–E. It
classifies on **two** axes, not one:

1. kgCO₂e per tonne of crude steel
2. **scrap share**

The second is the blocker. The IEA sliding scale LESS is built on puts the
near-zero threshold at roughly 400 kgCO₂e/t for 0% scrap falling to 50 at
100% scrap, and the A–E boundaries are multiples of that near-zero value
(×2 for A/B, ×3 for B/C, and so on). Without the scrap share a carbon figure
cannot be placed on the scale at all.

`EPD` has no scrap or recycled-content field, and the source declarations
mostly do not state one. BEAT's 92 ALCBT steel EPDs span 0.76–3.45 kgCO₂e/kg,
and that spread is largely scrap-based EAF against BF-BOF — which is to say,
it is largely the scrap share. Inferring the scrap share back out of the
carbon number and then rating on both would be circular.

**If this is revisited:** it needs a migration adding `scrap_content` to `EPD`,
and someone reading the figure out of each source PDF. Rating on carbon alone
would systematically mislabel EAF steel and must not be presented as LESS.
