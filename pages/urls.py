from django.urls import path
from django.views.generic import TemplateView

from pages.views.map import map_view
from pages.views.select_lists import select_lists

from .views.about import AboutPageView
from .views.home import buildings_list
from .views.building import building
from .views.assembly.assembly import component_edit

urlpatterns = [
    path("", buildings_list, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("privacy_policy/", TemplateView.as_view(template_name="compliance/privacy_policy.html"), name="privacy_policy"),
    path("select_lists/", select_lists, name="select-lists"),
    path("map/", map_view, name="map"),
    path("building/_new/", building, name="new_building"),
    path("building/<int:building_id>/", building, name="building"),

    path("component/<int:building_id>/_new", component_edit, name="component"),
    path("component/<int:assembly_id>/<int:building_id>/", component_edit, name="component_edit"),  # For editing an existing component
]
