import logging

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from cities_light.models import Country, City

from pages.forms.building_general_info import BuildingGeneralInformation

logger = logging.getLogger(__name__)

def get_building(request):

    print("Test")
    print(request.POST)
    # if this is a POST request we need to process the form data
    if request.method == "POST" and request.POST.get('action') == "general_information":
        print("I am here")
        # create a form instance and populate it with data from the request:
        form = BuildingGeneralInformation(request.POST)
        print(form.is_valid())
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            # ...
            # redirect to a new URL:
            building = form.save()
        else:
            print("Form errors:", form.errors)

    if request.GET.get('country'):
        print("country I request")
        country_id = request.GET.get('country')
        print("This is country id: %s", country_id)
        if country_id:
            cities = City.objects.filter(country_id=country_id).order_by('name')
            return render(request, 'pages/home/home_country.html', {'cities': cities})
    
    # if a regular get (or any other method) we'll create a blank form
    else:
        form = BuildingGeneralInformation()

    return render(request, "pages/home/home.html", {"form": form})

