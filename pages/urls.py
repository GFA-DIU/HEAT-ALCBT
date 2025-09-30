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
from .views.assembly.assembly_templates import assembly_templates_list, copy_template
from .views.assembly.assembly_template_management import (
    assembly_template_management, 
    toggle_template_status,
    delete_template,
    duplicate_template,
    convert_assembly_to_template
)
from cookie_management.views import get_cookie_groups


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
    path(
        "template-edit/<uuid:assembly_id>/",
        component_edit,
        name="template_edit",
),
    path("boq/<uuid:building_id>/_new", boq_edit, name="boq"),
    path(
        "boq/<uuid:assembly_id>/<uuid:building_id>/",
        boq_edit,
        name="boq_edit",
    ),
    path("templates/<uuid:building_id>/", assembly_templates_list, name="assembly_templates"),
    path(
        "copy-template/<uuid:building_id>/<uuid:template_id>/",
        copy_template,
        name="copy_template",
    ),
    # Template Management URLs
    path("template-management/", assembly_template_management, name="assembly_template_management"),
    path(
        "template-management/toggle/<uuid:assembly_id>/", 
        toggle_template_status, 
        name="toggle_template_status"
    ),
    path(
        "template-management/delete/<uuid:assembly_id>/", 
        delete_template, 
        name="delete_template"
    ),
    path(
        "template-management/duplicate/<uuid:assembly_id>/", 
        duplicate_template, 
        name="duplicate_template"
    ),
    path(
        "template-management/convert/<uuid:assembly_id>/", 
        convert_assembly_to_template, 
        name="convert_assembly_to_template"
    ),
    path("cookie_groups/", get_cookie_groups, name="cookie_groups"),
]
