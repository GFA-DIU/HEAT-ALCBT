from django.urls import path
from django.views.generic import TemplateView

from cookie_management.views import get_cookie_groups
from pages.views.boq.boq import boq_edit
from pages.views.building.dashboards import dashboard_view
from pages.views.datasets import datasets
from pages.views.map import map_view
from pages.views.select_lists import select_lists
from pages.views.templates import templates

from .views.assembly.assembly import component_edit
from .views.building.add_building_steps import (building_step_view,
                                                complete_building_setup,
                                                get_building_step_data,
                                                save_building_step)
from .views.building.building import building
from .views.building.building_simulation import building_simulation
from .views.building.components import building_components, new_building
from .views.home import buildings_list
from .views.resources import resources

urlpatterns = [
    path("", buildings_list, name="home"),
    path("resource/", resources, name="resources"),
    path("templates/", templates, name="templates"),
    path("datasets/", datasets, name="datasets"),
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
    path("map/", map_view, name="map"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("building/_new", new_building, name="new_building"),
    path("building/component", building_components),
    path("building/step", building_step_view, name="building_step"),
    path("building/step/save", save_building_step, name="save_building_step"),
    path("building/step/data", get_building_step_data, name="get_building_step_data"),
    path("building/complete", complete_building_setup, name="complete_building_setup"),
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
    path("cookie_groups/", get_cookie_groups, name="cookie_groups"),
]
