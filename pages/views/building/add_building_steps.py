"""
Views for handling the multi-step building creation process.
Each step loads a template and provides necessary context data.
"""

import os as _os
import json
import logging
import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from cities_light.models import Country

from accounts.models import CustomCity, CustomRegion
from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import Assembly, StructuralProduct
from pages.models.base import ALCBTCountryManager
from pages.models.building import Building, BuildingAssembly, BuildingBoQFile, BuildingCategory, OperationalProduct, CategorySubcategory, ClimateZone
from pages.models.building_operation.energy_summary import EnergySummary
from pages.models.climate_type import ClimateType
from pages.models.epd import EPD, EPDImpact, EPDType, MaterialCategory
from pages.geo_lookup import resolve_building_location_fields
from pages.views.building.impact_calculation import calculate_impacts, ImpactCalculationError

logger = logging.getLogger(__name__)


def _resolve_and_apply_geo_fields(building):
    """
    Auto-populate building.climate_zone / building.seismic_zone from GPS coordinates
    (per BEAT spec: auto-fill when lat/lon + country are known, otherwise leave the
    fields for manual selection in the next step). Does not save() the building.

    Returns the resolve_building_location_fields() dict, or None if lat/lon/country
    weren't available to attempt a lookup.
    """
    if building.latitude is None or building.longitude is None or not building.country_id:
        return None

    geo_result = resolve_building_location_fields(
        building.latitude, building.longitude, building.country.name
    )
    if geo_result.get("climate_type"):
        building.climate_zone = ClimateType.objects.filter(name=geo_result["climate_type"]).first()
    if geo_result.get("seismic_zone"):
        building.seismic_zone = geo_result["seismic_zone"]
    return geo_result


@login_required
@require_http_methods(["GET"])
def building_step_view(request):
    """
    Main view for handling all building creation steps.
    Returns the appropriate template based on the step parameter.
    """
    step = request.GET.get("step")
    
    if not step:
        return JsonResponse({"error": "Step parameter is required"}, status=400)
    
    # Map steps to their handlers
    step_handlers = {
        # Building Information
        "building-information/building-name-location.html": handle_name_location_step,
        "building-information/building-details.html": handle_details_step,
        
        # Operational Details
        "operational-details/operational-schedule-temperature.html": handle_schedule_temp_step,
        "operational-details/cooling-system.html": handle_cooling_system_step,
        "operational-details/ventilation-system.html": handle_ventilation_system_step,
        "operational-details/lighting-system.html": handle_lighting_system_step,
        "operational-details/lift-escalator-system.html": handle_lift_escalator_step,
        "operational-details/hot-water-system.html": handle_hot_water_step,
        "operational-details/energy-consumption-summary.html": handle_energy_consumption_summary_step,  # Placeholder for energy summary step
        # Operational Data Entry
        "operational-data-entry/operational-data-entry.html": handle_operational_data_step,
        
        # Building Structural Components
        "building-structural-components/building-structural-components.html": handle_structural_components_step,
    }
    
    handler = step_handlers.get(step)
    if handler:
        return handler(request)
    
    return JsonResponse({"error": f"Unknown step: {step}"}, status=404)


# Step 1.1: Building Name & Location
def handle_name_location_step(request):
    """Provide countries and optionally pre-populated region/city for edit mode."""


    building_uuid = request.GET.get('building_uuid')

    context = {
        "countries": ALCBTCountryManager.get_alcbt_countries(),
        "regions": [],
        "cities": [],
        "selected_country": None,
        "selected_region": None,
        "selected_city": None,
        "building_data": None,
    }

    # Edit mode: pre-populate dependent selects from existing building
    if building_uuid:
        try:
            building = Building.objects.get(uuid=building_uuid, created_by=request.user)

            context["building_data"] = {
                "building_name": building.name,
                "address": building.street or "",
                "longitude": building.longitude,
                "latitude": building.latitude,
            }

            if building.country:
                context["selected_country"] = building.country_id
                context["regions"] = CustomRegion.objects.filter(
                    country=building.country
                ).order_by("name")

            if building.region:
                context["selected_region"] = building.region_id
                context["cities"] = CustomCity.objects.filter(
                    region=building.region
                ).order_by("name")

            if building.city:
                context["selected_city"] = building.city_id

        except Building.DoesNotExist:
            logger.warning(f"Building not found for edit: {building_uuid}")

    return render(
        request,
        "pages/add-building/components/building-information/building-name-location.html",
        context
    )


