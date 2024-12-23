import logging

from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from cities_light.models import City
from pages.models.epd import MaterialCategory

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def select_lists(request):
    if request.GET.get('country'):
        country_id = int(request.GET.get("country"))
        if country_id:
            cities = City.objects.filter(country=country_id).order_by("name")
            return render(
                request,
                "pages/utils/select_list.html",
                {"items": cities, "default_text": "Select a country"},
            )
    if request.GET.get('category'):
        category_id = int(request.GET.get('category'))
        if category_id:
            subcategories = MaterialCategory.objects.filter(
                level=2, parent=category_id
            ).order_by("name_en")
            return render(
                request,
                "pages/utils/select_list.html",
                {"items": subcategories, "default_text": "Select a category"},
            )
    if request.GET.get('subcategory'):
        subcategory_id = int(request.GET.get("subcategory"))
        if subcategory_id:
            childcategories = MaterialCategory.objects.filter(
                level=3, parent=subcategory_id
            ).order_by("name_en")
            return render(
                request,
                "pages/utils/select_list.html",
                {"items": childcategories, "default_text": "Select a subcategory"},
            )
    # Full page load for GET request
    return render(
        request,
        "pages/utils/select_list.html",
        {"items": [], "default_text": ""},
    )
