from django.contrib import admin
from .models import (
    MaterialCategory,
    Material,
    StructuralComponent,
    BuildingSubcategory,
    BuildingCategory,
    Building,
)

# Register your models here.
admin.site.register(MaterialCategory)
admin.site.register(Material)
admin.site.register(StructuralComponent)
admin.site.register(BuildingSubcategory)
admin.site.register(BuildingCategory)
admin.site.register(Building)