# Step 1.2: Building Details
def _get_building_categories_for_country(country_id):
    """Return building categories filtered for a country, falling back to global ones."""
    if country_id:
        country_cats = BuildingCategory.objects.filter(
            categorysubcategory__country_id=country_id
        ).distinct().order_by("name")
        if country_cats.exists():
            return country_cats
        return BuildingCategory.objects.filter(
            categorysubcategory__country__isnull=True
        ).distinct().order_by("name")
    return BuildingCategory.objects.all().order_by("name")


def handle_details_step(request):
    """Provide building categories and optionally pre-populated apartment types for edit mode."""

    building_uuid = request.GET.get('building_uuid')

    # country_id may be passed directly (new building flow) or read from building (edit flow)
    try:
        country_id = int(request.GET.get('country_id', ''))
    except (ValueError, TypeError):
        country_id = None

    is_india = False
    if country_id:
        try:
            is_india = Country.objects.filter(pk=country_id, code2="IN").exists()
        except Exception:
            pass

    context = {
        "building_categories": _get_building_categories_for_country(country_id),
        "apartment_types": [],
        "climate_zones": [{"id": ct.name, "name": ct.name} for ct in ClimateType.objects.order_by("name")],
        "selected_building_type": None,
        "selected_apartment_type": None,
        "selected_climate_type": None,
        "building_data": None,
        "country_id": country_id,
        "is_india": is_india,
    }

    # Edit mode: pre-populate dependent selects from existing building
    if building_uuid:
        try:
            building = Building.objects.get(uuid=building_uuid, created_by=request.user)


            cert_info = None
            if building.certification_file:
                cert_info = {
                    "name": _os.path.basename(building.certification_file.name),
                    "url": f"/building/files/serve/?building_uuid={building.uuid}&type=certification",
                }
            drawing_info = [
                {
                    "id": bf.id,
                    "name": bf.original_filename or _os.path.basename(bf.file.name),
                    "url": f"/building/files/serve/?building_uuid={building.uuid}&type=boq&file_id={bf.id}",
                }
                for bf in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_DRAWING)
            ]
            boq_info = [
                {
                    "id": bf.id,
                    "name": bf.original_filename or _os.path.basename(bf.file.name),
                    "url": f"/building/files/serve/?building_uuid={building.uuid}&type=boq&file_id={bf.id}",
                }
                for bf in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_BOQ)
            ]

            # Pre-fill text fields
            energy_summary = None
            try:
                energy_summary = building.energy_summary
            except EnergySummary.DoesNotExist:
                pass

            context["building_data"] = {
                "assessment_period": building.reference_period,
                "construction_year": building.construction_year,
                "total_floor_area": building.total_floor_area,
                "conditioned_floor_area": building.cond_floor_area,
                "floors_above_ground": building.floors_above_ground,
                "floors_below_ground": building.floors_below_ground,
                "has_certification": building.has_certification,
                "certification_file": cert_info,
                "design_drawings_status": building.design_drawings_status,
                "has_design_drawings": building.has_design_drawings,
                "design_drawing_files": drawing_info,
                "boq_status": building.boq_status,
                "has_boq": building.has_boq,
                "boq_files": boq_info,
                "total_annual_energy_consumption": energy_summary.total_kwh if energy_summary and energy_summary.total_kwh is not None else None,
                "energy_summary_any_components": energy_summary.any_components if energy_summary else False,
                "energy_summary_exists": energy_summary is not None,
                "seismic_zone": building.seismic_zone,
            }

            # Pre-populate climate_type
            if building.climate_zone:
                context["selected_climate_type"] = building.climate_zone.name

            if building.country_id:
                context["country_id"] = building.country_id
                context["is_india"] = Country.objects.filter(pk=building.country_id, code2="IN").exists()
                filtered_categories = _get_building_categories_for_country(building.country_id)
                context["building_categories"] = filtered_categories
                filtered_ids = set(filtered_categories.values_list('id', flat=True))
            else:
                filtered_ids = None

            # Pre-populate building_type and apartment_type only if the saved
            # category is valid for the currently filtered category list
            if building.category:
                saved_cat_id = building.category.category.id
                if filtered_ids is None or saved_cat_id in filtered_ids:
                    context["selected_building_type"] = saved_cat_id
                    context["selected_apartment_type"] = building.category.subcategory.id
                    subcategories = CategorySubcategory.objects.filter(
                        category=building.category.category
                    ).select_related('subcategory').order_by('subcategory__name')
                    seen_ids = set()
                    unique_subcats = []
                    for cs in subcategories:
                        if cs.subcategory_id not in seen_ids:
                            seen_ids.add(cs.subcategory_id)
                            unique_subcats.append(cs.subcategory)
                    context["apartment_types"] = unique_subcats
                # else: saved category not valid for this country — leave selects empty

        except Building.DoesNotExist:
            logger.warning(f"Building not found for edit: {building_uuid}")

    return render(
        request,
        "pages/add-building/components/building-information/building-details.html",
        context
    )


