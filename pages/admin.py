from django.contrib import admin
from .models.epd import MaterialCategory, EPD
from .models.assembly import Product, Assembly
from .models.building import Building

# Register your models here.
admin.site.register(MaterialCategory)
admin.site.register(EPD)
admin.site.register(Product)
admin.site.register(Assembly)
admin.site.register(Building)
