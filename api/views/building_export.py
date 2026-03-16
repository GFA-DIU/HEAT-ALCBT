"""
API view for exporting the building list to Excel (.xlsx).

GET /api/buildings/export/

Accepts the same query params as BuildingListView (search, country, city,
climate_zone, draft, organisation) and returns an Excel file with one row
per building.

Columns:
  Name, Country, City, Region, Climate Zone, Building Type, Subcategory,
  Total Floor Area (m²), Construction Year, Assessment Period (years),
  Draft, Public, Organisation, Created By, Created At,
  Total Carbon Footprint (kgCO₂e/m²), Total Embodied Carbon (kgCO₂e/m²),
  Total Operational Carbon (kgCO₂e/m²)
"""

import io
import logging

import openpyxl
from django.db.models import Q
from django.http import HttpResponse
from rest_framework.views import APIView

from api.permissions import IsAdminUser
from api.views.buildings import _buildings_queryset
from pages.views.building.building_stats import (
    calculate_total_carbon_footprint,
    calculate_total_embodied_carbon,
    calculate_total_operational_carbon,
)

logger = logging.getLogger(__name__)

HEADERS = [
    "Name",
    "Country",
    "City",
    "Region",
    "Climate Zone",
    "Building Type",
    "Subcategory",
    "Total Floor Area (m²)",
    "Construction Year",
    "Assessment Period (years)",
    "Draft",
    "Public",
    "Organisation",
    "Created By",
    "Created At",
    "Total Carbon Footprint (kgCO₂e/m²)",
    "Total Embodied Carbon (kgCO₂e/m²)",
    "Total Operational Carbon (kgCO₂e/m²)",
]


class BuildingExportView(APIView):
    """
    GET /api/buildings/export/

    Streams an Excel file with all buildings accessible to the requesting admin.
    Applies the same filters as the building list endpoint.
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

        # Build workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Buildings"

        # Header row (bold)
        ws.append(HEADERS)
        for cell in ws[1]:
            cell.font = openpyxl.styles.Font(bold=True)

        # Data rows
        for building in qs.iterator():
            try:
                embodied = calculate_total_embodied_carbon(building, simulated=False)
                operational = calculate_total_operational_carbon(building, simulated=False)
                footprint = embodied + operational
            except Exception:
                embodied = operational = footprint = None

            row = [
                building.name,
                building.country.name if building.country else "",
                building.city.name if building.city else "",
                building.region.name if building.region else "",
                building.climate_zone.name if building.climate_zone else "",
                building.category.category.name if building.category and building.category.category else "",
                building.category.subcategory.name if building.category and building.category.subcategory else "",
                float(building.total_floor_area) if building.total_floor_area else "",
                building.construction_year or "",
                building.reference_period or "",
                "Yes" if building.draft else "No",
                "Yes" if building.public else "No",
                building.organisation.name if building.organisation else "",
                building.created_by.get_full_name() or building.created_by.username if building.created_by else "",
                building.created_at.strftime("%Y-%m-%d %H:%M") if building.created_at else "",
                float(footprint) if footprint is not None else "",
                float(embodied) if embodied is not None else "",
                float(operational) if operational is not None else "",
            ]
            ws.append(row)

        # Auto-size columns (approximate)
        for col in ws.columns:
            max_len = max((len(str(cell.value)) if cell.value else 0) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

        # Stream response
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="buildings_export.xlsx"'
        logger.info("API: building export requested by %s (%d rows)", request.user, qs.count())
        return response
