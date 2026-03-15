import logging
import uuid as uuid_lib

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdminUser
from api.serializers.organisation import AdminBuildingSerializer
from api.utils import paginate_queryset
from pages.models.assembly import (
    Assembly, AssemblyCategory, AssemblyDimension, AssemblyMode,
    AssemblyCategoryTechnique, StructuralProduct,
)
from pages.models.building import Building, BuildingBoQFile, CategorySubcategory, OperationalProduct
from pages.models.epd import EPD, EPDType, Unit
from pages.models.organisation import Organisation
from pages.views.building.building_stats import (
    calculate_total_carbon_footprint,
    calculate_total_embodied_carbon,
    calculate_total_operational_carbon,
)
from pages.views.building.import_building import (
    _str,
    _bool_from_excel,
    _resolve_country,
    _resolve_region,
    _resolve_city,
    _resolve_building_type,
    _resolve_climate,
    _parse_cooling_rows,
    _parse_ventilation_rows,
    _parse_lighting_rows,
    _parse_hot_water_rows,
    _lookup_energy_carrier_epd,
    _get_structural_category_map,
    _lookup_structural_epd,
    COOLING_TAB_MAP,
    VENTILATION_TAB_MAP,
    LIGHTING_TAB_LAYOUT,
    HOT_WATER_TAB_MAP,
    DIMENSION_MAP,
    STRUCTURAL_UNIT_MAP,
)
from pages.forms.cooling_system_form import CoolingSystemAirConditionerForm, CoolingSystemChillerForm
from pages.forms.ventilation_system_form import VentilationSystemForm
from pages.forms.lighting_system_form import LightingSystemForm
from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm
from pages.forms.hot_water_system_form import HotWaterSystemForm
from pages.models.building_operation import LiftEscalatorSystem

logger = logging.getLogger(__name__)


def _buildings_queryset(request):
    """
    Return a Building queryset accessible by the requesting admin.
    Superadmin sees all buildings that belong to an organisation.
    Regular admin sees only buildings in their organisations.
    """
    qs = Building.objects.select_related(
        "country", "city", "region",
        "category__category", "category__subcategory",
        "created_by", "organisation", "climate_zone",
    )

    if request.user.is_superuser:
        qs = qs.filter(organisation__isnull=False)
    else:
        orgs = Organisation.objects.filter(memberships__user=request.user)
        qs = qs.filter(organisation__in=orgs)

    return qs