# Step 2.1: Operational Schedule & Temperature
def handle_schedule_temp_step(request):
    """Handle operational schedule and temperature step."""
    context = {}
    return render(
        request,
        "pages/add-building/components/operational-details/operational-schedule-temperature.html",
        context
    )


# Step 2.2: Cooling System
def handle_cooling_system_step(request):
    """Handle cooling system configuration step."""
    building_uuid = request.GET.get('building_uuid', '')
    climate_zone = ''
    if building_uuid:
        try:

            building = Building.objects.get(uuid=uuid_lib.UUID(building_uuid), created_by=request.user)
            climate_zone = building.climate_zone.name if building.climate_zone else ''
        except Exception:
            pass
    context = {
        "building_uuid": building_uuid,
        "climate_zone": climate_zone,
    }
    return render(
        request,
        "pages/add-building/components/operational-details/cooling-system.html",
        context
    )


# Step 2.3: Ventilation System
def handle_ventilation_system_step(request):
    """Handle ventilation system configuration step."""
    building_uuid = request.GET.get('building_uuid', '')
    climate_zone = ''
    if building_uuid:
        try:
            building = Building.objects.get(uuid=uuid_lib.UUID(building_uuid), created_by=request.user)
            if building.climate_zone:
                climate_zone = building.climate_zone.name
        except Exception:
            pass
    context = {
        "building_uuid": building_uuid,
        "climate_zone": climate_zone,
    }
    return render(
        request,
        "pages/add-building/components/operational-details/ventilation-system.html",
        context
    )


# Step 2.4: Lighting System
def handle_lighting_system_step(request):
    """Handle lighting system configuration step."""
    context = {
        "building_uuid": request.GET.get('building_uuid', '')
    }
    return render(
        request,
        "pages/add-building/components/operational-details/lighting-system.html",
        context
    )


# Step 2.5: Lift & Escalator System
def handle_lift_escalator_step(request):
    """Handle lift and escalator system configuration step."""
    context = {
        "building_uuid": request.GET.get('building_uuid', '')
    }
    return render(
        request,
        "pages/add-building/components/operational-details/lift-escalator-system.html",
        context
    )


# Step 2.6: Hot Water System
def handle_hot_water_step(request):
    """Handle hot water system configuration step."""
    context = {
        "building_uuid": request.GET.get('building_uuid', '')
    }
    return render(
        request,
        "pages/add-building/components/operational-details/hot-water-system.html",
        context
    )

# Step 2.7: Energy Consumption Summary
def handle_energy_consumption_summary_step(request):
    """Handle energy consumption summary step."""
    building_uuid = request.GET.get('building_uuid', '')
    summary = None

    if building_uuid:
        try:
            building = Building.objects.get(uuid=building_uuid, created_by=request.user)
            summary, created = EnergySummary.objects.get_or_create(building=building)
            if created:
                summary.recalculate()
                summary.save()
        except Building.DoesNotExist:
            pass

    context = {
        "building_uuid": building_uuid,
        "summary": summary,
    }
    return render(
        request,
        "pages/add-building/components/operational-details/energy-consumption-summary.html",
        context
    )


