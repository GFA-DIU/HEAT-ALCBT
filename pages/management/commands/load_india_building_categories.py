from django.core.management.base import BaseCommand
from django.db import transaction

from cities_light.models import Country
from pages.models.building import BuildingCategory, BuildingSubcategory, CategorySubcategory, Building

# Full India-specific category/subcategory structure per client spec.
# Mixed-use building has no distinct subcategories so we use itself as the single sub-option.
INDIA_CATEGORIES = [
    ("Hospitality",         ["No-star Hotels", "Resort", "Star Hotel"]),
    ("Health care",         ["Hospital", "Out-patient Healthcare"]),
    ("Assembly",            ["Theatre", "Transport Service Facilities", "Multiplex"]),
    ("Office/Business",     ["24-hour use", "Day time use"]),
    ("Educational",         ["Schools", "College", "Universities", "Training institutes"]),
    ("Shopping complex",    ["Shopping malls", "Stand-alone Retails", "Open Gallery Malls", "Super Markets"]),
    ("Mixed-use building",  ["Mixed-use building"]),
    ("Homes",               ["Low income", "Middle income", "High income"]),
    ("Apartments",          ["Low income", "Middle income", "High income", "Serviced apartment"]),
]

# Remapping: (old_global_category, old_global_sub, new_india_category, new_india_sub)
# old_global_sub=None matches any subcategory under that category (used for Mixed Use).
REMAP = [
    ("Hotels",      "1 star",                       "Hospitality",       "No-star Hotels"),
    ("Hotels",      "2 star",                       "Hospitality",       "Star Hotel"),
    ("Hotels",      "3 star",                       "Hospitality",       "Star Hotel"),
    ("Hotels",      "4 star",                       "Hospitality",       "Star Hotel"),
    ("Hotels",      "5 star",                       "Hospitality",       "Star Hotel"),
    ("Resorts",     "1 star",                       "Hospitality",       "Resort"),
    ("Resorts",     "2 star",                       "Hospitality",       "Resort"),
    ("Resorts",     "3 star",                       "Hospitality",       "Resort"),
    ("Resorts",     "4 star",                       "Hospitality",       "Resort"),
    ("Resorts",     "5 star",                       "Hospitality",       "Resort"),
    ("Office",      "Grade A",                      "Office/Business",   "Day time use"),
    ("Office",      "Grade B",                      "Office/Business",   "Day time use"),
    ("Office",      "Grade C",                      "Office/Business",   "24-hour use"),
    ("Retail",      "Shopping Mall",                "Shopping complex",  "Shopping malls"),
    ("Retail",      "Department Store",             "Shopping complex",  "Stand-alone Retails"),
    ("Retail",      "Non-food Big Box Retail",      "Shopping complex",  "Stand-alone Retails"),
    ("Retail",      "Supermarket",                  "Shopping complex",  "Super Markets"),
    ("Healthcare",  "Private Hospital",             "Health care",       "Hospital"),
    ("Healthcare",  "Public Hospital",              "Health care",       "Hospital"),
    ("Healthcare",  "Multi-specialty Hospital",     "Health care",       "Hospital"),
    ("Healthcare",  "Teaching Hospital",            "Health care",       "Hospital"),
    ("Healthcare",  "Eye Hospital",                 "Health care",       "Hospital"),
    ("Healthcare",  "Dental Hospital",              "Health care",       "Hospital"),
    ("Healthcare",  "Clinics",                      "Health care",       "Out-patient Healthcare"),
    ("Healthcare",  "Diagnostic Center",            "Health care",       "Out-patient Healthcare"),
    ("Healthcare",  "Nursing homes",                "Health care",       "Out-patient Healthcare"),
    ("Education",   "Preschool",                    "Educational",       "Schools"),
    ("Education",   "School",                       "Educational",       "Schools"),
    ("Education",   "University",                   "Educational",       "Universities"),
    ("Education",   "Sports Facilities",            "Educational",       "Training institutes"),
    ("Education",   "Other Educational Facilities", "Educational",       "Training institutes"),
    ("Homes",       "Low income",                   "Homes",             "Low income"),
    ("Homes",       "Middle income",                "Homes",             "Middle income"),
    ("Homes",       "High income",                  "Homes",             "High income"),
    ("Apartments",  "Low income",                   "Apartments",        "Low income"),
    ("Apartments",  "Middle income",                "Apartments",        "Middle income"),
    ("Apartments",  "High income",                  "Apartments",        "High income"),
    ("Mixed Use",   None,                           "Mixed-use building","Mixed-use building"),
]


class Command(BaseCommand):
    help = "Seed India-specific building categories and remap existing India buildings to them"

    def handle(self, *args, **options):
        try:
            india = Country.objects.get(code2="IN")
        except Country.DoesNotExist:
            self.stderr.write(self.style.ERROR("India not found — run 'python manage.py cities_light' first."))
            return

        with transaction.atomic():
            self._seed_categories(india)
            self._remap_buildings(india)

        self.stdout.write(self.style.SUCCESS("Done: India building categories loaded and existing buildings remapped."))

    def _seed_categories(self, india):
        self.stdout.write("Seeding India categories...")
        for cat_name, sub_names in INDIA_CATEGORIES:
            category, _ = BuildingCategory.objects.get_or_create(name=cat_name)
            for sub_name in sub_names:
                subcategory, _ = BuildingSubcategory.objects.get_or_create(name=sub_name)
                _, created = CategorySubcategory.objects.get_or_create(
                    category=category,
                    subcategory=subcategory,
                    country=india,
                )
                self.stdout.write(f"  {'Created' if created else 'Exists ':6} {cat_name} / {sub_name}")

    def _remap_buildings(self, india):
        self.stdout.write("Remapping existing India buildings...")
        indian_buildings = Building.objects.filter(country=india)
        total = 0

        for old_cat_name, old_sub_name, new_cat_name, new_sub_name in REMAP:
            # Find old global CategorySubcategory (country=NULL)
            old_qs = CategorySubcategory.objects.filter(
                category__name=old_cat_name,
                country__isnull=True,
            )
            if old_sub_name:
                old_qs = old_qs.filter(subcategory__name=old_sub_name)

            if not old_qs.exists():
                continue

            # Find new India-specific CategorySubcategory
            try:
                new_cs = CategorySubcategory.objects.get(
                    category__name=new_cat_name,
                    subcategory__name=new_sub_name,
                    country=india,
                )
            except CategorySubcategory.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  Target not found, skipping: {new_cat_name} / {new_sub_name}"
                ))
                continue

            for old_cs in old_qs:
                count = indian_buildings.filter(category=old_cs).update(category=new_cs)
                if count:
                    self.stdout.write(
                        f"  Remapped {count:3} building(s): "
                        f"{old_cat_name}/{old_sub_name} → {new_cat_name}/{new_sub_name}"
                    )
                    total += count

        self.stdout.write(f"Total buildings remapped: {total}")
