# EPD accuracy review, 2 November 2026

Prompted by a question that looked small: the UltraTech cement EPD could not
be found in BEAT. It is there. What followed was a check of whether the rest
of the India catalogue is accurate.

**Status: findings only. Section 4 is not fixed and should not be fixed
without a decision.**

---

## 1. The UltraTech EPD is correct

`EPD-IES-0005019:001 (S-P-05019)`, UltraTech Cement Ltd., India, valid to
1 August 2027. BEAT holds it as four records, one per cement type. Every
figure was checked against the published document
(`Final_EPD_Ultratech_Cement_4 August 2022.pdf`, 22 pages):

| Type | EPD, GWP-total A1-A3 | BEAT | |
|---|---|---|---|
| OPC | 9.96E+02 = 996 | 996 | ✓ |
| PPC | 7.10E+02 = 710 | 710 | ✓ |
| PCC | 5.41E+02 = 541 | 541 | ✓ |
| PSC | 4.87E+02 = 487 | 487 | ✓ |

Also confirmed: the declared unit is "1000 kg each of OPC, PPC, PSC, PCC",
matching BEAT's kg x 1000. PENRT A1-A3 for OPC is 5,960 MJ, which is what
BEAT stores, and is NOT the ADPF figure of 5,950 sitting beside it in the
same table. The EPD declares **A1-A3 only**: A4, A5, B1-B7, C1-C4 and D are
all marked MND, so BEAT carrying no downstream stages for these is correct
rather than missing. Scope is 22 plants covering 67% of UltraTech's
production volume.

**The fault was metadata, not carbon.** The manufacturer field was empty, so
searching "UltraTech" returned nothing, and only one of the four carried a
brand in its title, which named the parent group Aditya Birla rather than the
registered owner.

## 2. What was changed

Each of the four now reads with the brand, and the published title is kept in
`source_name` so any figure can still be traced to the document it came from:

| Now | Published title, retained |
|---|---|
| UltraTech Ordinary Portland Cement (OPC) | Aditya Birla Ordinary Portland Cement (OPC) |
| UltraTech Pozzolana Portland Cement (PPC) | Portland Pozzolano Cement (PPC) |
| UltraTech Portland Composite Cement (PCC) | Portland Composite Cement (PCC) |
| UltraTech Portland Slag Cement (PSC) | Portland Slag Cement (PSC) |

Three code changes to `EPD.display_name`, all covered by tests:

1. The maker is no longer repeated when the title already names it. 39 India
   records read "Hardtop XP II, Jotun India Private Limited - Jotun A/S".
   Matching requires **every** word of the maker's name, not the first: the
   first-word rule would have hidden "Steel Authority of India Limited"
   behind a material called "Steel sheet", which is a different company.
2. A maker is now shown even when no `material_name` was split out. Nine
   records are titled "Xtend", "Stonix", "OPOS" or "Building", and the early
   return hid the only identifying detail they had.
3. 180 of 217 India EPDs that had no manufacturer now have one, every value
   taken from a published source rather than inferred. The remaining 37 are
   left empty on purpose; see section 5.

## 3. The catalogue was checked, not assumed

192 India EPDs carry a dataset UUID that can be traced to the offline
ECO-Platform archive, which holds the publisher's own A1-A3 figure and
declared unit.

| | |
|---|---|
| Traceable to a published dataset | 192 |
| **Agree on value and unit, within 1%** | **183** |
| Disagree | 9 |
| Disagree on declared unit | **0** |

That is a good result. Every one of the 9 is explained by section 4, not by a
mistyped figure.

One warning for anyone repeating this: the archive states GWP for the whole
declared amount, while `get_gwp_impact_sum` divides by it. Comparing the two
directly reports every steel EPD as wrong by a factor of a thousand. The
first run of this audit did exactly that and produced 73 false positives.

## 4. The rounding defect is still live

`EPD.get_gwp_impact_sum` rounds the impact to two decimals **before** dividing
by the declared amount:

```python
rounded = round(epdimpact.value, 2)
return Decimal(rounded) / self.declared_amount
```

This is the defect `AGENTS.md` rule 4 describes, and it is still in the code.
Measured against production, over all 5,423 GWP A1-A3 impact rows:

