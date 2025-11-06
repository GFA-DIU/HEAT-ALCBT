
from django.shortcuts import render

from pages.forms.building_detailed_info import BuildingDetailedInformation
from pages.forms.building_general_info import BuildingGeneralInformation
from pages.forms.operational_info_form import OperationalInfoForm


def building_components(request):
    template = request.GET.get("template");

    return render(request, "pages/add-building/components/"+template)

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