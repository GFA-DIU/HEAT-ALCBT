from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models.epd import MaterialCategory, EPD, Impact
from .models.assembly import Assembly, AssemblyCategory, AssemblyTechnique
from .models.building import Building, BuildingCategory, BuildingSubcategory, CategorySubcategory

# Register your models here.

# Inline for Many-to-Many (impacts in EPD)
class ImpactsInline(admin.TabularInline):  # or admin.StackedInline
    model = EPD.impacts.through  # Use the through model for the many-to-many field
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

# Custom admin for EPD
class EPDAdmin(admin.ModelAdmin):
    inlines = [ImpactsInline]  # Add the inline for impacts
    list_display = ["name", "country", "category"]  # Show all fields in list view

# Custom admin for Assembly
class AssemblyAdmin(admin.ModelAdmin):
    inlines = [ProductsInline]  # Add the inline for products
    list_display = ["name", "country", "classification", "id"]


# Custom admin for AssemblyCategory
class AssemblyCategoryAdmin(admin.ModelAdmin):
    inlines = [AssembliesClassificationInline]  # Add the inline for techniques
    list_display = ["name", "tag"]

# Custom admin for Building
class BuildingAdmin(admin.ModelAdmin):
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
    ordering    = ("category_id",)

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
