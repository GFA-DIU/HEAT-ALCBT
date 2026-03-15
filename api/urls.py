from django.urls import path

from api.views.auth import (
    AdminLoginView,
    AdminLogoutView,
    AdminTokenRefreshView,
    AdminForgotPasswordView,
    AdminProfileView,
)
from api.views.organisation import (
    OrganisationListCreateView,
    OrganisationDetailView,
    OrganisationBuildingsView,
)
from api.views.users import (
    UserListCreateView,
    UserDetailView,
    UserExportView,
    UserImportView,
)
from api.views.system_settings import (
    CountryListCreateView,
    CountryDetailView,
    CountryImportView,
    CountryExportView,
    ClimateTypeListCreateView,
    ClimateTypeDetailView,
    ClimateTypeImportView,
    ClimateTypeExportView,
    BuildingTypeListCreateView,
    BuildingTypeDetailView,
    BuildingTypeImportView,
    BuildingTypeExportView,
)

urlpatterns = [
    # Auth
    path("auth/login/", AdminLoginView.as_view(), name="api_admin_login"),
    path("auth/logout/", AdminLogoutView.as_view(), name="api_admin_logout"),
    path("auth/token/refresh/", AdminTokenRefreshView.as_view(), name="api_token_refresh"),
    path("auth/forgot-password/", AdminForgotPasswordView.as_view(), name="api_admin_forgot_password"),
    path("auth/profile/", AdminProfileView.as_view(), name="api_admin_profile"),

    # Organisations
    path("organisations/", OrganisationListCreateView.as_view(), name="api_organisations"),
    path("organisations/<uuid:pk>/", OrganisationDetailView.as_view(), name="api_organisation_detail"),
    path("organisations/<uuid:pk>/buildings/", OrganisationBuildingsView.as_view(), name="api_organisation_buildings"),

    # Users
    path("users/", UserListCreateView.as_view(), name="api_users"),
    path("users/export/", UserExportView.as_view(), name="api_users_export"),
    path("users/import/", UserImportView.as_view(), name="api_users_import"),
    path("users/<uuid:pk>/", UserDetailView.as_view(), name="api_user_detail"),

    # System Settings — Countries
    path("system-settings/countries/", CountryListCreateView.as_view(), name="api_countries"),
    path("system-settings/countries/import/", CountryImportView.as_view(), name="api_countries_import"),
    path("system-settings/countries/export/", CountryExportView.as_view(), name="api_countries_export"),
    path("system-settings/countries/<int:pk>/", CountryDetailView.as_view(), name="api_country_detail"),

    # System Settings — Climate Types
    path("system-settings/climate-types/", ClimateTypeListCreateView.as_view(), name="api_climate_types"),
    path("system-settings/climate-types/import/", ClimateTypeImportView.as_view(), name="api_climate_types_import"),
    path("system-settings/climate-types/export/", ClimateTypeExportView.as_view(), name="api_climate_types_export"),
    path("system-settings/climate-types/<int:pk>/", ClimateTypeDetailView.as_view(), name="api_climate_type_detail"),

    # System Settings — Building Types
    path("system-settings/building-types/", BuildingTypeListCreateView.as_view(), name="api_building_types"),
    path("system-settings/building-types/import/", BuildingTypeImportView.as_view(), name="api_building_types_import"),
    path("system-settings/building-types/export/", BuildingTypeExportView.as_view(), name="api_building_types_export"),
    path("system-settings/building-types/<int:pk>/", BuildingTypeDetailView.as_view(), name="api_building_type_detail"),
]