# Step 3: Operational Data Entry
def handle_operational_data_step(request):

    # Initialize filter form with pre-filled operational filters
    epd_filters_form = EPDsFilterForm()
    
    # Lock category and subcategory for operational products
    # Category: "Others" (ID: 9), Subcategory: "Energy carrier - delivery free user" (ID: 9.2)
    try:
        category = MaterialCategory.objects.get(category_id="9")
        subcategory = MaterialCategory.objects.get(category_id="9.2")
        
        # Set initial values and disable these fields
        epd_filters_form.fields['category'].initial = category
        epd_filters_form.fields['category'].disabled = True
        epd_filters_form.fields['subcategory'].initial = subcategory
        epd_filters_form.fields['subcategory'].disabled = True
        epd_filters_form.fields['subcategory'].queryset = MaterialCategory.objects.filter(
            level=2, parent=category
        )
        epd_filters_form.fields['childcategory'].queryset = MaterialCategory.objects.filter(
            level=3, parent=subcategory
        ).order_by("name_en")
    except MaterialCategory.DoesNotExist:
        logger.warning("Energy carrier categories not found")
    
    # Load previously saved operational products from database (if building exists)
    selected_products = []
    total_annual_energy_consumption = None
    building_uuid = request.GET.get('building_uuid')

    logger.info(f"Loading operational data step with building_uuid: {building_uuid}")

    if building_uuid:
        try:
            uuid_obj = uuid_lib.UUID(building_uuid)
            building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
            logger.info(f"Found building: {building.id} - {building.name}")

            # Target total energy from building systems (Systems/Consumption section)
            energy_summary = EnergySummary.objects.filter(building=building).first()
            if energy_summary and energy_summary.total_kwh is not None:
                total_annual_energy_consumption = energy_summary.total_kwh

            # Get saved operational products from database
            saved_products = OperationalProduct.objects.filter(
                building=building
            ).select_related('epd', 'epd__country', 'epd__category')

            logger.info(f"Found {saved_products.count()} saved operational products")

            for op_product in saved_products:
                # Get available units and ensure it's a list
                available_units = op_product.epd.get_available_units()
                if available_units is None:
                    available_units = [op_product.epd.declared_unit]
                elif isinstance(available_units, set):
                    available_units = sorted(list(available_units))
                elif not isinstance(available_units, list):
                    available_units = list(available_units)

                selected_products.append({
                    "id": str(op_product.epd.id),
                    "name": op_product.epd.name,
                    "country": op_product.epd.country.name if op_product.epd.country else "Unknown",
                    "category": op_product.epd.category.name_en if op_product.epd.category else "Unknown",
                    "description": op_product.description,
                    "selection_unit": op_product.input_unit,
                    "selection_quantity": op_product.quantity,
                    "timestamp": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                    "op_units": available_units,
                })
        except (ValueError, Building.DoesNotExist):
            logger.warning(f"Building not found for UUID: {building_uuid}")
    
    context = {
        'epd_filters_form': epd_filters_form,
        'countries': ALCBTCountryManager.get_all_countries(),
        'selected_products': selected_products,
        'total_annual_energy_consumption': total_annual_energy_consumption,
    }
    return render(
        request,
        "pages/add-building/components/operational-data-entry/operational-data-entry.html",
        context
    )


