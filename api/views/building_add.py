"""
API views for the add-building multi-step manual form.

These mirror the HTMX add_building_steps / cooling_system / ventilation_system /
lighting_system / lift_escalator_system / hot_water_system / building_step_operational
views but:
  - Require JWT admin authentication (IsAdminUser)
  - Use _buildings_queryset() for org-scoped access instead of created_by=request.user
  - Accept/return JSON exclusively
  - Include organisation_id on step 1 so the building is org-linked from creation

Step layout (matches the HTMX wizard):
  POST /api/buildings/add/name-location/         Step 1 — create/update name & location
  POST /api/buildings/add/details/               Step 2 — building type, climate, areas
  POST /api/buildings/add/operational-schedule/  Step 3 — schedule & temperatures
  POST /api/buildings/add/cooling-systems/       Step 4 — add/update/delete cooling
  DELETE /api/buildings/add/cooling-systems/     Delete single cooling system
  POST /api/buildings/add/ventilation-systems/   Step 5 — add/update/delete ventilation
  DELETE /api/buildings/add/ventilation-systems/ Delete single ventilation system
  POST /api/buildings/add/lighting-systems/      Step 6 — add/update/delete lighting
  DELETE /api/buildings/add/lighting-systems/    Delete single lighting system
  POST /api/buildings/add/lift-escalator/        Step 7 — create/update lift system
  DELETE /api/buildings/add/lift-escalator/      Delete lift system
  POST /api/buildings/add/hot-water-systems/     Step 8 — add/update/delete hot water
  DELETE /api/buildings/add/hot-water-systems/   Delete single hot water system
  POST /api/buildings/add/energy-carriers/       Step 9 — save operational products
  POST /api/buildings/add/structural-components/ Step 10 — add assembly
  DELETE /api/buildings/add/structural-components/ Delete single building assembly
  POST /api/buildings/add/complete/              Mark building as published (draft=False)
"""

import logging
import os
import uuid as uuid_lib

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdminUser
from api.views.buildings import _buildings_queryset, _get_building_or_error
from pages.forms.cooling_system_form import CoolingSystemAirConditionerForm, CoolingSystemChillerForm
from pages.forms.ventilation_system_form import VentilationSystemForm
from pages.forms.lighting_system_form import LightingSystemForm
from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm
from pages.forms.hot_water_system_form import HotWaterSystemForm
from pages.models.assembly import (
    Assembly, AssemblyCategoryTechnique, AssemblyDimension, AssemblyMode,
    AssemblyTechnique, StructuralProduct,
)
from pages.models.building import Building, BuildingAssembly, BuildingBoQFile, CategorySubcategory, OperationalProduct
from pages.models.building_operation import (
    CoolingSystemAirConditioner, CoolingSystemChiller,
    LiftEscalatorSystem, HotWaterSystem,
)
from pages.models.building_operation.ventilation import VentilationSystem
from pages.models.building_operation.lighting import LightingSystem
from pages.models.epd import EPD
from pages.models.organisation import Organisation
from pages.views.building.import_building import (
    _str,
    _bool_from_excel,
    _resolve_building_type,
    _resolve_climate,
)
from api.views.building_files import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    _validate_file,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1 — Name & Location
# ---------------------------------------------------------------------------

