from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django_plotly_dash import DjangoDash

from .views.about import AboutPageView
from .views.home import get_building
from .views.building import building


urlpatterns = [
    path("", get_building, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("building/<int:building_id>/", building, name="building"),
    path('django_plotly_dash/', include('django_plotly_dash.urls')), 
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)