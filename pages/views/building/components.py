
from countrystatecity_countries import (get_cities_of_state, get_countries,
                                        get_country_by_code,
                                        get_states_of_country)
from django.shortcuts import render

from pages.forms.building_detailed_info import BuildingDetailedInformation
from pages.forms.building_general_info import BuildingGeneralInformation
from pages.forms.operational_info_form import OperationalInfoForm


def building_components(request):
    template = request.GET.get("template")
    
    # Provide context for different templates
    context = {}
    if template == "building-information/building-name-location.html":
        from pages.models.base import ALCBTCountryManager
        context["countries"] = ALCBTCountryManager.get_alcbt_countries()
    elif template == "building-information/building-details.html":
        from pages.models.building import BuildingCategory
        context["building_categories"] = BuildingCategory.objects.all().order_by("name")

    return render(request, "pages/add-building/components/"+template, context)

def new_building(request):
    context = {
                "building_id": None,
                "building": None,
                "structural_components": [],
                "edit_mode": False,
            }
    form = BuildingGeneralInformation()
    detailedForm = BuildingDetailedInformation()
    operationalInfoForm = OperationalInfoForm()

    context["form_general_info"] = form
    context["form_detailed_info"] = detailedForm
    context["form_operational_info"] = operationalInfoForm

    return render(request, "pages/add-building/add-building.html", context)