# Step 4: Building Structural Components
def handle_structural_components_step(request):
    """Handle building structural components step."""


    # Get filter dropdown data for EPD library search
    countries = Country.objects.all().order_by("name")
    epd_categories = MaterialCategory.objects.filter(parent__isnull=True).order_by("name_en")
    epd_types = [{"value": t[0], "label": t[1]} for t in EPDType.choices]

    # Load previously saved assemblies from database (if building exists)
    boq_items = []
    component_items = []
    building_uuid = request.GET.get('building_uuid')

    if building_uuid:
        try:
            uuid_obj = uuid_lib.UUID(building_uuid)
            building = Building.objects.get(uuid=uuid_obj, created_by=request.user)

            # Get saved assemblies with their structural products, newest first
            building_assemblies = BuildingAssembly.objects.filter(
                building=building
            ).order_by('-assembly__created_at').select_related(
                'assembly'
            ).prefetch_related(
                Prefetch(
                    'assembly__structuralproduct_set',
                    queryset=StructuralProduct.objects
                        .select_related('epd', 'classification')
                        .prefetch_related(
                            Prefetch(
                                'epd__epdimpact_set',
                                queryset=EPDImpact.objects.select_related('impact'),
                                to_attr='all_impacts',
                            ),
                            'epd__country',
                            'epd__category',
                            'classification__category',
                        ),
                    to_attr='prefetched_products',
                ),
            )

            floor_area = float(building.total_floor_area) if building.total_floor_area else 1.0

            building_assemblies_list = list(building_assemblies)
            newest_assembly_id = building_assemblies_list[0].assembly.id if building_assemblies_list else None

            for ba in building_assemblies_list:
                assembly = ba.assembly
                products = getattr(assembly, 'prefetched_products', None) or list(assembly.structuralproduct_set.all())

                # Get materials for this assembly
                materials = []
                for sp in products:
                    material = {
                        'epd_id': sp.epd.id,
                        'name': sp.epd.name,
                        'quantity': float(sp.quantity),
                        'unit': sp.input_unit,
                        'description': sp.description or '',
                        'gwp': float(sp.epd.get_gwp_impact_sum("a1a3") or 0),
                        'country': sp.epd.country.name if sp.epd.country else 'Unknown',
                        'type': sp.epd.type,
                        'source': sp.epd.source,
                    }

                    # Add category for BOQ items
                    if assembly.is_boq and sp.classification:
                        material['category'] = sp.classification.category.id
                        material['category_name'] = sp.classification.category.name

                    materials.append(material)

                # Calculate total GWP using proper formula (matches dashboard)
                total_gwp = 0.0
                for sp in products:
                    try:
                        impacts = calculate_impacts(
                            dimension=assembly.dimension,
                            assembly_quantity=ba.quantity,
                            total_floor_area=floor_area,
                            p=sp,
                        )
                        for impact in impacts:
                            if (impact["impact_type"].impact_category == "gwp" and
                                    impact["impact_type"].life_cycle_stage == "a1a3"):
                                val = float(impact["impact_value"])
                                if val > 0:
                                    total_gwp += val
                    except (ImpactCalculationError, ValueError, ZeroDivisionError):
                        pass

                is_newest = (assembly.id == newest_assembly_id)
                if assembly.is_boq:
                    # BOQ item
                    boq_items.append({
                        'id': assembly.id,
                        'name': assembly.name,
                        'comment': assembly.comment or '',
                        'materials': materials,
                        'total_gwp': total_gwp,
                        'is_template': assembly.is_template,
                        'is_newest': is_newest,
                    })
                else:
                    # Component item
                    classification = assembly.classification
                    component_items.append({
                        'id': assembly.id,
                        'title': assembly.name,
                        'category': classification.category.id if classification else None,
                        'category_name': classification.category.name if classification else '',
                        'technique': classification.technique.id if classification and classification.technique else None,
                        'dimension': assembly.dimension,
                        'quantity': float(ba.quantity),
                        'comment': assembly.comment or '',
                        'materials': materials,
                        'total_gwp': total_gwp,
                        'is_template': assembly.is_template,
                        'is_newest': is_newest,
                    })

        except (ValueError, Building.DoesNotExist):
            logger.warning(f"Building not found for UUID: {building_uuid}")
        except Exception as e:
            logger.exception(f"Error loading structural assemblies: {str(e)}")

    logger.info(f"Loaded {len(boq_items)} BOQ items and {len(component_items)} component items")

    context = {
        'countries': countries,
        'epd_categories': epd_categories,
        'epd_types': epd_types,
        'boq_items': boq_items,
        'component_items': component_items,
    }
    return render(
        request,
        "pages/add-building/components/building-structural-components/building-structural-components.html",
        context
    )


