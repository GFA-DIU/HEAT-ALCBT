from django.urls import path

from .views.about import AboutPageView
from .views.home import item_list

urlpatterns = [
    path("", item_list, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
]
