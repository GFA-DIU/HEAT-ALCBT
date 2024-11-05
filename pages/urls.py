from django.urls import path

from .views.about import AboutPageView
from .views.home import item_list
from .views.building import building

urlpatterns = [
    path("", item_list, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("building/", building, name="building")
]
