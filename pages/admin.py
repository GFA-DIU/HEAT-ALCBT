from django.contrib import admin
from .models.epd import MaterialCategory, EPD, EPDImpact, Impact
from .models.assembly import Product, Assembly
from .models.building import Building

# Register your models here.

# Inline for Many-to-Many (impacts in EPD)
class ImpactsInline(admin.TabularInline):  # or admin.StackedInline
    model = EPD.impacts.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display

# Inline for Many-to-Many (products in Assembly)
class ProductsInline(admin.TabularInline):  # or admin.StackedInline
    model = Assembly.products.through  # Use the through model for the many-to-many field
    extra = 1  # Number of empty rows to display

# Custom admin for EPD
class EPDAdmin(admin.ModelAdmin):
    inlines = [ImpactsInline]  # Add the inline for impacts
    list_display = ["name", "country", "category"]  # Show all fields in list view

# Custom admin for Assembly
class AssemblyAdmin(admin.ModelAdmin):
    inlines = [ProductsInline]  # Add the inline for products
    list_display = ["name", "country", "classification"]
    # list_display = [field.name for field in Assembly._meta.fields]  # Show all fields in list view

# Register your models with custom admin
admin.site.register(MaterialCategory)
admin.site.register(EPD, EPDAdmin)
admin.site.register(Product)
admin.site.register(Assembly, AssemblyAdmin)
admin.site.register(Building)
admin.site.register(EPDImpact)
admin.site.register(Impact)
