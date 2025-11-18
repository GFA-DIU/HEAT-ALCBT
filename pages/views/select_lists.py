import logging

from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from pages.models.epd import MaterialCategory
from pages.models.assembly import AssemblyTechnique
from accounts.models import CustomCity, CustomRegion

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

    # Full page load for GET request
    return render(
        request,
        "pages/utils/select_list.html",
        {"items": [], "default_text": ""},
    )
