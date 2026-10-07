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
from pages.models.assembly import AssemblyCategory, AssemblyTechnique
from pages.models.building import (BuildingCategory, CategorySubcategory,
                                   ClimateZone, CoolingType, HeatingType,
                                   LightingType)
from pages.models.epd import MaterialCategory, Unit
from pages.models.building_operation.hot_water import (HotWaterSystemType, FuelType,
                                                       EnergyEfficiencyLabelType)
from pages.models.building_operation.lighting import (RoomType, LightingBulbType,
                                                      LightingSpaceType, LightingReference)
from pages.models.building_operation.chilling import RefrigerantType
from pages.models.building_operation.ventilation import VentilationType, VentilationCapacity

logger = logging.getLogger(__name__)



def _lighting_room_type_items(building_uuid):
    """Room-type options for the lighting step, narrowed to the building type.

    SNI 6197:2020 lists 99 rooms; most are irrelevant to any one building, and
    nine of them (toilet, stairs, kitchen ...) repeat verbatim across building
    categories. Those are held once as `is_common` and shown everywhere, so an
    office sees ~14 options rather than 99 or the old fixed six.

    Falls back to every non-legacy space when the building or its category
    cannot be determined, which is better than showing nothing.
    """
    from pages.models.building import Building

    qs = LightingSpaceType.objects.filter(legacy=False)
    category = None
    if building_uuid:
        building = (
            Building.objects.filter(uuid=building_uuid)
            .select_related("category__category")
            .first()
        )
        if building and building.category and building.category.category:
            category = building.category.category.name

    if category:
        qs = qs.filter(Q(is_common=True) | Q(building_categories__contains=[category]))

    # The country's own standard supplies the reference shown beside each room.
    refs = {}
    if building_uuid:
        building = Building.objects.filter(uuid=building_uuid).select_related("country").first()
        if building and building.country:
            refs = {
                r.space_type_id: r
                for r in LightingReference.objects.filter(
                    country=building.country, basis=LightingReference.Basis.ROOM
                )
            }

    items = []
    for st in qs:
        label = st.name
        ref = refs.get(st.id)
        if ref and ref.lpd_w_m2:
            label = f"{st.name} — {ref.lpd_w_m2} W/m²"
        items.append({"id": st.code, "name": label})
    return items


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
        # When lat/lon are supplied (map pin), expose them as data-* attributes
        # on each option so the frontend can pick the nearest city to the pin.
        try:
            lat = float(request.GET.get("lat")) if request.GET.get("lat") else None
            lon = float(request.GET.get("lon")) if request.GET.get("lon") else None
        except (TypeError, ValueError):
            lat = lon = None
        include_coords = lat is not None and lon is not None
        return render(
            request,
            "pages/utils/select_list.html",
            {
                "items": cities,
                "default_text": "Select a city",
                "include_coords": include_coords,
            },
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

    elif m := request.GET.get("building_part"):
        # Components within the chosen family. Pass as {id, name} dicts so the
        # template shows the clean component name (not the "tag - name" __str__).
        categories = AssemblyCategory.objects.filter(family=m).order_by("tag")
        items = [{"id": c.id, "name": c.name} for c in categories]
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": items, "default_text": "Select a component"},
        )

    elif m := request.GET.get("assembly_category"):
        assembly_category_id = int(m)
        techniques = AssemblyTechnique.objects.filter(
            categories__id=assembly_category_id
        ).order_by("name")
        return render(
            request,
            "pages/utils/select_list.html",
            {"items": techniques, "default_text": "Select a technique"},
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

    # One room's reference value, as JSON, for the benchmark line under the LPD
    # field. Returns nothing usable for a country with no standard (Cambodia),
    # which the caller treats as "no benchmark" rather than an error.
    elif request.GET.get("lighting_reference"):
        from django.http import JsonResponse
        from pages.models.building import Building

        code = request.GET.get("code") or ""
        building = (
            Building.objects.filter(uuid=request.GET.get("building_uuid") or None)
            .select_related("country", "category__category").first()
        )
        out = {"has_reference": False}
        if building and building.country and code:
            ref = LightingReference.objects.filter(
                country=building.country, space_type__code=code,
                basis=LightingReference.Basis.ROOM,
            ).first()
            if ref is None:
                # Countries whose standard is whole-building only (Vietnam,
                # Thailand) still have a limit worth showing, but it applies to
                # the building average rather than this room.
                cat = (building.category.category.name
                       if building.category and building.category.category else None)
                if cat:
                    ref = LightingReference.objects.filter(
                        country=building.country, building_category=cat,
                        basis=LightingReference.Basis.BUILDING,
                    ).first()
            if ref and ref.lpd_w_m2:
                out = {
                    "has_reference": True,
                    "lpd_w_m2": float(ref.lpd_w_m2),
                    "lux": ref.lux,
                    "standard": ref.standard,
                    "basis": ref.basis,
                    "country": building.country.name,
                }
        return JsonResponse(out)

    # Room Types (for lighting systems)
    #
    # Filtered by the building type the user already chose, so someone modelling
    # a school is not offered "Hospital: Patient Room". Spaces that occur in
    # every building (toilet, stairs, parking) come first, then the ones
    # specific to that building type. Legacy codes are excluded from new
    # entries but still resolve for records that already hold them.
    elif request.GET.get("room_types"):
        items = _lighting_room_type_items(request.GET.get("building_uuid"))
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