class BuildingAddNameLocationView(APIView):
    """
    POST /api/buildings/add/name-location/

    Creates a new building or updates an existing draft.
    Pass organisation_id to link to an organisation.

    Fields:
      building_uuid   — omit to create, provide to update
      building_name   — required
      address         — required (→ street)
      country         — country PK (integer)
      region          — region PK (integer, optional)
      city            — city PK (integer, optional)
      longitude       — float, optional
      latitude        — float, optional
      organisation_id — UUID string, optional
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        errors = {}

        building_name = _str(data.get("building_name"))
        address = _str(data.get("address"))
        country_id = data.get("country")
        region_id = data.get("region") or None
        city_id = data.get("city") or None
        longitude = data.get("longitude") or None
        latitude = data.get("latitude") or None
        building_uuid_str = _str(data.get("building_uuid"))
        organisation_id = _str(data.get("organisation_id"))

        if not building_name:
            errors["building_name"] = "Building name is required."
        if not address:
            errors["address"] = "Address is required."

        try:
            longitude = float(longitude) if longitude else None
        except (ValueError, TypeError):
            longitude = None
        try:
            latitude = float(latitude) if latitude else None
        except (ValueError, TypeError):
            latitude = None

        # Resolve organisation
        organisation = None
        if organisation_id:
            try:
                org_qs = Organisation.objects.all()
                if not request.user.is_superuser:
                    org_qs = org_qs.filter(memberships__user=request.user)
                organisation = org_qs.get(pk=organisation_id)
            except Organisation.DoesNotExist:
                errors["organisation_id"] = "Organisation not found or access denied."

        if errors:
            return Response({"success": False, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        if building_uuid_str:
            try:
                uuid_obj = uuid_lib.UUID(building_uuid_str)
                building = _buildings_queryset(request).get(uuid=uuid_obj)
                building.name = building_name
                building.street = address
                if country_id:
                    building.country_id = country_id
                building.region_id = region_id
                building.city_id = city_id
                building.longitude = longitude
                building.latitude = latitude
                if organisation:
                    building.organisation = organisation
                building.save()
            except (ValueError, Building.DoesNotExist):
                return Response(
                    {"success": False, "errors": {"__all__": ["Building not found."]}},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            building = Building.objects.create(
                name=building_name,
                street=address,
                country_id=country_id or None,
                region_id=region_id,
                city_id=city_id,
                longitude=longitude,
                latitude=latitude,
                created_by=request.user,
                organisation=organisation,
                climate_zone=None,
                total_floor_area=100,
                reference_period=50,
            )

        logger.info("API Add Step 1: building %s saved by %s", building.uuid, request.user)
        return Response({"success": True, "building_uuid": str(building.uuid)})


# ---------------------------------------------------------------------------
# Step 2 — Building Details
# ---------------------------------------------------------------------------

class BuildingAddDetailsView(APIView):
    """
    POST /api/buildings/add/details/

    Updates building type, climate zone, floor area, construction year etc.

    Fields:
      building_uuid         — required
      building_type_id      — BuildingCategory PK
      apartment_type_id     — BuildingSubcategory PK
      climate_type          — climate zone name or PK
      assessment_period     — int (years)
      total_floor_area      — float (m²)
      conditioned_floor_area— float, optional
      construction_year     — int, optional
      floors_below_ground   — int, optional
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        errors = {}

        # Building type → CategorySubcategory
        building_type_id = data.get("building_type_id") or data.get("building_type")
        apartment_type_id = data.get("apartment_type_id") or data.get("apartment_type")
        cat_subcat = None
        if building_type_id and apartment_type_id:
            cat_subcat = CategorySubcategory.objects.filter(
                category_id=building_type_id,
                subcategory_id=apartment_type_id,
            ).first()
            if not cat_subcat:
                errors["building_type"] = "Invalid building type / apartment type combination."
        elif building_type_id:
            # Building type with no subtypes — look up any CategorySubcategory for this category
            cat_subcat = CategorySubcategory.objects.filter(
                category_id=building_type_id,
            ).first()

        # Climate zone
        climate_value = None
        climate_raw = data.get("climate_type")
        if climate_raw:
            climate_value, climate_err = _resolve_climate(climate_raw)
            if climate_err:
                errors["climate_type"] = climate_err

        # Assessment period
        assessment_period = None
        ap_raw = _str(data.get("assessment_period"))
        if ap_raw:
            try:
                assessment_period = int(float(ap_raw))
                if assessment_period <= 0:
                    errors["assessment_period"] = "Assessment period must be positive."
            except (ValueError, TypeError):
                errors["assessment_period"] = "Assessment period must be a valid number."

        # Total floor area
        total_floor_area = None
        tfa_raw = _str(data.get("total_floor_area"))
        if tfa_raw:
            try:
                total_floor_area = float(tfa_raw)
                if total_floor_area <= 0:
                    errors["total_floor_area"] = "Total floor area must be greater than zero."
            except (ValueError, TypeError):
                errors["total_floor_area"] = "Total floor area must be a valid number."

        # Optional fields
        conditioned_floor_area = None
        cfa_raw = _str(data.get("conditioned_floor_area"))
        if cfa_raw:
            try:
                conditioned_floor_area = float(cfa_raw)
            except (ValueError, TypeError):
                errors["conditioned_floor_area"] = "Conditioned floor area must be a valid number."

        construction_year = None
        cy_raw = _str(data.get("construction_year"))
        if cy_raw:
            try:
                construction_year = int(float(cy_raw))
            except (ValueError, TypeError):
                errors["construction_year"] = "Construction year must be a valid year."

        floors_below_ground = None
        fbg_raw = _str(data.get("floors_below_ground"))
        if fbg_raw:
            try:
                floors_below_ground = int(float(fbg_raw))
            except (ValueError, TypeError):
                errors["floors_below_ground"] = "Floors below ground must be a valid number."

        if errors:
            return Response({"success": False, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        if cat_subcat:
            building.category = cat_subcat
        if climate_value is not None:
            building.climate_zone = climate_value
        if assessment_period is not None:
            building.reference_period = assessment_period
        if total_floor_area is not None:
            building.total_floor_area = total_floor_area
        if conditioned_floor_area is not None:
            building.cond_floor_area = conditioned_floor_area
        if construction_year is not None:
            building.construction_year = construction_year
        if floors_below_ground is not None:
            building.floors_below_ground = floors_below_ground

        # has_certification / has_boq flags
        has_cert_raw = data.get("has_certification")
        if has_cert_raw is not None:
            if isinstance(has_cert_raw, str):
                building.has_certification = has_cert_raw.lower() in ("yes", "true", "1")
            else:
                building.has_certification = bool(has_cert_raw)

        has_boq_raw = data.get("has_boq")
        if has_boq_raw is not None:
            if isinstance(has_boq_raw, str):
                building.has_boq = has_boq_raw.lower() in ("yes", "true", "1")
            else:
                building.has_boq = bool(has_boq_raw)

        building.save()

        logger.info("API Add Step 2: building %s details saved by %s", building.uuid, request.user)
        return Response({"success": True, "building_uuid": str(building.uuid)})


# ---------------------------------------------------------------------------
# Restore form data (GET)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Step 3 — Operational Schedule
# ---------------------------------------------------------------------------

class BuildingAddOperationalScheduleView(APIView):
    """
    POST /api/buildings/add/operational-schedule/

    Fields: building_uuid, num_residents, hours_per_workday, workdays_per_week,
            weeks_per_year, heating_temp, heating_temp_unit, cooling_temp,
            cooling_temp_unit, renewable_energy_percent, building_smart_system
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        if data.get("num_residents") is not None:
            building.num_residents = data.get("num_residents")
        if data.get("hours_per_workday") is not None:
            building.hours_per_workday = data.get("hours_per_workday")
        if data.get("workdays_per_week") is not None:
            building.workdays_per_week = data.get("workdays_per_week")
        if data.get("weeks_per_year") is not None:
            building.weeks_per_year = data.get("weeks_per_year")
        if data.get("heating_temp") is not None:
            building.heating_temp = data.get("heating_temp")
        if data.get("heating_temp_unit"):
            building.heating_temp_unit = data.get("heating_temp_unit")
        if data.get("cooling_temp") is not None:
            building.cooling_temp = data.get("cooling_temp")
        if data.get("cooling_temp_unit"):
            building.cooling_temp_unit = data.get("cooling_temp_unit")

        renewable = data.get("renewable_energy_percent")
        building.renewable_energy_percent = renewable if renewable not in (None, "", "0", 0) else None

        smart_raw = data.get("building_smart_system", "no")
        building.building_smart_system = _bool_from_excel(smart_raw) if isinstance(smart_raw, str) else bool(smart_raw)

        building.save()

        logger.info("API Add Step 3: building %s schedule saved by %s", building.uuid, request.user)
        return Response({"success": True, "building_uuid": str(building.uuid)})


# ---------------------------------------------------------------------------
# Step 4 — Cooling Systems (CRUD)
# ---------------------------------------------------------------------------

class BuildingAddCoolingSystemView(APIView):
    """
    POST /api/buildings/add/cooling-systems/
      Create or update a single cooling system.
      cooling_system_type: "chiller" | "air_conditioner"
      cooling_system_id: int (omit to create)

    DELETE /api/buildings/add/cooling-systems/
      cooling_system_id: int (required)
      cooling_system_type: "chiller" | "air_conditioner"
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        ctype = data.get("cooling_system_type")
        system_id = data.get("cooling_system_id")
        is_update = bool(system_id)

        if ctype == "chiller":
            if is_update:
                try:
                    instance = CoolingSystemChiller.objects.get(id=system_id, building=building)
                except CoolingSystemChiller.DoesNotExist:
                    return Response({"success": False, "errors": {"cooling_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)
                form = CoolingSystemChillerForm(data, instance=instance)
            else:
                form = CoolingSystemChillerForm(data)
        elif ctype == "air_conditioner":
            if is_update:
                try:
                    instance = CoolingSystemAirConditioner.objects.get(id=system_id, building=building)
                except CoolingSystemAirConditioner.DoesNotExist:
                    return Response({"success": False, "errors": {"cooling_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)
                form = CoolingSystemAirConditionerForm(data, instance=instance)
            else:
                form = CoolingSystemAirConditionerForm(data)
        else:
            return Response({"success": False, "errors": {"cooling_system_type": ["Must be 'chiller' or 'air_conditioner'."]}}, status=status.HTTP_400_BAD_REQUEST)

        if not form.is_valid():
            return Response({"success": False, "errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            system = form.save(commit=False)
            system.building = building
            system.save()

        return Response({
            "success": True,
            "cooling_system": {"id": system.id, "cooling_system_type": ctype},
        }, status=status.HTTP_200_OK if is_update else status.HTTP_201_CREATED)

    def delete(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        system_id = data.get("cooling_system_id")
        ctype = data.get("cooling_system_type")

        model = CoolingSystemChiller if ctype == "chiller" else CoolingSystemAirConditioner
        try:
            system = model.objects.get(id=system_id, building=building)
        except model.DoesNotExist:
            return Response({"success": False, "errors": {"cooling_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)

        system.delete()
        return Response({"success": True})


# ---------------------------------------------------------------------------
# Step 5 — Ventilation Systems (CRUD)
# ---------------------------------------------------------------------------

class BuildingAddVentilationSystemView(APIView):
    """
    POST /api/buildings/add/ventilation-systems/  — create/update
    DELETE /api/buildings/add/ventilation-systems/ — delete
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        system_id = data.get("ventilation_system_id")
        is_update = bool(system_id)

        if is_update:
            try:
                instance = VentilationSystem.objects.get(id=system_id, building=building)
            except VentilationSystem.DoesNotExist:
                return Response({"success": False, "errors": {"ventilation_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)
            form = VentilationSystemForm(data, instance=instance)
        else:
            form = VentilationSystemForm(data)

        if not form.is_valid():
            return Response({"success": False, "errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            system = form.save(commit=False)
            system.building = building
            system.save()

        return Response({"success": True, "ventilation_system": {"id": system.id}},
                        status=status.HTTP_200_OK if is_update else status.HTTP_201_CREATED)

    def delete(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        system_id = data.get("ventilation_system_id")
        try:
            system = VentilationSystem.objects.get(id=system_id, building=building)
        except VentilationSystem.DoesNotExist:
            return Response({"success": False, "errors": {"ventilation_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)

        system.delete()
        return Response({"success": True})


# ---------------------------------------------------------------------------
# Step 6 — Lighting Systems (CRUD)
# ---------------------------------------------------------------------------

class BuildingAddLightingSystemView(APIView):
    """
    POST /api/buildings/add/lighting-systems/  — create/update
    DELETE /api/buildings/add/lighting-systems/ — delete
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        system_id = data.get("lighting_system_id")
        is_update = bool(system_id)

        if is_update:
            try:
                instance = LightingSystem.objects.get(id=system_id, building=building)
            except LightingSystem.DoesNotExist:
                return Response({"success": False, "errors": {"lighting_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)
            form = LightingSystemForm(data, instance=instance)
        else:
            form = LightingSystemForm(data)

        if not form.is_valid():
            return Response({"success": False, "errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            system = form.save(commit=False)
            system.building = building
            system.save()

        return Response({"success": True, "lighting_system": {"id": system.id}},
                        status=status.HTTP_200_OK if is_update else status.HTTP_201_CREATED)

    def delete(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        system_id = data.get("lighting_system_id")
        try:
            system = LightingSystem.objects.get(id=system_id, building=building)
        except LightingSystem.DoesNotExist:
            return Response({"success": False, "errors": {"lighting_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)

        system.delete()
        return Response({"success": True})


# ---------------------------------------------------------------------------
# Step 7 — Lift & Escalator (CRUD)
# ---------------------------------------------------------------------------

class BuildingAddLiftEscalatorView(APIView):
    """
    POST /api/buildings/add/lift-escalator/   — create/update (one per building)
    DELETE /api/buildings/add/lift-escalator/ — delete
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        system_id = data.get("lift_escalator_system_id")
        is_update = bool(system_id)

        if is_update:
            try:
                instance = LiftEscalatorSystem.objects.get(id=system_id, building=building)
            except LiftEscalatorSystem.DoesNotExist:
                return Response({"success": False, "errors": {"lift_escalator_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)
            form = LiftEscalatorSystemForm(data, instance=instance)
        else:
            if LiftEscalatorSystem.objects.filter(building=building).exists():
                return Response(
                    {"success": False, "errors": {"building": ["Only one lift & escalator system is allowed per building."]}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            form = LiftEscalatorSystemForm(data)

        if not form.is_valid():
            return Response({"success": False, "errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            system = form.save(commit=False)
            system.building = building
            system.save()

        return Response(
            {"success": True, "lift_escalator_system": {"id": system.id, "number_of_lifts": system.number_of_lifts}},
            status=status.HTTP_200_OK if is_update else status.HTTP_201_CREATED,
        )

    def delete(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        system_id = data.get("lift_escalator_system_id")
        try:
            system = LiftEscalatorSystem.objects.get(id=system_id, building=building)
        except LiftEscalatorSystem.DoesNotExist:
            return Response({"success": False, "errors": {"lift_escalator_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)

        system.delete()
        return Response({"success": True})


# ---------------------------------------------------------------------------
# Step 8 — Hot Water Systems (CRUD)
# ---------------------------------------------------------------------------

class BuildingAddHotWaterSystemView(APIView):
    """
    POST /api/buildings/add/hot-water-systems/   — create/update
    DELETE /api/buildings/add/hot-water-systems/ — delete
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        system_id = data.get("hot_water_system_id")
        is_update = bool(system_id)

        if is_update:
            try:
                instance = HotWaterSystem.objects.get(id=system_id, building=building)
            except HotWaterSystem.DoesNotExist:
                return Response({"success": False, "errors": {"hot_water_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)
            form = HotWaterSystemForm(data, instance=instance)
        else:
            form = HotWaterSystemForm(data)

        if not form.is_valid():
            return Response({"success": False, "errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            system = form.save(commit=False)
            system.building = building
            system.save()

        return Response({"success": True, "hot_water_system": {"id": system.id}},
                        status=status.HTTP_200_OK if is_update else status.HTTP_201_CREATED)

    def delete(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        system_id = data.get("hot_water_system_id")
        try:
            system = HotWaterSystem.objects.get(id=system_id, building=building)
        except HotWaterSystem.DoesNotExist:
            return Response({"success": False, "errors": {"hot_water_system_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)

        system.delete()
        return Response({"success": True})


# ---------------------------------------------------------------------------
# Step 9 — Energy Carriers (Operational Products)
# ---------------------------------------------------------------------------

class BuildingAddEnergyCarriersView(APIView):
    """
    POST /api/buildings/add/energy-carriers/

    Saves/replaces operational products for the building.

    Body:
    {
        "building_uuid": str,
        "products": [
            {"epd_id": str (UUID), "quantity": float, "input_unit": str, "description": str},
            ...
        ]
    }
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        products_payload = data.get("products", [])
        errors = {}
        to_save = []

        for idx, item in enumerate(products_payload):
            label = f"product {idx + 1}"
            epd_id = _str(item.get("epd_id"))
            quantity_raw = item.get("quantity")
            input_unit = _str(item.get("input_unit"))
            description = _str(item.get("description"))

            if not epd_id:
                errors[label] = {"epd_id": ["EPD ID is required."]}
                continue

            try:
                epd = EPD.objects.get(pk=uuid_lib.UUID(epd_id))
            except (ValueError, EPD.DoesNotExist):
                errors[label] = {"epd_id": [f"EPD not found: {epd_id}"]}
                continue

            try:
                quantity = float(quantity_raw)
                if quantity <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors[label] = {"quantity": ["Must be a positive number."]}
                continue

            if not input_unit:
                errors[label] = {"input_unit": ["Unit is required."]}
                continue

            to_save.append({"epd": epd, "quantity": quantity, "input_unit": input_unit, "description": description})

        if errors:
            return Response({"success": False, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            OperationalProduct.objects.filter(building=building).delete()
            for item in to_save:
                OperationalProduct.objects.create(
                    building=building,
                    epd=item["epd"],
                    quantity=item["quantity"],
                    input_unit=item["input_unit"],
                    description=item["description"],
                )

        logger.info("API Add energy carriers: %d product(s) saved for building %s by %s", len(to_save), building.uuid, request.user)
        return Response({"success": True, "saved_count": len(to_save), "building_uuid": str(building.uuid)})


# ---------------------------------------------------------------------------
# Step 10 — Structural Components (CRUD)
# ---------------------------------------------------------------------------

class BuildingAddStructuralComponentView(APIView):
    """
    POST /api/buildings/add/structural-components/

    Creates one assembly + links it to the building.

    Body:
    {
        "building_uuid": str,
        "title": str,
        "category_id": int (AssemblyCategory PK),
        "technique_name": str (optional),
        "dimension": str (area|length|mass|volume|pieces|pcs),
        "quantity": float,
        "unit": str (m2|m3|m|kg|ton|pcs),
        "comment": str (optional),
        "reporting_life_cycle": int (default 50),
        "materials": [
            {"epd_id": str (UUID), "quantity": float, "input_unit": str},
            ...
        ]
    }

    DELETE /api/buildings/add/structural-components/
    {
        "building_uuid": str,
        "building_assembly_id": int (BuildingAssembly PK)
    }
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from pages.models.assembly import AssemblyCategory
        from pages.views.building.import_building import DIMENSION_MAP, STRUCTURAL_UNIT_MAP

        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        errors = {}

        title = _str(data.get("title")) or "Unnamed Assembly"
        category_id = data.get("category_id")
        technique_name = _str(data.get("technique_name"))
        dim_raw = _str(data.get("dimension", "")).lower()
        qty_raw = data.get("quantity")
        unit_raw = _str(data.get("unit", "")).lower()
        comment = _str(data.get("comment"))
        reporting_life_cycle = int(data.get("reporting_life_cycle") or 50)
        materials_payload = data.get("materials", [])

        try:
            category = AssemblyCategory.objects.get(pk=category_id)
        except (AssemblyCategory.DoesNotExist, TypeError, ValueError):
            errors["category_id"] = "Unknown building component category."

        dim_val = DIMENSION_MAP.get(dim_raw)
        if not dim_val:
            errors["dimension"] = f"Unknown dimension '{dim_raw}'."

        try:
            asm_qty = float(qty_raw)
            if asm_qty <= 0:
                raise ValueError
        except (ValueError, TypeError):
            errors["quantity"] = f"Invalid quantity."

        asm_unit = STRUCTURAL_UNIT_MAP.get(unit_raw)
        if not asm_unit:
            errors["unit"] = f"Unknown unit '{unit_raw}'."

        materials = []
        for idx, mat in enumerate(materials_payload):
            mat_label = f"material {idx + 1}"
            epd_id = _str(mat.get("epd_id"))
            mat_qty_raw = mat.get("quantity")
            mat_unit = _str(mat.get("input_unit"))

            if not epd_id:
                errors[mat_label] = {"epd_id": ["Required."]}
                continue
            try:
                epd = EPD.objects.get(pk=uuid_lib.UUID(epd_id))
            except (ValueError, EPD.DoesNotExist):
                errors[mat_label] = {"epd_id": [f"EPD not found: {epd_id}"]}
                continue
            try:
                mat_qty = float(mat_qty_raw)
                if mat_qty <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors[mat_label] = {"quantity": ["Must be a positive number."]}
                continue

            materials.append({"epd": epd, "quantity": mat_qty, "input_unit": mat_unit})

        if errors:
            return Response({"success": False, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        classification = None
        if technique_name:
            try:
                technique = AssemblyTechnique.objects.get(name__iexact=technique_name.strip())
                classification = AssemblyCategoryTechnique.objects.filter(
                    category=category, technique=technique,
                ).first()
            except AssemblyTechnique.DoesNotExist:
                pass

        with transaction.atomic():
            assembly = Assembly.objects.create(
                created_by=request.user,
                name=title,
                comment=comment,
                dimension=dim_val,
                mode=AssemblyMode.CUSTOM,
                is_boq=False,
                is_template=False,
                public=False,
                draft=False,
            )
            for mat in materials:
                StructuralProduct.objects.create(
                    epd=mat["epd"],
                    assembly=assembly,
                    quantity=mat["quantity"],
                    input_unit=mat["input_unit"],
                    classification=classification,
                )
            ba = BuildingAssembly.objects.create(
                building=building,
                assembly=assembly,
                quantity=asm_qty,
                reporting_life_cycle=reporting_life_cycle,
            )

        logger.info("API Add structural: assembly %s created for building %s by %s", assembly.id, building.uuid, request.user)
        return Response({"success": True, "building_assembly_id": ba.id, "assembly_id": assembly.id}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        ba_id = data.get("building_assembly_id")
        try:
            ba = BuildingAssembly.objects.get(id=ba_id, building=building)
        except BuildingAssembly.DoesNotExist:
            return Response({"success": False, "errors": {"building_assembly_id": ["Not found."]}}, status=status.HTTP_404_NOT_FOUND)

        assembly = ba.assembly
        ba.delete()
        # Delete the assembly itself if it's not linked to other buildings
        if not BuildingAssembly.objects.filter(assembly=assembly).exists():
            assembly.delete()

        return Response({"success": True})


# ---------------------------------------------------------------------------
# Complete — publish the building
# ---------------------------------------------------------------------------

class BuildingAddCompleteView(APIView):
    """
    POST /api/buildings/add/complete/
    Marks a building as published (draft=False).
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        building, err = _get_building_or_error(request, _str(request.data.get("building_uuid")))
        if err:
            return err

        building.draft = False
        building.save()

        logger.info("API Add: building %s published by %s", building.uuid, request.user)
        return Response({"success": True, "building_uuid": str(building.uuid)})