@login_required
@require_http_methods(["POST", "PUT"])
def save_building_step(request):
    """
    Save data from a building creation step.
    Handles AJAX POST/PUT requests to save step data.

    Step 1.1 (building-name-location): Creates Building with basic data, returns UUID.
    Step 1.2 (building-details): Updates the Building with additional details using UUID.
    Operational steps: Data is saved immediately via dedicated APIs, this just returns success.
    """
    try:
        data = json.loads(request.body)
        step_key = data.get("step_key")
        step_data = data.get("data")
        logging.info(f"Saving step data for {step_key}")

        if not step_key or step_data is None:
            return JsonResponse({"error": "Missing step_key or data"}, status=400)

        building_uuid = step_data.get('building_uuid', '')
        geo_result = None

        # Step 1.1: Create the Building with basic info from name & location
        if step_key == "building-information/building-name-location":
            if building_uuid:
                # Update existing building
                try:
                    uuid_obj = uuid_lib.UUID(building_uuid)
                    building = Building.objects.get(uuid=uuid_obj, created_by=request.user)

                    # Update name and location fields (handle both 'name' and 'building_name')
                    if 'building_name' in step_data:
                        building.name = step_data['building_name']
                    elif 'name' in step_data:
                        building.name = step_data['name']

                    if 'address' in step_data:
                        building.street = step_data['address']  # Using address for street field
                    if 'country' in step_data and step_data['country']:
                        building.country_id = step_data['country']
                    if 'region' in step_data and step_data['region']:
                        building.region_id = step_data['region']
                    if 'city' in step_data and step_data['city']:
                        building.city_id = step_data['city']
                    if 'longitude' in step_data:
                        building.longitude = step_data['longitude'] if step_data['longitude'] else None
                    if 'latitude' in step_data:
                        building.latitude = step_data['latitude'] if step_data['latitude'] else None

                    geo_result = _resolve_and_apply_geo_fields(building)

                    building.save()
                    building_uuid = str(building.uuid)

                except (ValueError, Building.DoesNotExist):
                    return JsonResponse({"error": "Invalid building UUID"}, status=400)
            else:
                # Create new building with basic required fields
                # Handle both 'name' and 'building_name' field names
                building_name = step_data.get('building_name') or step_data.get('name', 'Untitled Building')

                building = Building.objects.create(
                    name=building_name,
                    street=step_data.get('address', ''),  # Using address for street field
                    country_id=step_data.get('country') if step_data.get('country') else None,
                    region_id=step_data.get('region') if step_data.get('region') else None,
                    city_id=step_data.get('city') if step_data.get('city') else None,
                    longitude=step_data.get('longitude') if step_data.get('longitude') else None,
                    latitude=step_data.get('latitude') if step_data.get('latitude') else None,
                    created_by=request.user,
                    # Add minimal defaults for required fields
                    climate_zone=None,  # Will be updated in step 1.2
                    total_floor_area=100,  # Will be updated in step 1.2
                    reference_period=50,    # Will be updated in step 1.2
                )
                geo_result = _resolve_and_apply_geo_fields(building)
                if geo_result:
                    building.save()
                building_uuid = str(building.uuid)

        # Step 1.2: Update the Building with detailed information
        elif step_key == "building-information/building-details":
            if building_uuid:
                # Update existing building
                try:
                    uuid_obj = uuid_lib.UUID(building_uuid)
                    building = Building.objects.get(uuid=uuid_obj, created_by=request.user)

                    # Resolve climate_zone FK before generic field mapping
                    if step_data.get('climate_type'):
                        try:
                            building.climate_zone = ClimateType.objects.get(name=step_data['climate_type'])
                        except ClimateType.DoesNotExist:
                            pass

                    # Map remaining form field names to model field names
                    field_mapping = {
                        'assessment_period': 'reference_period',
                        'conditioned_floor_area': 'cond_floor_area',
                        'construction_year': 'construction_year',
                        'total_floor_area': 'total_floor_area',
                        'floors_above_ground': 'floors_above_ground',
                        'floors_below_ground': 'floors_below_ground',
                        'seismic_zone': 'seismic_zone',
                    }

                    # Update building with mapped fields
                    for form_field, model_field in field_mapping.items():
                        if form_field in step_data and step_data[form_field] not in (None, ""):
                            setattr(building, model_field, step_data[form_field])

                    # Resolve building_type (BuildingCategory.id) + apartment_type
                    # (BuildingSubcategory.id) → CategorySubcategory
                    building_type_id = step_data.get('building_type')
                    apartment_type_id = step_data.get('apartment_type')
                    if building_type_id and apartment_type_id:
                        try:
                            cat_subcat = CategorySubcategory.objects.filter(
                                category_id=building_type_id,
                                subcategory_id=apartment_type_id,
                            ).first()
                            if cat_subcat:
                                building.category = cat_subcat
                        except Exception:
                            pass

                    building.save()
                    building_uuid = str(building.uuid)

                    # Save manual total energy if no system-derived data exists
                    raw_total = step_data.get('total_annual_energy_consumption')
                    if raw_total not in (None, ''):
                        try:
                            summary, _ = EnergySummary.objects.get_or_create(building=building)
                            if not summary.any_components:
                                summary.total_override_kwh = Decimal(str(raw_total))
                                summary.save(update_fields=['total_override_kwh'])
                        except (InvalidOperation, ValueError):
                            pass

                except Building.DoesNotExist:
                    return JsonResponse({"error": "Building not found"}, status=404)
                except ValueError as e:
                    logger.exception(f"Error updating building details: {e}")
                    return JsonResponse({"error": str(e)}, status=400)
            else:
                return JsonResponse({"error": "Building must be created in step 1.1 first"}, status=400)

        # Step 3: Operational Data Entry - Save operational products
        elif step_key in ["operational-data-entry/operational-data-entry", "operational-data-entry/operational-data-entry.html"]:
            logger.info(f"Handling operational data entry step for building_uuid: {building_uuid}")
            logger.info(f"Step data: {step_data}")

            if not building_uuid:
                return JsonResponse({"error": "Building UUID is required"}, status=400)

            try:
                uuid_obj = uuid_lib.UUID(building_uuid)
                building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
                logger.info(f"Found building: {building.id}")

                # Extract operational products from step_data
                operation_products = step_data.get('operation_products', [])
                logger.info(f"Found {len(operation_products)} operational products in step_data")

                if operation_products:
                    # Delete existing operational products for this building
                    OperationalProduct.objects.filter(building=building).delete()

                    # Create new operational products
                    created_count = 0
                    for product in operation_products:
                        # Extract the actual product data (skip csrf token)
                        epd_id = product.get('id')
                        if epd_id:
                            try:
                                # The id is a UUID string (EPD uses UUID as primary key)
                                epd_uuid_obj = uuid_lib.UUID(epd_id)
                                epd = EPD.objects.get(id=epd_uuid_obj)

                                # Extract quantity and unit from the material_* fields
                                quantity = None
                                unit = None
                                description = None

                                # Find the material fields with this EPD's UUID
                                for key, value in product.items():
                                    if key.startswith(f'material_{epd_id}_quantity_'):
                                        quantity = float(value)
                                    elif key.startswith(f'material_{epd_id}_unit_'):
                                        unit = value
                                    elif key.startswith(f'material_{epd_id}_description_'):
                                        description = value

                                if quantity is not None and unit:
                                    OperationalProduct.objects.create(
                                        building=building,
                                        epd=epd,
                                        quantity=quantity,
                                        input_unit=unit,
                                        description=description or ''
                                    )
                                    created_count += 1
                                else:
                                    logger.warning(f"Missing quantity or unit for EPD {epd_id}")
                            except (ValueError, EPD.DoesNotExist) as e:
                                logger.warning(f"EPD not found for UUID: {epd_id}, error: {e}")
                                continue
                        else:
                            logger.warning(f"Product missing EPD ID: {product}")

                    logger.info(f"Saved {created_count} operational products for building {building.id}")

            except (ValueError, Building.DoesNotExist):
                return JsonResponse({"error": "Invalid building UUID or building not found"}, status=400)
            except Exception as e:
                logger.exception(f"Error saving operational products: {str(e)}")
                return JsonResponse({"error": str(e)}, status=500)

        # For all other steps, just acknowledge receipt
        # Operational systems are saved immediately via their dedicated APIs
        # Other data is kept client-side until final completion
        building_name = None
        if building_uuid:
            try:
                _b = Building.objects.only("name").get(
                    uuid=uuid_lib.UUID(building_uuid), created_by=request.user
                )
                building_name = _b.name
            except (ValueError, Building.DoesNotExist):
                pass
        return JsonResponse({
            "success": True,
            "message": "Step data saved successfully",
            "building_uuid": building_uuid,
            "building_name": building_name,
            "geo_climate_type": geo_result.get("climate_type") if geo_result else None,
            "geo_climate_warning": geo_result.get("climate_warning") if geo_result else None,
            "geo_seismic_zone": geo_result.get("seismic_zone") if geo_result else None,
            "geo_seismic_warning": geo_result.get("seismic_warning") if geo_result else None,
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logging.error(f"Error saving building step: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_building_data(request):
    """
    Get building data by UUID for restoring form fields.
    Returns building data formatted for form restoration.
    """
    building_uuid = request.GET.get('building_uuid')

    if not building_uuid:
        return JsonResponse({"error": "building_uuid parameter is required"}, status=400)

    try:
        uuid_obj = uuid_lib.UUID(building_uuid)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)

        # Return building data with form field names (not model field names)
        # Get parent category (building_type) and subcategory (apartment_type) if category exists
        building_type_id = None
        apartment_type_id = None
        if building.category:
            # building.category is a CategorySubcategory object
            # It has both category (parent) and subcategory (apartment type)
            building_type_id = building.category.category.id
            apartment_type_id = building.category.subcategory.id

        data = {
            # Step 1.1 fields
            'building_name': building.name,
            'address': building.street or '',
            'country': building.country_id,
            'region': building.region_id,
            'city': building.city_id,
            'longitude': building.longitude,
            'latitude': building.latitude,

            # Step 1.2 fields (use form field names)
            'building_type': building_type_id,
            'building_type_name': building.category.category.name if building.category else '',
            'building_sub_type_name': building.category.subcategory.name if building.category else '',
            'apartment_type': apartment_type_id,
            'climate_type': building.climate_zone.name if building.climate_zone else '',
            'assessment_period': building.reference_period,
            'construction_year': building.construction_year,
            'total_floor_area': str(building.total_floor_area) if building.total_floor_area is not None else '',
            'conditioned_floor_area': str(building.cond_floor_area) if building.cond_floor_area is not None else '',
            'floors_above_ground': building.floors_above_ground,
            'floors_below_ground': building.floors_below_ground,
            'has_design_drawings': building.has_design_drawings,
            'design_drawings_status': building.design_drawings_status,
            'boq_status': building.boq_status,
            'has_boq': building.has_boq,
            'seismic_zone': building.seismic_zone or '',
        }

        return JsonResponse({
            "success": True,
            "data": data
        })

    except (ValueError, Building.DoesNotExist):
        return JsonResponse({"error": "Building not found or invalid UUID"}, status=404)
    except Exception as e:
        logging.error(f"Error fetching building data: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def complete_building_setup(request):
    """
    Complete the building setup process.

    At this point:
    - Building already exists (created in step 1.2)
    - All operational systems already saved to DB (via their dedicated APIs)
    - This just marks the process as complete and redirects to dashboard
    """
    try:
        data = json.loads(request.body)
        building_uuid = data.get("building_uuid")

        if not building_uuid:
            return JsonResponse({
                "success": False,
                "error": "Building UUID is required"
            }, status=400)

        # Verify building exists and belongs to user
        try:
            uuid_obj = uuid_lib.UUID(building_uuid)
            building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
        except (ValueError, Building.DoesNotExist):
            return JsonResponse({
                "success": False,
                "error": "Building not found or invalid UUID"
            }, status=404)

        # Building setup is complete - all data already saved
        return JsonResponse({
            "success": True,
            "message": "Building setup completed successfully",
            "redirect_url": f"/building/{building.id}/"
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logging.error(f"Error completing building setup: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


_SYSTEM_NA_FIELDS = {
    "cooling": "cooling_not_applicable",
    "ventilation": "ventilation_not_applicable",
    "lighting": "lighting_not_applicable",
    "lift": "lift_not_applicable",
    "hot_water": "hot_water_not_applicable",
}


@login_required
@require_http_methods(["POST"])
def toggle_system_not_applicable(request):
    """Toggle a system's not-applicable flag on the building."""
    try:
        data = json.loads(request.body)
        building_uuid = data.get("building_uuid")
        system = data.get("system")
        value = data.get("value", False)

        field = _SYSTEM_NA_FIELDS.get(system)
        if not field:
            return JsonResponse({"success": False, "error": "Unknown system"}, status=400)

        uuid_obj = uuid_lib.UUID(building_uuid)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
        setattr(building, field, bool(value))
        building.save(update_fields=[field])
        return JsonResponse({"success": True, "system": system, "value": bool(value)})
    except (ValueError, Building.DoesNotExist):
        return JsonResponse({"success": False, "error": "Building not found"}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_systems_status(request):
    """Return completion status for all 5 operational systems."""
    building_uuid = request.GET.get("building_uuid")
    try:
        uuid_obj = uuid_lib.UUID(building_uuid)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
        systems = [
            {
                "key": "cooling",
                "label": "Cooling system",
                "has_data": building.air_conditioners.exists() or building.chillers.exists(),
                "not_applicable": building.cooling_not_applicable,
            },
            {
                "key": "ventilation",
                "label": "Ventilation system",
                "has_data": building.ventilation_systems.exists(),
                "not_applicable": building.ventilation_not_applicable,
            },
            {
                "key": "lighting",
                "label": "Lighting system",
                "has_data": building.lighting_systems.exists(),
                "not_applicable": building.lighting_not_applicable,
            },
            {
                "key": "lift",
                "label": "Lift & escalator system",
                "has_data": building.lift_escalator_systems.exists(),
                "not_applicable": building.lift_not_applicable,
            },
            {
                "key": "hot_water",
                "label": "Hot water system",
                "has_data": building.hot_water_systems.exists(),
                "not_applicable": building.hot_water_not_applicable,
            },
        ]
        return JsonResponse({"success": True, "systems": systems})
    except (ValueError, Building.DoesNotExist):
        return JsonResponse({"success": False, "error": "Building not found"}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
