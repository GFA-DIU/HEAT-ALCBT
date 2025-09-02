from django.urls import path
from django.views.generic import TemplateView


from pages.views.boq.boq import boq_edit
from pages.views.building.dashboards import dashboard_view
from pages.views.map import map_view
from pages.views.select_lists import select_lists, update_regions, update_categories

from .views.resources import resources
from .views.home import buildings_list
from .views.building.building import building
from .views.building.building_simulation import building_simulation
from .views.assembly.assembly import component_edit


urlpatterns = [
    path("", buildings_list, name="home"),
    path(
        "privacy_policy/",
        TemplateView.as_view(template_name="compliance/privacy_policy.html"),
        name="privacy_policy",
    ),
    path(
        "terms_of_use/",
        TemplateView.as_view(template_name="compliance/terms_of_use.html"),
        name="terms_of_use",
    ),
    path("resources/", resources, name="resources"),
    path("select_lists/", select_lists, name="select-lists"),
    path("update_regions/", update_regions, name="update-regions"),
    path("update_categories/", update_categories, name="update-categories"),
    path("map/", map_view, name="map"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("building/_new", building, name="new_building"),
    path("building/<uuid:building_id>/", building, name="building"),
    path(
        "building/<uuid:building_id>/simulation",
        building_simulation,
        name="building_simulation",
    ),
    path("component/<uuid:building_id>/_new", component_edit, name="component"),
    path(
        "component/<uuid:assembly_id>/<uuid:building_id>/",
        component_edit,
        name="component_edit",
    ),  # For editing an existing component
    path("boq/<uuid:building_id>/_new", boq_edit, name="boq"),
    path(
        "boq/<uuid:assembly_id>/<uuid:building_id>/",
        boq_edit,
        name="boq_edit",
    ),
]
