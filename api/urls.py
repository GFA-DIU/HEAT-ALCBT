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
from api.views.buildings import (
    BuildingListView,
    BuildingDetailView,
    BuildingImportNameLocationView,
    BuildingImportDetailsView,
    BuildingImportOperationalScheduleView,
    BuildingImportCoolingSystemsView,
    BuildingImportVentilationSystemsView,
    BuildingImportLightingSystemsView,
    BuildingImportLiftEscalatorView,
    BuildingImportHotWaterSystemsView,
    BuildingImportEnergyCarriersView,
    BuildingImportStructuralComponentsView,
    BuildingCompleteView,
)
from api.views.building_add import (
    BuildingAddNameLocationView,
    BuildingAddDetailsView,
    BuildingAddOperationalScheduleView,
    BuildingAddCoolingSystemView,
    BuildingAddVentilationSystemView,
    BuildingAddLightingSystemView,
    BuildingAddLiftEscalatorView,
    BuildingAddHotWaterSystemView,
    BuildingAddEnergyCarriersView,
    BuildingAddStructuralComponentView,
    BuildingAddCompleteView,
)
from api.views.building_detail import BuildingFullDetailView
from api.views.building_export import BuildingExportView
from api.views.building_files import BuildingFilesView
from api.views.users import (
    UserListCreateView,
    UserDetailView,
    UserExportView,
    UserImportView,
)
from api.views.system_settings import (
    CountryListCreateView,
    CountryDetailView,
    CountryRegionsView,
    CountryCitiesView,
    CountryImportView,
    CountryExportView,
    ClimateTypeListCreateView,
    ClimateTypeDetailView,
    ClimateTypeImportView,
    ClimateTypeExportView,
    ApartmentTypeListView,
    BuildingTypeListCreateView,
    BuildingTypeDetailView,
    BuildingTypeImportView,
    BuildingTypeExportView,
    SelectListsView,
)

urlpatterns = [
    # Auth
    path("auth/login/", AdminLoginView.as_view(), name="api_admin_login"),
    path("auth/logout/", AdminLogoutView.as_view(), name="api_admin_logout"),
    path("auth/token/refresh/", AdminTokenRefreshView.as_view(), name="api_token_refresh"),
    path("auth/forgot-password/", AdminForgotPasswordView.as_view(), name="api_admin_forgot_password"),
    path("auth/profile/", AdminProfileView.as_view(), name="api_admin_profile"),

    # Buildings — list & export
    path("buildings/", BuildingListView.as_view(), name="api_buildings"),
    path("buildings/export/", BuildingExportView.as_view(), name="api_buildings_export"),

    # Buildings — file upload/serve (must be before <str:pk> to avoid conflict)
    path("buildings/files/", BuildingFilesView.as_view(), name="api_building_files"),

    # Buildings — detail & full-detail (pk = uuid field, not the pk/id)
    path("buildings/<str:pk>/", BuildingDetailView.as_view(), name="api_building_detail"),
    path("buildings/<str:pk>/detail/", BuildingFullDetailView.as_view(), name="api_building_full_detail"),

    # Buildings — Excel import (step-by-step)
    path("buildings/import/name-location/", BuildingImportNameLocationView.as_view(), name="api_building_import_name_location"),
    path("buildings/import/details/", BuildingImportDetailsView.as_view(), name="api_building_import_details"),
    path("buildings/import/operational-schedule/", BuildingImportOperationalScheduleView.as_view(), name="api_building_import_operational_schedule"),
    path("buildings/import/cooling-systems/", BuildingImportCoolingSystemsView.as_view(), name="api_building_import_cooling_systems"),
    path("buildings/import/ventilation-systems/", BuildingImportVentilationSystemsView.as_view(), name="api_building_import_ventilation_systems"),
    path("buildings/import/lighting-systems/", BuildingImportLightingSystemsView.as_view(), name="api_building_import_lighting_systems"),
    path("buildings/import/lift-escalator/", BuildingImportLiftEscalatorView.as_view(), name="api_building_import_lift_escalator"),
    path("buildings/import/hot-water-systems/", BuildingImportHotWaterSystemsView.as_view(), name="api_building_import_hot_water_systems"),
    path("buildings/import/energy-carriers/", BuildingImportEnergyCarriersView.as_view(), name="api_building_import_energy_carriers"),
    path("buildings/import/structural-components/", BuildingImportStructuralComponentsView.as_view(), name="api_building_import_structural_components"),
    path("buildings/import/complete/", BuildingCompleteView.as_view(), name="api_building_import_complete"),

    # Buildings — manual add (multi-step form)
    path("buildings/add/name-location/", BuildingAddNameLocationView.as_view(), name="api_building_add_name_location"),
    path("buildings/add/details/", BuildingAddDetailsView.as_view(), name="api_building_add_details"),
    path("buildings/add/operational-schedule/", BuildingAddOperationalScheduleView.as_view(), name="api_building_add_operational_schedule"),
    path("buildings/add/cooling-systems/", BuildingAddCoolingSystemView.as_view(), name="api_building_add_cooling_systems"),
    path("buildings/add/ventilation-systems/", BuildingAddVentilationSystemView.as_view(), name="api_building_add_ventilation_systems"),
    path("buildings/add/lighting-systems/", BuildingAddLightingSystemView.as_view(), name="api_building_add_lighting_systems"),
    path("buildings/add/lift-escalator/", BuildingAddLiftEscalatorView.as_view(), name="api_building_add_lift_escalator"),
    path("buildings/add/hot-water-systems/", BuildingAddHotWaterSystemView.as_view(), name="api_building_add_hot_water_systems"),
    path("buildings/add/energy-carriers/", BuildingAddEnergyCarriersView.as_view(), name="api_building_add_energy_carriers"),
    path("buildings/add/structural-components/", BuildingAddStructuralComponentView.as_view(), name="api_building_add_structural_components"),
    path("buildings/add/complete/", BuildingAddCompleteView.as_view(), name="api_building_add_complete"),

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
    path("system-settings/countries/<int:pk>/regions/", CountryRegionsView.as_view(), name="api_country_regions"),
    path("system-settings/countries/<int:pk>/cities/", CountryCitiesView.as_view(), name="api_country_cities"),

    # System Settings — Climate Types
    path("system-settings/climate-types/", ClimateTypeListCreateView.as_view(), name="api_climate_types"),
    path("system-settings/climate-types/import/", ClimateTypeImportView.as_view(), name="api_climate_types_import"),
    path("system-settings/climate-types/export/", ClimateTypeExportView.as_view(), name="api_climate_types_export"),
    path("system-settings/climate-types/<int:pk>/", ClimateTypeDetailView.as_view(), name="api_climate_type_detail"),

    # System Settings — Apartment Types
    path("system-settings/apartment-types/", ApartmentTypeListView.as_view(), name="api_apartment_types"),

    # System Settings — Select Lists (JSON equivalents of HTMX select_lists)
    path("system-settings/select-lists/", SelectListsView.as_view(), name="api_select_lists"),

    # System Settings — Building Types
    path("system-settings/building-types/", BuildingTypeListCreateView.as_view(), name="api_building_types"),
    path("system-settings/building-types/import/", BuildingTypeImportView.as_view(), name="api_building_types_import"),
    path("system-settings/building-types/export/", BuildingTypeExportView.as_view(), name="api_building_types_export"),
    path("system-settings/building-types/<int:pk>/", BuildingTypeDetailView.as_view(), name="api_building_type_detail"),
]