| | |
|---|---|
| Rounded to **zero**, from a non-zero published value | **41** |
| Changed by more than 1% | **350** |

An EPD declared per kg or per m2 has a small raw value, so two decimals throw
away a large share of it. `0.0011` becomes `0.00`: the material then
contributes no carbon at all, which is the kind of figure nobody questions
because it looks like an absence rather than an error. Per tonne EPDs are
unaffected, which is why this has survived.

It is **not** display-only. Callers include
`pages/scripts/a4a5/construction.py` (A4 transport and A5 waste),
`apply_gcca_concrete_labels.py` (the A-G concrete rating), and the structural
and template views.

**Not fixed here.** Removing the rounding changes live carbon figures on an
unknown number of buildings, which needs the blast radius counted first and a
decision about buildings whose reported carbon would move. It should be its
own task.

## 5. What is deliberately left undone

**37 India EPDs still have no manufacturer.** Their sources are environdec
library pages (15), a Scribd copy of the ACC cement EPD (8), the environdec
file API (7), data.environdec (4), Vetrotech (2) and EPD Norway (1). Several
name the maker plainly in the title, "Asian Paints Weathercoat Ultra" among
them, but reading a maker off a product name is a guess, and once saved a
guess is indistinguishable from a sourced value. They need their own source
pages read.

**2,863 EPDs outside India still have no manufacturer**, 2,652 of them German
Okobaudat records. The same command handles them once their makers are
sourced.

**A machine check could not reach these source pages.** The development
machine runs TLS interception, so direct HTTPS to the ILCD nodes fails
certificate validation. The documented workaround is a combined CA bundle via
`REQUESTS_CA_BUNDLE`, not disabling verification.

---

*Evidence: `Downloads/india_epd_manufacturer_proposal.csv` (217 rows, maker
and its source per record), `Downloads/india_epd_accuracy_audit.csv` (the 9
disagreements), and the EPD PDF named above.*

---

## 6. Catalogue coverage, measured against the live registry

Added after colleagues reported that India was missing EPDs. The whole
"Construction products" listing was re-harvested from EPD International for
all five ALCBT countries on 2 November 2026, with TLS verification intact.

| Country | Published | In BEAT | **Missing** |
|---|---|---|---|
| India | 384 | 232 | **152** |
| Thailand | 214 | 140 | **74** |
| Vietnam | 138 | 89 | **49** |
| Indonesia | 36 | 32 | **4** |
| Cambodia | 2 | 2 | 0 |
| **Total** | **774** | **495** | **279** |

The colleagues were right and were understating it. An earlier count of 73
missing for India was measured against our own 2026 harvest, which is stale;
against the live registry it is 152.

Most of the gap is recent registrations, with validity dates running to 2031,
so this is a catalogue that moved on rather than an import that failed. Only
5 of the 774 published EPDs are expired.

Notable by country: Thailand is missing 19 INSEE mortar and cement products;
Vietnam is missing VINH TUONG boards, Weber mortars, slag cement and GGBFS.
All are ordinary building materials, not edge cases.

### What India's 152 are

| | |
|---|---|
| Clear building materials, proposed for import | **98** |
| Cannot be classified from the name, needs a human | **38** |
| Out of scope for a building tool (furniture, PV) | 16 |

Steel and metal account for 50 and gypsum/boards for 26. Note that
environdec's "Construction products" category also contains office furniture,
safes and solar modules, which is why a straight import of the category would
put rows in the material picker that nobody will choose.

### Identifiers: how the 232 were found

| Route | Matched |
|---|---|
| The EPD's UUID in the source URL | 161 |
| environdec library id | 67 |
| Product name | 4 |
| **Registration number** | **0** |

No BEAT record anywhere stores its EPD registration number. That is the
structural reason a record can become unfindable: when a URL moves, the only
route back is guessing by name. Storing the registration number on import
would fix this permanently and costs nothing.

*Files: `environdec_<CC>_construction_2026-11-02.csv` (the full listing per
country), `<CC>_epds_missing_2026-11-02.csv`, `india_epd_import_list_2026-11-02.csv`
(the 152 split into import / review / skip).*
