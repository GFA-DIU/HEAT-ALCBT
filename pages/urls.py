from django.urls import path

from .views.about import AboutPageView
from .views.home import buildings_list
from .views.building import building

urlpatterns = [
    path("", buildings_list, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("building/<int:building_id>/", building, name="building"),
    path("building/_new/", building, name="new_building"),
]
