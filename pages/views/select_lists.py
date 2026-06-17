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

Hot Water System Options:
- ?hot_water_system_types      - Get hot water system type options
- ?fuel_types                  - Get fuel type options
- ?energy_efficiency_label_types - Get energy efficiency label options

Cooling System Options:
- ?refrigerant_types           - Get refrigerant type options

Lighting System Options:
- ?room_types                  - Get room type options
- ?lighting_bulb_types         - Get lighting bulb type options
"""

import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from accounts.models import CustomCity, CustomRegion
from pages.models.assembly import AssemblyTechnique
from pages.models.building import (BuildingCategory, CategorySubcategory,
                                   ClimateZone, CoolingType, HeatingType,
                                   LightingType)
from pages.models.epd import MaterialCategory, Unit
from pages.models.building_operation.hot_water import (HotWaterSystemType, FuelType,
                                                       EnergyEfficiencyLabelType)
from pages.models.building_operation.lighting import RoomType, LightingBulbType
from pages.models.building_operation.chilling import RefrigerantType
from pages.models.building_operation.ventilation import VentilationType, VentilationCapacity

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def select_lists(request):
    if request.GET.get("building_category"):
        m = request.GET.get("building_category")
        category_id = int(m)
        country_id = request.GET.get("country")
        try:
            country_id = int(country_id)
        except (TypeError, ValueError):
            country_id = None

        if country_id:
            subcategories = CategorySubcategory.objects.filter(
                category_id=category_id, country_id=country_id
            ).select_related('subcategory').order_by('subcategory__name')
            if not subcategories.exists():
                subcategories = CategorySubcategory.objects.filter(
                    category_id=category_id, country__isnull=True
                ).select_related('subcategory').order_by('subcategory__name')
        else:
            subcategories = CategorySubcategory.objects.filter(
                category_id=category_id
            ).select_related('subcategory').order_by('subcategory__name')

        seen_ids = set()
        items = []
        for cs in subcategories:
            if cs.subcategory_id not in seen_ids:
                seen_ids.add(cs.subcategory_id)
                items.append(cs.subcategory)
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Pick a building sub-type"},
        )
    elif m := request.GET.get("country"):
        # Handle empty or invalid country values
        if not m or m in ['', '""', '\\"\\"']:
            return render(
                request,
                "pages/utils/select_list.html",
                {"items": [], "default_text": "Select a region"},
            )
        try:
            country_id = int(m)
        except ValueError:
            logger.error(f"Invalid country ID: {m}")
            return render(
                request,
                "pages/utils/select_list.html",
                {"items": [], "default_text": "Select a region"},
            )
        regions = CustomRegion.objects.filter(country=country_id).order_by("name")
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": regions, "default_text": "Select a region"},
        )
    elif m := request.GET.get("region"):
        if not m or m in ['', '""', '\\"\\"']:
            return render(
                request,
                "pages/utils/select_list.html",
                {"items": [], "default_text": "Select a city"},
            )
        try:
            region_id = int(m)
        except ValueError:
            logger.error(f"Invalid region ID: {m}")
            return render(
                request,
                "pages/utils/select_list.html",
                {"items": [], "default_text": "Select a city"},
            )
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
        country_id = request.GET.get("country")
        try:
            country_id = int(country_id)
        except (TypeError, ValueError):
            country_id = None

        if country_id:
            # Get categories that have country-specific entries for this country
            country_categories = BuildingCategory.objects.filter(
                categorysubcategory__country_id=country_id
            ).distinct().order_by("name")
            if country_categories.exists():
                categories = country_categories
            else:
                # Fall back to global (country=null) categories
                categories = BuildingCategory.objects.filter(
                    categorysubcategory__country__isnull=True
                ).distinct().order_by("name")
        else:
            categories = BuildingCategory.objects.all().order_by("name")

        return render(
            request,
            "pages/utils/select_list.html",
            {"items": categories, "default_text": "Select a building type"},
        )

    
    # Climate and System Choices
    elif request.GET.get("climate_zones"):
        from pages.models.climate_type import ClimateType
        items = [{"id": ct.name, "name": ct.name} for ct in ClimateType.objects.order_by("name")]
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

    elif request.GET.get("ventilation_capacity_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in VentilationCapacity.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select capacity unit"},
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

    # Hot Water System Options
    elif request.GET.get("hot_water_system_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in HotWaterSystemType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select hot water system type"},
        )

    elif request.GET.get("fuel_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in FuelType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select fuel type"},
        )

    elif request.GET.get("energy_efficiency_label_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in EnergyEfficiencyLabelType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select energy efficiency label"},
        )

    # Refrigerant Types (for cooling systems)
    elif request.GET.get("refrigerant_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in RefrigerantType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select refrigerant type"},
        )

    # Room Types (for lighting systems)
    elif request.GET.get("room_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in RoomType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select room type"},
        )

    # Lighting Bulb Types
    elif request.GET.get("lighting_bulb_types"):
        items = [{"id": choice[0], "name": choice[1]} for choice in LightingBulbType.choices]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select lighting bulb type"},
        )

    # Full page load for GET request
    return render(
        request,
        "pages/utils/select_list.html",
        {"items": [], "default_text": ""},
    )