class BuildingListView(APIView):
    """
    GET /api/buildings/
    Lists all buildings across all organisations the admin can access.
    Superadmin sees all buildings that belong to any organisation.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = _buildings_queryset(request)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(city__name__icontains=search) |
                Q(country__name__icontains=search) |
                Q(category__category__name__icontains=search) |
                Q(category__subcategory__name__icontains=search) |
                Q(street__icontains=search)
            ).distinct()

        country = request.query_params.get("country", "").strip()
        if country:
            qs = qs.filter(country__name__icontains=country)

        city = request.query_params.get("city", "").strip()
        if city:
            qs = qs.filter(city__name__icontains=city)

        climate_zone = request.query_params.get("climate_zone", "").strip()
        if climate_zone:
            qs = qs.filter(climate_zone__name__iexact=climate_zone)

        draft = request.query_params.get("draft", "").strip().lower()
        if draft in ("true", "false"):
            qs = qs.filter(draft=(draft == "true"))

        organisation = request.query_params.get("organisation", "").strip()
        if organisation:
            qs = qs.filter(organisation__id=organisation)

        items, meta = paginate_queryset(qs, request)

        stats_map = {}
        for building in items:
            try:
                stats_map[str(building.pk)] = {
                    "total_carbon_footprint": calculate_total_carbon_footprint(building),
                    "total_embodied_carbon": calculate_total_embodied_carbon(building),
                    "total_operational_carbon": calculate_total_operational_carbon(building),
                }
            except Exception:
                stats_map[str(building.pk)] = {}

        serializer = AdminBuildingSerializer(items, many=True, context={"stats": stats_map})
        return Response({"results": serializer.data, "pagination": meta})


class BuildingDetailView(APIView):
    """
    GET /api/buildings/<pk>/
    Returns full detail for a single building.
    """
    permission_classes = [IsAdminUser]

    def _get_building(self, pk, request):
        try:
            qs = _buildings_queryset(request)
            return qs.get(pk=pk)
        except Building.DoesNotExist:
            return None

    def get(self, request, pk):
        building = self._get_building(pk, request)
        if building is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            stats = {
                str(building.pk): {
                    "total_carbon_footprint": calculate_total_carbon_footprint(building),
                    "total_embodied_carbon": calculate_total_embodied_carbon(building),
                    "total_operational_carbon": calculate_total_operational_carbon(building),
                }
            }
        except Exception:
            stats = {}
        serializer = AdminBuildingSerializer(building, context={"stats": stats})
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Import / Add building — step endpoints
# ---------------------------------------------------------------------------

class BuildingImportNameLocationView(APIView):
    """
    POST /api/buildings/import/name-location/
    Step 1: Create or update a building's name and location.
    Accepts organisation_id to link the building to an organisation.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        errors = {}

        building_name = _str(data.get("building_name"))
        address = _str(data.get("address"))
        country_name = _str(data.get("country"))
        region_name = _str(data.get("region"))
        city_name = _str(data.get("city"))
        longitude = data.get("longitude") or None
        latitude = data.get("latitude") or None
        building_uuid = _str(data.get("building_uuid"))
        organisation_id = _str(data.get("organisation_id"))

        if not building_name:
            errors["building_name"] = "Building name is required."
        if not address:
            errors["address"] = "Address is required."

        country, country_err = _resolve_country(country_name)
        if country_err:
            errors["country"] = country_err

        region = None
        if country and region_name:
            region, region_err = _resolve_region(region_name, country)
            if region_err:
                errors["region"] = region_err

        city = None
        if country:
            city, city_err = _resolve_city(city_name, country)
            if city_err:
                errors["city"] = city_err
        elif not city_name:
            errors["city"] = "City is required."

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

        try:
            longitude = float(longitude) if longitude else None
        except (ValueError, TypeError):
            longitude = None
        try:
            latitude = float(latitude) if latitude else None
        except (ValueError, TypeError):
            latitude = None

        if building_uuid:
            try:
                uuid_obj = uuid_lib.UUID(building_uuid)
                qs = _buildings_queryset(request)
                building = qs.get(uuid=uuid_obj)
                building.name = building_name
                building.street = address
                building.country = country
                building.region = region
                building.city = city
                building.longitude = longitude
                building.latitude = latitude
                if organisation:
                    building.organisation = organisation
                building.save()
            except (ValueError, Building.DoesNotExist):
                return Response(
                    {"success": False, "errors": {"__all__": ["Invalid building UUID."]}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            building = Building.objects.create(
                name=building_name,
                street=address,
                country=country,
                region=region,
                city=city,
                longitude=longitude,
                latitude=latitude,
                created_by=request.user,
                organisation=organisation,
                climate_zone=None,
                total_floor_area=100,
                reference_period=50,
            )

        logger.info("API Import Step 1: building %s saved by %s", building.uuid, request.user)
        return Response({"success": True, "building_uuid": str(building.uuid)})


class BuildingImportDetailsView(APIView):
    """
    POST /api/buildings/import/details/
    Step 2: Building type, climate zone, floor area, certification/BoQ files.
    Expects multipart/form-data.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        import os

        building_uuid_str = _str(request.data.get("building_uuid"))
        if not building_uuid_str:
            return Response(
                {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uuid_obj = uuid_lib.UUID(building_uuid_str)
            qs = _buildings_queryset(request)
            building = qs.get(uuid=uuid_obj)
        except (ValueError, Building.DoesNotExist):
            return Response(
                {"success": False, "errors": {"__all__": ["Building not found."]}},
                status=status.HTTP_404_NOT_FOUND,
            )

        errors = {}

        cat_subcat, bt_err = _resolve_building_type(_str(request.data.get("building_type")))
        if bt_err:
            errors["building_type"] = bt_err

        climate_value, climate_err = _resolve_climate(request.data.get("climate_type"))
        if climate_err:
            errors["climate_type"] = climate_err

        assessment_period_raw = _str(request.data.get("assessment_period"))
        assessment_period = None
        if not assessment_period_raw:
            errors["assessment_period"] = "Assessment period is required."
        else:
            try:
                assessment_period = int(float(assessment_period_raw))
                if assessment_period <= 0:
                    errors["assessment_period"] = "Assessment period must be a positive number."
            except (ValueError, TypeError):
                errors["assessment_period"] = "Assessment period must be a valid number."

        total_floor_area_raw = _str(request.data.get("total_floor_area"))
        total_floor_area = None
        if not total_floor_area_raw:
            errors["total_floor_area"] = "Total floor area is required."
        else:
            try:
                total_floor_area = float(total_floor_area_raw)
                if total_floor_area <= 0:
                    errors["total_floor_area"] = "Total floor area must be greater than zero."
            except (ValueError, TypeError):
                errors["total_floor_area"] = "Total floor area must be a valid number."

        conditioned_floor_area = None
        cfa_raw = _str(request.data.get("conditioned_floor_area"))
        if cfa_raw:
            try:
                conditioned_floor_area = float(cfa_raw)
            except (ValueError, TypeError):
                errors["conditioned_floor_area"] = "Conditioned floor area must be a valid number."

        construction_year = None
        cy_raw = _str(request.data.get("construction_year"))
        if cy_raw:
            try:
                construction_year = int(float(cy_raw))
            except (ValueError, TypeError):
                errors["construction_year"] = "Construction year must be a valid year."

        floors_below_ground = None
        fbg_raw = _str(request.data.get("floors_below_ground"))
        if fbg_raw:
            try:
                floors_below_ground = int(float(fbg_raw))
            except (ValueError, TypeError):
                errors["floors_below_ground"] = "Floors below ground must be a valid number."

        has_certification = _bool_from_excel(request.data.get("has_certification", "no"))
        has_boq = _bool_from_excel(request.data.get("has_boq", "no"))

        from pages.views.building.building_step_files import _validate_file

        if has_certification:
            cert_file = request.FILES.get("certification_file")
            if not cert_file:
                errors["certification_file"] = "A certification file is required when 'Has certification' is Yes."
            else:
                cert_err = _validate_file(cert_file)
                if cert_err:
                    errors["certification_file"] = f"Certification file: {cert_err}"

        if has_boq:
            boq_files = request.FILES.getlist("boq_files")
            if not boq_files:
                errors["boq_files"] = "At least one BoQ file is required when 'Has BoQ' is Yes."
            else:
                for f in boq_files:
                    boq_err = _validate_file(f)
                    if boq_err:
                        errors["boq_files"] = f"BoQ file '{f.name}': {boq_err}"
                        break

        if errors:
            return Response({"success": False, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        if cat_subcat:
            building.category = cat_subcat
        building.climate_zone = climate_value
        building.reference_period = assessment_period
        building.total_floor_area = total_floor_area

        if conditioned_floor_area is not None:
            building.cond_floor_area = conditioned_floor_area
        if construction_year is not None:
            building.construction_year = construction_year
        if floors_below_ground is not None:
            building.floors_below_ground = floors_below_ground

        building.has_certification = has_certification
        building.has_boq = has_boq

        if has_certification:
            cert_file = request.FILES.get("certification_file")
            if cert_file:
                if building.certification_file:
                    try:
                        old_path = building.certification_file.path
                        if os.path.isfile(old_path):
                            os.remove(old_path)
                    except Exception:
                        pass
                building.certification_file = cert_file
        else:
            if building.certification_file:
                try:
                    old_path = building.certification_file.path
                    if os.path.isfile(old_path):
                        os.remove(old_path)
                except Exception:
                    pass
                building.certification_file = None

        building.save()

        if has_boq:
            new_boq_files = request.FILES.getlist("boq_files")
            if new_boq_files:
                for old_file in building.boq_files.all():
                    try:
                        if os.path.isfile(old_file.file.path):
                            os.remove(old_file.file.path)
                    except Exception:
                        pass
                    old_file.delete()
                for f in new_boq_files:
                    BuildingBoQFile.objects.create(
                        building=building,
                        file=f,
                        original_filename=f.name,
                    )
        else:
            for old_file in building.boq_files.all():
                try:
                    if os.path.isfile(old_file.file.path):
                        os.remove(old_file.file.path)
                except Exception:
                    pass
                old_file.delete()

        logger.info("API Import Step 2: building %s details saved by %s", building.uuid, request.user)
        return Response({"success": True, "building_uuid": str(building.uuid)})


class BuildingImportOperationalScheduleView(APIView):
    """
    POST /api/buildings/import/operational-schedule/
    Step 3: Operational schedule and temperature settings.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data

        building_uuid_str = _str(data.get("building_uuid"))
        if not building_uuid_str:
            return Response(
                {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uuid_obj = uuid_lib.UUID(building_uuid_str)
            qs = _buildings_queryset(request)
            building = qs.get(uuid=uuid_obj)
        except (ValueError, Building.DoesNotExist):
            return Response(
                {"success": False, "errors": {"__all__": ["Building not found."]}},
                status=status.HTTP_404_NOT_FOUND,
            )

        from pages.views.building.import_building import _validate_int_range, _validate_decimal_range

        errors = {}

        num_residents, err = _validate_int_range(data.get("num_residents"), "Number of residents", 0, 100000)
        if err:
            errors["num_residents"] = err

        hours_per_workday, err = _validate_int_range(data.get("hours_per_workday"), "Hours per workday", 0, 24)
        if err:
            errors["hours_per_workday"] = err

        workdays_per_week, err = _validate_int_range(data.get("workdays_per_week"), "Workdays per week", 0, 7)
        if err:
            errors["workdays_per_week"] = err

        weeks_per_year, err = _validate_int_range(data.get("weeks_per_year"), "Weeks per year", 0, 52)
        if err:
            errors["weeks_per_year"] = err

        heating_temp, err = _validate_decimal_range(data.get("heating_temp"), "Heating temperature", 0, 120)
        if err:
            errors["heating_temp"] = err

        cooling_temp, err = _validate_decimal_range(data.get("cooling_temp"), "Cooling temperature", 0, 120)
        if err:
            errors["cooling_temp"] = err

        renewable_energy_percent, err = _validate_decimal_range(data.get("renewable_energy_percent"), "Renewable energy percent", 0, 100)
        if err:
            errors["renewable_energy_percent"] = err

        if errors:
            return Response({"success": False, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        fields = {
            "num_residents": num_residents,
            "hours_per_workday": hours_per_workday,
            "workdays_per_week": workdays_per_week,
            "weeks_per_year": weeks_per_year,
            "heating_temp": heating_temp,
            "cooling_temp": cooling_temp,
            "renewable_energy_percent": renewable_energy_percent,
        }
        for field, val in fields.items():
            if val is not None:
                setattr(building, field, val)

        heating_temp_unit = _str(data.get("heating_temp_unit")).upper()
        if heating_temp_unit in ("CELSIUS", "FAHRENHEIT"):
            building.heating_temp_unit = heating_temp_unit

        cooling_temp_unit = _str(data.get("cooling_temp_unit")).upper()
        if cooling_temp_unit in ("CELSIUS", "FAHRENHEIT"):
            building.cooling_temp_unit = cooling_temp_unit

        smart_system_raw = data.get("building_smart_system")
        if smart_system_raw is not None:
            building.building_smart_system = _bool_from_excel(smart_system_raw)

        building.save()

        logger.info("API Import Step 3: building %s operational schedule saved by %s", building.uuid, request.user)
        return Response({"success": True, "building_uuid": str(building.uuid)})


class BuildingCompleteView(APIView):
    """
    POST /api/buildings/import/complete/
    Marks a building as no longer draft (publishes it).
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        building_uuid_str = _str(request.data.get("building_uuid"))
        if not building_uuid_str:
            return Response(
                {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            uuid_obj = uuid_lib.UUID(building_uuid_str)
            qs = _buildings_queryset(request)
            building = qs.get(uuid=uuid_obj)
        except (ValueError, Building.DoesNotExist):
            return Response(
                {"success": False, "errors": {"__all__": ["Building not found."]}},
                status=status.HTTP_404_NOT_FOUND,
            )

        building.draft = False
        building.save()

        logger.info("API: building %s marked complete by %s", building.uuid, request.user)
        return Response({"success": True, "building_uuid": str(building.uuid)})


def _get_building_or_error(request, building_uuid_str):
    """Helper: resolve building UUID and return (building, error_response)."""
    if not building_uuid_str:
        return None, Response(
            {"success": False, "errors": {"__all__": ["building_uuid is required."]}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = _buildings_queryset(request).get(uuid=uuid_obj)
        return building, None
    except (ValueError, Building.DoesNotExist):
        return None, Response(
            {"success": False, "errors": {"__all__": ["Building not found."]}},
            status=status.HTTP_404_NOT_FOUND,
        )


class BuildingImportCoolingSystemsView(APIView):
    """
    POST /api/buildings/import/cooling-systems/
    Step 4: Import cooling systems from structured JSON payload.

    Expects JSON:
    {
        "building_uuid": str,
        "systems": [
            {"tab": "Air Conditioning", "rows": [[col0, col1, ...], ...]},
            {"tab": "Chiller", "rows": [[col0, col1, ...], ...]},
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

        systems_payload = data.get("systems", [])
        all_errors = {}
        to_save = []

        for tab_entry in systems_payload:
            tab_name = _str(tab_entry.get("tab", "")).lower().replace(" ", "")
            raw_rows = tab_entry.get("rows", [])

            tab_key = None
            for key in COOLING_TAB_MAP:
                if key.replace(" ", "") in tab_name or tab_name in key.replace(" ", ""):
                    tab_key = key
                    break

            if tab_key is None:
                continue

            parsed_rows = _parse_cooling_rows(tab_key, raw_rows)

            for row_idx, row_data in enumerate(parsed_rows):
                ctype = row_data.pop("cooling_system_type")
                label = f"{tab_entry.get('tab', tab_key)} row {row_idx + 1}"

                if ctype == 'chiller':
                    form = CoolingSystemChillerForm(row_data)
                else:
                    form = CoolingSystemAirConditionerForm(row_data)

                if form.is_valid():
                    to_save.append((form, ctype))
                else:
                    all_errors[label] = {
                        field: [str(e) for e in errs]
                        for field, errs in form.errors.items()
                    }

        if all_errors:
            return Response({"success": False, "errors": all_errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for form, ctype in to_save:
                system = form.save(commit=False)
                system.building = building
                system.save()

        logger.info("API Import cooling: %d system(s) saved for building %s by %s", len(to_save), building.uuid, request.user)
        return Response({"success": True, "saved_count": len(to_save), "building_uuid": str(building.uuid)})


class BuildingImportVentilationSystemsView(APIView):
    """
    POST /api/buildings/import/ventilation-systems/
    Step 5: Import ventilation systems from structured JSON payload.

    Expects JSON:
    {
        "building_uuid": str,
        "systems": [
            {"tab": "AHU", "rows": [[col0, col1, ...], ...]},
            {"tab": "FCU", "rows": [[col0, col1, ...], ...]},
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

        systems_payload = data.get("systems", [])
        all_errors = {}
        to_save = []

        for tab_entry in systems_payload:
            tab_name = _str(tab_entry.get("tab", "")).lower().strip()
            raw_rows = tab_entry.get("rows", [])

            vent_type = None
            for key, vtype in VENTILATION_TAB_MAP.items():
                if key in tab_name or tab_name in key:
                    vent_type = vtype
                    break

            if vent_type is None:
                continue

            parsed_rows = _parse_ventilation_rows(vent_type, raw_rows)

            for row_idx, row_data in enumerate(parsed_rows):
                label = f"{tab_entry.get('tab', tab_name)} row {row_idx + 1}"
                form = VentilationSystemForm(row_data)

                if form.is_valid():
                    to_save.append(form)
                else:
                    all_errors[label] = {
                        field: [str(e) for e in errs]
                        for field, errs in form.errors.items()
                    }

        if all_errors:
            return Response({"success": False, "errors": all_errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for form in to_save:
                system = form.save(commit=False)
                system.building = building
                system.save()

        logger.info("API Import ventilation: %d system(s) saved for building %s by %s", len(to_save), building.uuid, request.user)
        return Response({"success": True, "saved_count": len(to_save), "building_uuid": str(building.uuid)})


class BuildingImportLightingSystemsView(APIView):
    """
    POST /api/buildings/import/lighting-systems/
    Step 6: Import lighting systems from structured JSON payload.

    Expects JSON:
    {
        "building_uuid": str,
        "systems": [
            {"tab": "LED", "rows": [[col0, col1, ...], ...]},
            {"tab": "Fluorescent", "rows": [[col0, col1, ...], ...]},
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

        systems_payload = data.get("systems", [])
        all_errors = {}
        to_save = []

        for tab_entry in systems_payload:
            tab_name = _str(tab_entry.get("tab", "")).lower().strip()
            raw_rows = tab_entry.get("rows", [])

            tab_layout = None
            for key in LIGHTING_TAB_LAYOUT:
                if key in tab_name or tab_name in key:
                    tab_layout = key
                    break

            if tab_layout is None:
                continue

            parsed_rows = _parse_lighting_rows(tab_layout, raw_rows)

            for row_idx, row_data in enumerate(parsed_rows):
                label = f"{tab_entry.get('tab', tab_name)} row {row_idx + 1}"
                form = LightingSystemForm(row_data)

                if form.is_valid():
                    to_save.append(form)
                else:
                    all_errors[label] = {
                        field: [str(e) for e in errs]
                        for field, errs in form.errors.items()
                    }

        if all_errors:
            return Response({"success": False, "errors": all_errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for form in to_save:
                system = form.save(commit=False)
                system.building = building
                system.save()

        logger.info("API Import lighting: %d system(s) saved for building %s by %s", len(to_save), building.uuid, request.user)
        return Response({"success": True, "saved_count": len(to_save), "building_uuid": str(building.uuid)})


class BuildingImportLiftEscalatorView(APIView):
    """
    POST /api/buildings/import/lift-escalator/
    Step 7: Import lift & escalator system.

    Only one lift & escalator system is allowed per building.
    If the row is empty, the step is silently skipped.

    Expects JSON:
    {
        "building_uuid": str,
        "rows": [ [number_of_lifts, lift_regenerative_features, vvvf_sleep_mode], ... ]
    }
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        raw_rows = data.get("rows", [])

        row_data = None
        for raw_row in raw_rows:
            row = list(raw_row) + [None] * 5
            num_lifts_raw = _str(row[0])
            if num_lifts_raw:
                row_data = {
                    'number_of_lifts':           num_lifts_raw,
                    'lift_regenerative_features': _str(row[1]) or 'no',
                    'vvvf_sleep_mode':            _str(row[2]) or 'no',
                }
                break

        if row_data is None:
            return Response({"success": True, "saved_count": 0, "building_uuid": str(building.uuid)})

        existing = LiftEscalatorSystem.objects.filter(building=building).first()
        form = LiftEscalatorSystemForm(row_data, instance=existing)
        if not form.is_valid():
            return Response({"success": False, "errors": dict(form.errors)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            system = form.save(commit=False)
            system.building = building
            system.save()

        logger.info("API Import lift: system saved for building %s by %s", building.uuid, request.user)
        return Response({"success": True, "saved_count": 1, "building_uuid": str(building.uuid)})


class BuildingImportHotWaterSystemsView(APIView):
    """
    POST /api/buildings/import/hot-water-systems/
    Step 8: Import hot water systems from structured JSON payload.

    Expects JSON:
    {
        "building_uuid": str,
        "systems": [
            {"tab": "Boiler", "rows": [[col0, col1, ...], ...]},
            {"tab": "Heat Pump", "rows": [[col0, col1, ...], ...]},
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

        systems_payload = data.get("systems", [])
        all_errors = {}
        to_save = []

        for tab_entry in systems_payload:
            tab_name = _str(tab_entry.get("tab", "")).lower().strip()
            raw_rows = tab_entry.get("rows", [])

            hws_type = None
            for key, val in HOT_WATER_TAB_MAP.items():
                if key in tab_name or tab_name in key:
                    hws_type = val
                    break

            if hws_type is None:
                continue

            parsed_rows = _parse_hot_water_rows(hws_type, raw_rows)

            for row_idx, row_data in enumerate(parsed_rows):
                label = f"{tab_entry.get('tab', tab_name)} row {row_idx + 1}"
                form = HotWaterSystemForm(row_data)

                if form.is_valid():
                    to_save.append(form)
                else:
                    all_errors[label] = {
                        field: [str(e) for e in errs]
                        for field, errs in form.errors.items()
                    }

        if all_errors:
            return Response({"success": False, "errors": all_errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for form in to_save:
                system = form.save(commit=False)
                system.building = building
                system.save()

        logger.info("API Import hot water: %d system(s) saved for building %s by %s", len(to_save), building.uuid, request.user)
        return Response({"success": True, "saved_count": len(to_save), "building_uuid": str(building.uuid)})


class BuildingImportEnergyCarriersView(APIView):
    """
    POST /api/buildings/import/energy-carriers/
    Step 9: Import operational energy carriers.

    Existing OperationalProducts for the building are replaced.

    Expects JSON:
    {
        "building_uuid": str,
        "rows": [ [name, description, quantity, unit], ... ]
    }
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        raw_rows = data.get("rows", [])
        if not raw_rows:
            return Response({"success": True, "saved_count": 0, "building_uuid": str(building.uuid)})

        errors = {}
        to_save = []

        unit_norm_map = {
            'kwh': 'kwh', 'kilowatt hour': 'kwh', 'kilowatt-hour': 'kwh',
            'kg': 'kg', 'kilogram': 'kg',
            'm3': 'm3', 'm³': 'm3', 'cubic meter': 'm3', 'cubic metre': 'm3',
            'l': 'l', 'liter': 'l', 'litre': 'l', 'liter ': 'l',
        }

        for row_idx, raw_row in enumerate(raw_rows):
            row = list(raw_row) + [None] * 5
            label = f"row {row_idx + 1}"

            def cell(i):
                v = row[i]
                return '' if v is None else str(v).strip()

            name_raw = cell(0)
            description = cell(1)
            quantity_raw = cell(2)
            unit_raw = cell(3).lower()

            if not name_raw:
                continue

            if not quantity_raw:
                errors[label] = {"quantity": ["Quantity is required."]}
                continue
            try:
                quantity = float(quantity_raw)
                if quantity <= 0:
                    errors[label] = {"quantity": ["Quantity must be greater than 0."]}
                    continue
            except (ValueError, TypeError):
                errors[label] = {"quantity": [f"Invalid quantity: '{quantity_raw}'."]}
                continue

            if not unit_raw:
                errors[label] = {"unit": ["Quantity unit is required."]}
                continue

            unit_norm = unit_norm_map.get(unit_raw, unit_raw)

            epd, epd_error = _lookup_energy_carrier_epd(name_raw)
            if epd_error:
                errors[label] = {"name": [epd_error]}
                continue

            available = epd.get_available_units() or {epd.declared_unit}
            available_lower = {str(u).lower() for u in available}
            if unit_norm not in available_lower and unit_raw not in available_lower:
                errors[label] = {
                    "unit": [
                        f"Unit '{unit_raw}' is not valid for '{epd.name}'. "
                        f"Accepted: {', '.join(sorted(available_lower))}."
                    ]
                }
                continue

            to_save.append({
                "epd": epd,
                "quantity": quantity,
                "input_unit": unit_norm,
                "description": description,
            })

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

        logger.info("API Import energy carriers: %d product(s) saved for building %s by %s", len(to_save), building.uuid, request.user)
        return Response({"success": True, "saved_count": len(to_save), "building_uuid": str(building.uuid)})


class BuildingImportStructuralComponentsView(APIView):
    """
    POST /api/buildings/import/structural-components/
    Step 10: Import structural components (by component).

    Expects JSON:
    {
        "building_uuid": str,
        "rows": [ [col0..col16], ... ]   (data rows only, headers stripped by client)
    }

    Column layout:
      0:  Title
      1:  Building Component  (→ AssemblyCategory)
      2:  Construction Technique
      3:  Dimension
      4:  Quantity
      5:  Units
      6:  Comment
      8:  EPD Name      (added material)
      9:  Country       (added material country)
      10: Quantity      (added material quantity)
      11: Units         (added material unit)
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        building, err = _get_building_or_error(request, _str(data.get("building_uuid")))
        if err:
            return err

        raw_rows = data.get("rows", [])
        if not raw_rows:
            return Response({"success": True, "saved_count": 0, "building_uuid": str(building.uuid)})

        cat_map = _get_structural_category_map()
        errors = {}
        assemblies_to_create = []
        current_assembly = None

        for row_idx, raw_row in enumerate(raw_rows):
            row = list(raw_row) + [None] * 17
            label = f"row {row_idx + 1}"

            def cell(i):
                v = row[i]
                return '' if v is None else str(v).strip()

            title = cell(0)
            comp_raw = cell(1)
            tech_raw = cell(2)
            dim_raw = cell(3)
            qty_raw = cell(4)
            unit_raw = cell(5)
            comment = cell(6)
            epd_name = cell(8)
            epd_country = cell(9)
            epd_qty = cell(10)
            epd_unit = cell(11)

            # Separator row
            if comp_raw and not tech_raw and not qty_raw:
                current_assembly = None
                continue

            # New assembly row
            if comp_raw and qty_raw:
                cat = cat_map.get(comp_raw.lower().strip())
                if cat is None:
                    errors[label] = {"building_component": [f"Unknown building component '{comp_raw}'."]}
                    current_assembly = None
                    continue

                dim_val = DIMENSION_MAP.get(dim_raw.lower().strip())
                if not dim_val:
                    errors[label] = {"dimension": [f"Unknown dimension '{dim_raw}'."]}
                    current_assembly = None
                    continue

                try:
                    asm_qty = float(qty_raw)
                    if asm_qty <= 0:
                        raise ValueError
                except (ValueError, TypeError):
                    errors[label] = {"quantity": [f"Invalid quantity '{qty_raw}'."]}
                    current_assembly = None
                    continue

                asm_unit = STRUCTURAL_UNIT_MAP.get(unit_raw.lower())
                if not asm_unit:
                    errors[label] = {"unit": [f"Unknown unit '{unit_raw}'."]}
                    current_assembly = None
                    continue

                current_assembly = {
                    "title": title or comp_raw,
                    "category": cat,
                    "technique_name": tech_raw,
                    "dimension": dim_val,
                    "quantity": asm_qty,
                    "unit": asm_unit,
                    "comment": comment,
                    "materials": [],
                }
                assemblies_to_create.append(current_assembly)

            # Material row
            if epd_name and epd_qty:
                if current_assembly is None:
                    errors[label] = {"epd": ["Material row found without a preceding assembly row."]}
                    continue

                try:
                    mat_qty = float(epd_qty)
                    if mat_qty <= 0:
                        raise ValueError
                except (ValueError, TypeError):
                    errors[label] = {"epd_quantity": [f"Invalid material quantity '{epd_qty}'."]}
                    continue

                epd, epd_error = _lookup_structural_epd(epd_name, epd_country)
                if epd_error:
                    errors[label] = {"epd_name": [epd_error]}
                    continue

                from pages.views.assembly.epd_dimension_info import get_epd_dimension_info
                _, expected_unit = get_epd_dimension_info(current_assembly["dimension"], epd.declared_unit)

                current_assembly["materials"].append({
                    "epd": epd,
                    "quantity": mat_qty,
                    "unit": expected_unit,
                })

        assemblies_to_create = [a for a in assemblies_to_create if a["materials"]]

        if errors:
            return Response({"success": False, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        if not assemblies_to_create:
            return Response({"success": True, "saved_count": 0, "building_uuid": str(building.uuid)})

        from pages.models.assembly import AssemblyTechnique

        saved_count = 0
        with transaction.atomic():
            for asm_data in assemblies_to_create:
                classification = None
                if asm_data["technique_name"]:
                    try:
                        technique = AssemblyTechnique.objects.get(
                            name__iexact=asm_data["technique_name"].strip()
                        )
                        classification = AssemblyCategoryTechnique.objects.filter(
                            category=asm_data["category"],
                            technique=technique,
                        ).first()
                    except AssemblyTechnique.DoesNotExist:
                        pass

                assembly = Assembly.objects.create(
                    created_by=request.user,
                    name=asm_data["title"],
                    comment=asm_data["comment"],
                    dimension=asm_data["dimension"],
                    mode=AssemblyMode.CUSTOM,
                    is_boq=False,
                    is_template=False,
                    public=False,
                    draft=False,
                )

                for mat in asm_data["materials"]:
                    StructuralProduct.objects.create(
                        epd=mat["epd"],
                        assembly=assembly,
                        quantity=mat["quantity"],
                        input_unit=mat["unit"],
                        classification=classification,
                    )

                from pages.models.building import BuildingAssembly
                BuildingAssembly.objects.create(
                    building=building,
                    assembly=assembly,
                    quantity=asm_data["quantity"],
                    reporting_life_cycle=50,
                )

                saved_count += 1

        logger.info("API Import structural: %d assembly(ies) saved for building %s by %s", saved_count, building.uuid, request.user)
        return Response({"success": True, "saved_count": saved_count, "building_uuid": str(building.uuid)})