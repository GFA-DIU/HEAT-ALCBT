from django.urls import path

from .views.about import AboutPageView
from .views.home import get_building
from .views.building import building
from .views.assembly import component_edit, component_new

urlpatterns = [
    path("", get_building, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("building/<int:building_id>/", building, name="building"),
    path("component/", component_edit, name="component"),
    path("component/<int:assembly_id>/", component_edit, name="component_edit"),  # For editing an existing component
]
