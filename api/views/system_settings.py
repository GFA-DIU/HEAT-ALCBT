import logging

from cities_light.models import Country, Region
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomCity
from api.permissions import IsAdminUser
from api.utils import paginate_queryset, parse_csv, render_csv_response
from api.serializers.system_settings import (
    # Countries
    CountryListSerializer,
    CountryDetailSerializer,
    CountryCreateSerializer,
    CountryUpdateSerializer,
    # Climate types
    ClimateTypeListSerializer,
    ClimateTypeDetailSerializer,
    ClimateTypeCreateSerializer,
    ClimateTypeUpdateSerializer,
    # Building types
    BuildingTypeListSerializer,
    BuildingTypeDetailSerializer,
    BuildingTypeCreateSerializer,
    BuildingTypeUpdateSerializer,
)
from pages.models.building import Building, BuildingCategory, BuildingSubcategory, CategorySubcategory
from pages.models.climate_type import ClimateType

logger = logging.getLogger(__name__)


# ===========================================================================
# Countries
# ===========================================================================

class CountryListCreateView(APIView):
    """
    GET  /api/system-settings/countries/       — list countries (paginated, searchable)
    POST /api/system-settings/countries/       — create a new country with cities
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = Country.objects.all().order_by("name")
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        page_obj, meta = paginate_queryset(qs, request)
        return Response({"results": CountryListSerializer(page_obj, many=True).data, "pagination": meta})

    def post(self, request):
        serializer = CountryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            country = Country(name=serializer.validated_data["name"])
            country.save()

            for city_name in serializer.validated_data.get("cities", []):
                name = city_name.strip()
                if name:
                    CustomCity.objects.get_or_create(name=name, country=country)

        return Response(CountryDetailSerializer(country).data, status=status.HTTP_201_CREATED)


class CountryRegionsView(APIView):
    """
    GET /api/system-settings/countries/<pk>/regions/
    Returns all regions (states/provinces) for a given country.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        try:
            country = Country.objects.get(pk=pk)
        except Country.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        qs = Region.objects.filter(country=country).order_by("name")
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)

        data = [{"id": r.id, "name": r.name} for r in qs]
        return Response({"results": data})


