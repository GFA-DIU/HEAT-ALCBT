"""
Select Lists API Endpoint

Available endpoints for /select_lists/:

Geographic Data:
- ?country=<id>                 - Get regions for country
- ?region=<id>                  - Get cities for region

Material Categories:
- ?category=<id>                - Get material subcategories
- ?subcategory=<id>             - Get child categories
- ?assembly_category=<id>       - Get assembly techniques

Building Types:
- ?building_categories          - Get all building categories
- ?building_category=<id>       - Get subcategories (apartment types)

System Types:
- ?climate_zones               - Get climate zone options
- ?heating_types               - Get heating system options
- ?cooling_types               - Get cooling system options
- ?ventilation_types           - Get ventilation system options
- ?lighting_types              - Get lighting system options

Units:
- ?temperature_units           - Get temperature unit options (°C, °F)
- ?power_units                 - Get power unit options (kW)
- ?cooling_capacity_units      - Get cooling capacity units (kW, TR)
- ?airflow_units               - Get airflow units (m³/h, CFM)
"""

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from accounts.models import CustomCity, CustomRegion
from pages.models.assembly import AssemblyTechnique
from pages.models.building import (BuildingCategory, CategorySubcategory,
                                   ClimateZone, CoolingType, HeatingType,
                                   LightingType, VentilationType)
from pages.models.epd import MaterialCategory, Unit

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def select_lists(request):
    if m := request.GET.get("country"):
        country_id = int(m)
        regions = CustomRegion.objects.filter(country=country_id).order_by("name")
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": regions, "default_text": "Select a region"},
        )
    elif m := request.GET.get("region"):
        region_id = int(m)
        cities = CustomCity.objects.filter(region=region_id).order_by("name")
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": cities, "default_text": "Select a city"},
        )
    elif m := request.GET.get("category"):
        category_id = int(m)
        subcategories = MaterialCategory.objects.filter(
            level=2, parent=category_id
        ).order_by("name_en")
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": subcategories, "default_text": "Select a category"},
        )

    elif m := request.GET.get("subcategory"):
        subcategory_id = int(m)
        childcategories = MaterialCategory.objects.filter(
            level=3, parent=subcategory_id
        ).order_by("name_en")
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": childcategories, "default_text": "Select a subcategory"},
        )

    elif m := request.GET.get("assembly_category"):
        assembly_category_id = int(m)
        techniques = AssemblyTechnique.objects.filter(
            categories__id=assembly_category_id
        ).order_by("name")
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": techniques, "default_text": "Select a category"},
        )
    
    # Building Categories and Types
    elif request.GET.get("building_categories"):
        categories = BuildingCategory.objects.all().order_by("name")
        logging.info(f"Fetched {categories.count()} building categories.")
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": categories, "default_text": "Select a building type"},
        )
    
    elif m := request.GET.get("building_category"):
        category_id = int(m)
        subcategories = CategorySubcategory.objects.filter(
            category_id=category_id
        ).select_related('subcategory').order_by('subcategory__name')
        # Extract just the subcategory objects for the template
        items = [cs.subcategory for cs in subcategories]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select apartment type"},
        )
    
    # Climate and System Choices (TextChoices)
    elif request.GET.get("climate_zones"):
        # Convert TextChoices to objects with id and name for template compatibility
        items = [{"id": choice[0], "name": choice[1]} for choice in ClimateZone.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select climate type"},
        )
    
    elif request.GET.get("heating_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in HeatingType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select heating type"},
        )
    
    elif request.GET.get("cooling_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in CoolingType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select cooling type"},
        )
    
    elif request.GET.get("ventilation_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in VentilationType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select ventilation type"},
        )
    
    elif request.GET.get("lighting_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in LightingType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select lighting type"},
        )
    
    # Unit choices for different measurement types
    elif request.GET.get("temperature_units"):
        temp_units = [choice for choice in Unit.choices if choice[0] in (Unit.CELSIUS, Unit.FAHRENHEIT)]
        items = [{"id": choice[0], "name": choice[1]} for choice in temp_units]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select temperature unit"},
        )
    
    elif request.GET.get("power_units"):
        power_units = [choice for choice in Unit.choices if choice[0] in (Unit.KW,)]
        items = [{"id": choice[0], "name": choice[1]} for choice in power_units]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select power unit"},
        )
    
    elif request.GET.get("cooling_capacity_units"):
        cooling_units = [choice for choice in Unit.choices if choice[0] in (Unit.KW, Unit.TR)]
        items = [{"id": choice[0], "name": choice[1]} for choice in cooling_units]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select capacity unit"},
        )
    
    elif request.GET.get("airflow_units"):
        airflow_units = [choice for choice in Unit.choices if choice[0] in (Unit.M3_H, Unit.CFM)]
        items = [{"id": choice[0], "name": choice[1]} for choice in airflow_units]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select airflow unit"},
        )

    # Full page load for GET request
    return render(
        request,
        "pages/utils/select_list.html",
        {"items": [], "default_text": ""},
    )
