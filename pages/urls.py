from django.urls import path

from .views.about import AboutPageView
from .views.home import get_building
from .views.building import building

urlpatterns = [
    path("", get_building, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("building/", building, name="building")
]
