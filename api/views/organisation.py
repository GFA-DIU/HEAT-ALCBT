import logging

from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdminUser
from api.serializers.organisation import (
    OrganisationCreateSerializer,
    OrganisationUpdateSerializer,
    OrganisationListSerializer,
    OrganisationDetailSerializer,
    AdminBuildingSerializer,
)
from api.utils import paginate_queryset
from pages.models.building import Building
from pages.models.organisation import Organisation
from pages.views.building.building_stats import (
    calculate_total_carbon_footprint,
    calculate_total_embodied_carbon,
    calculate_total_operational_carbon,
)

logger = logging.getLogger(__name__)


class OrganisationListCreateView(APIView):
    """
    GET  /api/organisations/  — list organisations (paginated, filterable)
    POST /api/organisations/  — create organisation (optionally invite users)
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = Organisation.objects.select_related("country", "city").prefetch_related(
            "memberships__user", "buildings"
        )

        # Superadmin sees all; admin sees only their own orgs
        if not request.user.is_superuser:
            qs = qs.filter(memberships__user=request.user)

        # Search by name
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)

        # Filter by industry
        industry = request.query_params.get("industry", "").strip()
        if industry:
            qs = qs.filter(industry__iexact=industry)

        # Filter by location (country name or city name)
        location = request.query_params.get("location", "").strip()
        if location:
            qs = qs.filter(
                Q(country__name__icontains=location) |
                Q(city__name__icontains=location)
            )

        # Filter by admin name
        admin_name = request.query_params.get("admin", "").strip()
        if admin_name:
            qs = qs.filter(
                memberships__role="admin",
            ).filter(
                Q(memberships__user__first_name__icontains=admin_name) |
                Q(memberships__user__last_name__icontains=admin_name) |
                Q(memberships__user__username__icontains=admin_name)
            )

        qs = qs.distinct()
        items, meta = paginate_queryset(qs, request)
        serializer = OrganisationListSerializer(items, many=True)
        return Response({"results": serializer.data, "pagination": meta})

    def post(self, request):
        serializer = OrganisationCreateSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        organisation = serializer.save()
        logger.info("Admin %s created organisation %s", request.user, organisation)
        return Response(
            OrganisationDetailSerializer(organisation).data,
            status=status.HTTP_201_CREATED,
        )


class OrganisationDetailView(APIView):
    """
    GET   /api/organisations/<pk>/  — full organisation detail
    PATCH /api/organisations/<pk>/  — update organisation + add/update members
    """
    permission_classes = [IsAdminUser]

    def _get_organisation(self, pk, request):
        try:
            qs = Organisation.objects.select_related("country", "city").prefetch_related(
                "memberships__user__userprofile",
                "memberships__countries",
                "buildings",
            )
            if not request.user.is_superuser:
                qs = qs.filter(memberships__user=request.user)
            return qs.get(pk=pk)
        except Organisation.DoesNotExist:
            return None

    def get(self, request, pk):
        org = self._get_organisation(pk, request)
        if org is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrganisationDetailSerializer(org).data)

    def patch(self, request, pk):
        org = self._get_organisation(pk, request)
        if org is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrganisationUpdateSerializer(org, data=request.data, partial=True, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        organisation = serializer.save()
        logger.info("Admin %s updated organisation %s", request.user, organisation)
        return Response(OrganisationDetailSerializer(organisation).data)


class OrganisationBuildingsView(APIView):
    """
    GET /api/organisations/<pk>/buildings/
    Lists buildings for a specific organisation with same filters as the web
    app building list, plus pagination. Superadmin sees all; admin sees only
    buildings in their organisations.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        # Verify organisation access
        try:
            org_qs = Organisation.objects.all()
            if not request.user.is_superuser:
                org_qs = org_qs.filter(memberships__user=request.user)
            org = org_qs.get(pk=pk)
        except Organisation.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        qs = Building.objects.filter(organisation=org).select_related(
            "country", "city", "region", "category__category", "category__subcategory",
            "created_by", "organisation",
        )

        # Search — same fields as the web app
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

        # Filter by country
        country = request.query_params.get("country", "").strip()
        if country:
            qs = qs.filter(country__name__icontains=country)

        # Filter by city
        city = request.query_params.get("city", "").strip()
        if city:
            qs = qs.filter(city__name__icontains=city)

        # Filter by climate zone
        climate_zone = request.query_params.get("climate_zone", "").strip()
        if climate_zone:
            qs = qs.filter(climate_zone__name__iexact=climate_zone)

        # Filter by draft status
        draft = request.query_params.get("draft", "").strip().lower()
        if draft in ("true", "false"):
            qs = qs.filter(draft=(draft == "true"))

        items, meta = paginate_queryset(qs, request)

        # Build stats map for the serializer context
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