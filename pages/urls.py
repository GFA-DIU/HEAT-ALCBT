from django.urls import path

from pages.views.map import map_view

from .views.about import AboutPageView
from .views.home import buildings_list
from .views.building import building
from .views.assembly import component_edit, component_new

urlpatterns = [
    path("", buildings_list, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("map/", map_view, name="map"),
    path("building/_new/", building, name="new_building"),
    path("building/<int:building_id>/", building, name="building"),

    path("component/<int:building_id>/_new", component_edit, name="component"),
    path("component/<int:assembly_id>/<int:building_id>/", component_edit, name="component_edit"),  # For editing an existing component
]
