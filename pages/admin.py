from django import forms
from django.contrib import admin
from django.db.models import Q, Prefetch
from django.http import HttpResponse

from .models.epd import MaterialCategory, EPD, Impact, EPDImpact, Label, EPDLabel
from .models.assembly import Assembly, AssemblyCategory, AssemblyTechnique
from .models.building import Building, BuildingCategory, BuildingSubcategory
from .models.base import ALCBTCountryManager
from .scripts.Excel_export.export_EPDs_to_excel import to_excel_bytes


class CountryFieldMixin:
    # Mixin to handle country field querysets in admin
    use_all_countries = False
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "country":
            if self.use_all_countries:
                kwargs["queryset"] = ALCBTCountryManager.get_all_countries()
            else:
                kwargs["queryset"] = ALCBTCountryManager.get_alcbt_countries()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.site_header = "BEAT Admin"
admin.site.site_title = "BEAT Admin Portal"
admin.site.index_title = "Welcome to the BEAT Admin Area"
# Register your models here.

# Inline for Many-to-Many (impacts in EPD)
class ImpactsInline(admin.TabularInline):  # or admin.StackedInline
    model = EPD.impacts.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display

# Inline for Many-to-Many (labels in EPD)
class LabelsInline(admin.TabularInline):  # or admin.StackedInline
    model = EPDLabel
    extra = 1  # Number of empty rows to display

# Inline for Many-to-Many (products in Assembly)
class ProductsInline(admin.TabularInline):  # or admin.StackedInline
    model = Assembly.products.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display

class StructuralProductsInline(admin.TabularInline):
    model = Building.operational_components.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display
  
class StructuralProductsSimulationInline(admin.TabularInline):
    model = Building.simulated_operational_components.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display
    
class AssembliesClassificationInline(admin.TabularInline):
    model = AssemblyCategory.techniques.through


# Inline for Many-to-Many (assemblies in Building)
class AssembliesInline(admin.TabularInline):  # or admin.StackedInline
    model = Building.structural_components.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display


# Inline for Many-to-Many (assemblies in Building)
class AssembliesSimulationInline(admin.TabularInline):  # or admin.StackedInline
    model = Building.simulated_components.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display


class BuildingCategoryInline(admin.StackedInline):
    model = BuildingCategory.subcategories.through
    extra = 0


class TopLevelCategoryFilter(admin.SimpleListFilter):
    title = "Top-level category"        # Displayed in the sidebar
    parameter_name = "top_cat"          # URL query parameter

    def lookups(self, request, model_admin):
        # return only those MaterialCategorys whose level == 1
        qs = MaterialCategory.objects.filter(level=1).order_by("name_en")
        return [(c.pk, c.name_en) for c in qs]

    def queryset(self, request, queryset):
        if self.value():
            # match any EPD whose category_id == "X" (the root)
            # or starts with "X." (all its descendants)
            val = self.value()
            return queryset.filter(
                Q(category__parent__pk=val) |
                Q(category__parent__parent__pk=val)
            )
        return queryset


@admin.action(description="Export selected EPDs to Excel.")
def export_epds_action(modeladmin, request, queryset):
    queryset = (
        queryset.select_related(
            "country",
            "city",
            "category",
            "category__parent",
            "category__parent__parent",
        )
        # grab all the reverse/M2M data in one shot each
        .prefetch_related(
            # impacts are through the EPDImpact intermediary; prefetch both sides
            Prefetch(
                "epdimpact_set",
                queryset=EPDImpact.objects.select_related("impact"),
                to_attr="all_impacts",
            ),
            # if you ever do `epd.impacts.all()`, you can also prefetch that:
            "impacts",
        )
    )
    excel_data = to_excel_bytes(queryset)
    # Build response
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="export.xlsx"'
    return response


# Custom admin for EPD
class EPDAdmin(CountryFieldMixin, admin.ModelAdmin):
    use_all_countries = True
    inlines = [ImpactsInline, LabelsInline]  # Add the inline for impacts and labels
    list_display = ["name", "country", "category", "type"]  # Show all fields in list view
    list_display_links = ["name"]
    ordering = ["name", "country"]
    list_filter  = [
        "country",
        "type",
        TopLevelCategoryFilter,  # ← our custom filter
    ]
    search_fields = (
        "name",
        "category__name_en",
    )    
    actions = [export_epds_action]

    
# Custom admin for Assembly
class AssemblyAdmin(CountryFieldMixin, admin.ModelAdmin):
    use_all_countries = False
    inlines = [ProductsInline]  # Add the inline for products
    list_display = ["name", "country", "classification", "id"]


# Custom admin for AssemblyCategory
class AssemblyCategoryAdmin(admin.ModelAdmin):
    inlines = [AssembliesClassificationInline]  # Add the inline for techniques
    list_display = ["name", "tag"]

# Custom admin for Building
class BuildingAdmin(CountryFieldMixin, admin.ModelAdmin):
    use_all_countries = False  # Building admin shows only ALCBT countries
    inlines = [AssembliesInline, AssembliesSimulationInline, StructuralProductsInline, StructuralProductsSimulationInline]  # Add the inline for products
    list_display = ["name", "country", "category"]
    
class BuildingCategoryAdmin(admin.ModelAdmin):
    inlines = [BuildingCategoryInline]
    list_dispaly = ["name"]

class ChildCategoryInline(admin.TabularInline):
    model = MaterialCategory
    fk_name = "parent"
    extra = 0

class MaterialCategoryAdmin(admin.ModelAdmin):
    inlines = [ChildCategoryInline]
    list_display = ("category_id", "name_en", "parent")
    list_display_links = ["name_en"]
    ordering    = ("category_id",)

# Custom admin for Label
class LabelAdmin(admin.ModelAdmin):
    list_display = ["name", "source", "scale_type"]
    list_display_links = ["name"]
    ordering = ["name"]
    list_filter = ["scale_type", "source"]
    search_fields = ("name", "source")


# Register your models with custom admin
admin.site.register(MaterialCategory, MaterialCategoryAdmin)
admin.site.register(EPD, EPDAdmin)
admin.site.register(Assembly, AssemblyAdmin)
admin.site.register(AssemblyCategory, AssemblyCategoryAdmin)
admin.site.register(AssemblyTechnique)
admin.site.register(Building, BuildingAdmin)
admin.site.register(BuildingCategory, BuildingCategoryAdmin)
admin.site.register(BuildingSubcategory)
admin.site.register(Impact)
admin.site.register(Label, LabelAdmin)
