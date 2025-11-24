import os

from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic.base import RedirectView

DJANGO_ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL")

urlpatterns = [
    path(f"{DJANGO_ADMIN_URL}/admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),  # include custom views
    path("accounts/", include("allauth.urls")),
    path('cookies/', include('cookie_consent.urls')),
    path("i18n/", include("django.conf.urls.i18n")),  # Language switching
    path("", include("pages.urls")),


    # IMPORTANT that the redirect path is at the end of the urlpatterns.
    # The regex r"^.*$" will match any string and therefore, if this pattern is added at the beginning of the urlpatterns array, the app will not reach any other url as it would always match this pattern first.
    re_path(
        r"^.*$",
        RedirectView.as_view(url="/", permanent=False),
        name="redirect",
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
