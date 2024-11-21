from django.urls import path

from .views.about import AboutPageView
from .views.home import item_list
from .views.assembly import basic_assembly_info 

urlpatterns = [
    path("", item_list, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("assembly/", basic_assembly_info, name="assembly"),  
]