class CountryCitiesView(APIView):
    """
    GET /api/system-settings/countries/<pk>/cities/
    Returns all cities for a given country (id + name), optionally filtered by ?search=.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        try:
            country = Country.objects.get(pk=pk)
        except Country.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        qs = CustomCity.objects.filter(country=country).order_by("name")
        region_id = request.query_params.get("region_id", "").strip()
        if region_id:
            qs = qs.filter(region_id=region_id)
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)

        from api.serializers.system_settings import CitySerializer
        return Response({"results": CitySerializer(qs, many=True).data})


class CountryDetailView(APIView):
    """
    GET   /api/system-settings/countries/<pk>/  — country detail with cities
    PATCH /api/system-settings/countries/<pk>/  — edit country name or cities
    """
    permission_classes = [IsAdminUser]

    def _get_country(self, pk):
        try:
            return Country.objects.get(pk=pk)
        except Country.DoesNotExist:
            return None

    def get(self, request, pk):
        country = self._get_country(pk)
        if not country:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CountryDetailSerializer(country).data)

    def patch(self, request, pk):
        country = self._get_country(pk)
        if not country:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = CountryUpdateSerializer(instance=country, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if "name" in serializer.validated_data:
                country.name = serializer.validated_data["name"]
                country.save(update_fields=["name"])

            for city_name in serializer.validated_data.get("add_cities", []):
                name = city_name.strip()
                if name:
                    CustomCity.objects.get_or_create(name=name, country=country)

            for item in serializer.validated_data.get("update_cities", []):
                try:
                    city = CustomCity.objects.get(id=int(item["id"]), country=country)
                    city.name = item["name"].strip()
                    city.save(update_fields=["name"])
                except (CustomCity.DoesNotExist, KeyError, ValueError):
                    pass

        return Response(CountryDetailSerializer(country).data)


class CountryImportView(APIView):
    """
    POST /api/system-settings/countries/import/
    CSV format: first column = country name, subsequent columns = city names
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rows = parse_csv(file)
        except Exception as e:
            return Response({"detail": f"Could not parse CSV: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        created_countries = 0
        created_cities = 0

        with transaction.atomic():
            for row in rows:
                if not row:
                    continue
                country_name = row[0].strip()
                if not country_name:
                    continue
                country, c_created = Country.objects.get_or_create(name=country_name)
                if c_created:
                    created_countries += 1
                for city_name in row[1:]:
                    name = city_name.strip()
                    if name:
                        _, city_created = CustomCity.objects.get_or_create(name=name, country=country)
                        if city_created:
                            created_cities += 1

        return Response({
            "detail": f"Import complete. {created_countries} countries and {created_cities} cities created."
        }, status=status.HTTP_201_CREATED)


class CountryExportView(APIView):
    """
    GET /api/system-settings/countries/export/
    Exports all countries and their cities as CSV.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = [["country", "city_1", "city_2", "..."]]
        for country in Country.objects.order_by("name"):
            cities = list(CustomCity.objects.filter(country=country).order_by("name").values_list("name", flat=True))
            rows.append([country.name] + cities)
        return render_csv_response(rows, "countries_export.csv")


# ===========================================================================
# Climate Types
# ===========================================================================

class ClimateTypeListCreateView(APIView):
    """
    GET  /api/system-settings/climate-types/   — list (paginated, searchable)
    POST /api/system-settings/climate-types/   — create new climate type
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = ClimateType.objects.all()
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        page_obj, meta = paginate_queryset(qs, request)
        return Response({"results": ClimateTypeListSerializer(page_obj, many=True).data, "pagination": meta})

    def post(self, request):
        serializer = ClimateTypeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        climate_type = serializer.save()
        return Response(ClimateTypeDetailSerializer(climate_type).data, status=status.HTTP_201_CREATED)


class ClimateTypeDetailView(APIView):
    """
    GET   /api/system-settings/climate-types/<pk>/  — detail
    PATCH /api/system-settings/climate-types/<pk>/  — edit (also updates buildings)
    """
    permission_classes = [IsAdminUser]

    def _get_obj(self, pk):
        try:
            return ClimateType.objects.get(pk=pk)
        except ClimateType.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_obj(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ClimateTypeDetailSerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get_obj(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ClimateTypeUpdateSerializer(obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        climate_type = serializer.save()
        return Response(ClimateTypeDetailSerializer(climate_type).data)


class ClimateTypeImportView(APIView):
    """
    POST /api/system-settings/climate-types/import/
    CSV format: name, description
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rows = parse_csv(file)
        except Exception as e:
            return Response({"detail": f"Could not parse CSV: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        with transaction.atomic():
            for row in rows:
                if not row:
                    continue
                name = row[0].strip()
                if not name:
                    continue
                description = row[1].strip() if len(row) > 1 else ""
                _, was_created = ClimateType.objects.get_or_create(
                    name=name, defaults={"description": description}
                )
                if was_created:
                    created += 1

        return Response({"detail": f"Import complete. {created} climate types created."}, status=status.HTTP_201_CREATED)


class ClimateTypeExportView(APIView):
    """
    GET /api/system-settings/climate-types/export/
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = [["name", "description"]]
        for ct in ClimateType.objects.order_by("name"):
            rows.append([ct.name, ct.description])
        return render_csv_response(rows, "climate_types_export.csv")


# ===========================================================================
# Building Types
# ===========================================================================

class BuildingTypeListCreateView(APIView):
    """
    GET  /api/system-settings/building-types/  — list (paginated, searchable)
    POST /api/system-settings/building-types/  — create with optional subtypes
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = BuildingCategory.objects.prefetch_related("subcategories").order_by("name")
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        page_obj, meta = paginate_queryset(qs, request)
        return Response({"results": BuildingTypeListSerializer(page_obj, many=True).data, "pagination": meta})

    def post(self, request):
        serializer = BuildingTypeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            category = BuildingCategory.objects.create(name=serializer.validated_data["name"])
            for subtype_name in serializer.validated_data.get("subtypes", []):
                name = subtype_name.strip()
                if name:
                    subcategory, _ = BuildingSubcategory.objects.get_or_create(name=name)
                    CategorySubcategory.objects.get_or_create(category=category, subcategory=subcategory)

        return Response(BuildingTypeDetailSerializer(category).data, status=status.HTTP_201_CREATED)


class BuildingTypeDetailView(APIView):
    """
    GET   /api/system-settings/building-types/<pk>/  — detail with subtypes
    PATCH /api/system-settings/building-types/<pk>/  — edit name, add/remove/rename subtypes
    """
    permission_classes = [IsAdminUser]

    def _get_obj(self, pk):
        try:
            return BuildingCategory.objects.prefetch_related("subcategories").get(pk=pk)
        except BuildingCategory.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_obj(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(BuildingTypeDetailSerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get_obj(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = BuildingTypeUpdateSerializer(instance=obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if "name" in serializer.validated_data:
                obj.name = serializer.validated_data["name"]
                obj.save(update_fields=["name"])

            for subtype_name in serializer.validated_data.get("add_subtypes", []):
                name = subtype_name.strip()
                if name:
                    subcategory, _ = BuildingSubcategory.objects.get_or_create(name=name)
                    CategorySubcategory.objects.get_or_create(category=obj, subcategory=subcategory)

            for sub_id in serializer.validated_data.get("remove_subtype_ids", []):
                CategorySubcategory.objects.filter(category=obj, subcategory_id=sub_id).delete()

            for item in serializer.validated_data.get("update_subtypes", []):
                try:
                    sub = BuildingSubcategory.objects.get(id=int(item["id"]))
                    sub.name = item["name"].strip()
                    sub.save(update_fields=["name"])
                except (BuildingSubcategory.DoesNotExist, KeyError, ValueError):
                    pass

        obj.refresh_from_db()
        return Response(BuildingTypeDetailSerializer(obj).data)


class BuildingTypeImportView(APIView):
    """
    POST /api/system-settings/building-types/import/
    CSV format: building_type_name, subtype_1, subtype_2, ...
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rows = parse_csv(file)
        except Exception as e:
            return Response({"detail": f"Could not parse CSV: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        created_types = 0
        created_subtypes = 0

        with transaction.atomic():
            for row in rows:
                if not row:
                    continue
                type_name = row[0].strip()
                if not type_name:
                    continue
                category, c_created = BuildingCategory.objects.get_or_create(name=type_name)
                if c_created:
                    created_types += 1
                for subtype_name in row[1:]:
                    name = subtype_name.strip()
                    if name:
                        subcategory, _ = BuildingSubcategory.objects.get_or_create(name=name)
                        _, s_created = CategorySubcategory.objects.get_or_create(
                            category=category, subcategory=subcategory
                        )
                        if s_created:
                            created_subtypes += 1

        return Response({
            "detail": f"Import complete. {created_types} building types and {created_subtypes} subtypes created."
        }, status=status.HTTP_201_CREATED)


class BuildingTypeExportView(APIView):
    """
    GET /api/system-settings/building-types/export/
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = [["building_type", "subtype_1", "subtype_2", "..."]]
        for category in BuildingCategory.objects.prefetch_related("subcategories").order_by("name"):
            subtypes = list(category.subcategories.order_by("name").values_list("name", flat=True))
            rows.append([category.name] + subtypes)
        return render_csv_response(rows, "building_types_export.csv")