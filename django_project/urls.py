import os

from django.conf import settings
from django.contrib import admin
from django.urls import path, include

DJANGO_ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL")

urlpatterns = [
    path(f"{DJANGO_ADMIN_URL}/admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),  # include custom views
    path("accounts/", include("allauth.urls")),
    path("", include("pages.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
