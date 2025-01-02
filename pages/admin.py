from django.contrib import admin
from .models.epd import MaterialCategory, EPD, EPDImpact, Impact
from .models.assembly import Product, Assembly, AssemblyCategory, AssemblyTechnique
from .models.building import Building, BuildingSubcategory

# Register your models here.

# Inline for Many-to-Many (impacts in EPD)
class ImpactsInline(admin.TabularInline):  # or admin.StackedInline
    model = EPD.impacts.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display

# Inline for Many-to-Many (products in Assembly)
class ProductsInline(admin.TabularInline):  # or admin.StackedInline
    model = Assembly.products.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display
  

class AssemblyImpact(admin.TabularInline):
    model = Assembly.impacts.through  # Use the through model for the many-to-many field
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

# Custom admin for EPD
class EPDAdmin(admin.ModelAdmin):
    inlines = [ImpactsInline]  # Add the inline for impacts
    list_display = ["name", "country", "category"]  # Show all fields in list view

# Custom admin for Assembly
class AssemblyAdmin(admin.ModelAdmin):
    inlines = [ProductsInline, AssemblyImpact]  # Add the inline for products
    list_display = ["name", "country", "classification", "id"]


# Custom admin for AssemblyCategory
class AssemblyCategoryAdmin(admin.ModelAdmin):
    inlines = [AssembliesClassificationInline]  # Add the inline for techniques
    list_display = ["name", "tag"]

# Custom admin for Building
class BuildingAdmin(admin.ModelAdmin):
    inlines = [AssembliesInline, AssembliesSimulationInline]  # Add the inline for products
    list_display = ["name", "country", "category"]

# Register your models with custom admin
admin.site.register(MaterialCategory)
admin.site.register(EPD, EPDAdmin)
admin.site.register(Product)
admin.site.register(Assembly, AssemblyAdmin)
admin.site.register(AssemblyCategory, AssemblyCategoryAdmin)
admin.site.register(AssemblyTechnique)
admin.site.register(Building, BuildingAdmin)
admin.site.register(BuildingSubcategory)
admin.site.register(EPDImpact)
admin.site.register(Impact)
