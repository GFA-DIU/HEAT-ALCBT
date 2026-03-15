"""
Tests for System Settings API endpoints.
/api/system-settings/countries/
/api/system-settings/climate-types/
/api/system-settings/building-types/
"""
import io
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.account.models import EmailAddress

from accounts.models import CustomUser, UserProfile
from cities_light.models import Country
from accounts.models import CustomCity
from pages.models.climate_type import ClimateType
from pages.models.building import BuildingCategory, BuildingSubcategory, CategorySubcategory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_admin(username, email, superuser=False):
    user = CustomUser.objects.create_user(
        username=username, email=email, password="Pass123!", is_staff=True, is_superuser=superuser,
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    user.userprofile.role = UserProfile.Role.SUPERADMIN if superuser else UserProfile.Role.ADMIN
    user.userprofile.save()
    return user


def _auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


@pytest.fixture
def admin(db):
    return _make_admin("admin_ss", "admin_ss@example.com")


@pytest.fixture
def client(admin):
    return _auth_client(admin)


@pytest.fixture
def country(db):
    c, _ = Country.objects.get_or_create(
        code2="MY", defaults={"name": "Malaysia", "continent": "AS", "slug": "malaysia"}
    )
    return c


@pytest.fixture
def city(db, country):
    c, _ = CustomCity.objects.get_or_create(name="Kuala Lumpur", country=country)
    return c


@pytest.fixture
def climate(db):
    ct, _ = ClimateType.objects.get_or_create(name="tropical-wet", defaults={"description": "Tropical"})
    return ct


@pytest.fixture
def building_type(db):
    return BuildingCategory.objects.create(name="Residential")


# ---------------------------------------------------------------------------
# Countries
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCountryList:
    url = "/api/system-settings/countries/"

    def test_list_countries(self, client, country):
        resp = client.get(self.url)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "pagination" in data

    def test_search_countries(self, client, country):
        resp = client.get(self.url + "?search=Malaysia")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any(r["name"] == "Malaysia" for r in results)

    def test_search_no_match(self, client, db):
        resp = client.get(self.url + "?search=ZZZNOMATCH")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 0

    def test_unauthenticated_returns_401(self, db):
        resp = APIClient().get(self.url)
        assert resp.status_code == 401

    def test_list_includes_city_count(self, client, country, city):
        resp = client.get(self.url + "?search=Malaysia")
        result = resp.json()["results"][0]
        assert "city_count" in result
        assert result["city_count"] >= 1


@pytest.mark.django_db
class TestCountryCreate:
    url = "/api/system-settings/countries/"

    def test_create_country(self, client):
        resp = client.post(self.url, {"name": "New Country"}, format="json")
        assert resp.status_code == 201
        assert resp.json()["name"] == "New Country"

    def test_create_country_with_cities(self, client):
        resp = client.post(self.url, {
            "name": "Country With Cities",
            "cities": ["City A", "City B"],
        }, format="json")
        assert resp.status_code == 201
        data = resp.json()
        city_names = [c["name"] for c in data["cities"]]
        assert "City A" in city_names
        assert "City B" in city_names

    def test_duplicate_name_returns_400(self, client, country):
        resp = client.post(self.url, {"name": "Malaysia"}, format="json")
        assert resp.status_code == 400

    def test_missing_name_returns_400(self, client):
        resp = client.post(self.url, {}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestCountryDetail:

    def test_get_country(self, client, country, city):
        resp = client.get(f"/api/system-settings/countries/{country.id}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Malaysia"
        assert any(c["name"] == "Kuala Lumpur" for c in data["cities"])

    def test_get_nonexistent_returns_404(self, client, db):
        resp = client.get("/api/system-settings/countries/999999/")
        assert resp.status_code == 404

    def test_patch_country_name(self, client, country):
        resp = client.patch(f"/api/system-settings/countries/{country.id}/", {"name": "Malaysia Updated"}, format="json")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Malaysia Updated"

    def test_patch_add_cities(self, client, country):
        resp = client.patch(f"/api/system-settings/countries/{country.id}/", {
            "add_cities": ["New City 1", "New City 2"]
        }, format="json")
        assert resp.status_code == 200
        city_names = [c["name"] for c in resp.json()["cities"]]
        assert "New City 1" in city_names
        assert "New City 2" in city_names

    def test_patch_update_city_name(self, client, country, city):
        resp = client.patch(f"/api/system-settings/countries/{country.id}/", {
            "update_cities": [{"id": str(city.id), "name": "Renamed City"}]
        }, format="json")
        assert resp.status_code == 200
        city_names = [c["name"] for c in resp.json()["cities"]]
        assert "Renamed City" in city_names


@pytest.mark.django_db
class TestCountryImportExport:

    def test_export_csv(self, client, country, city):
        resp = client.get("/api/system-settings/countries/export/")
        assert resp.status_code == 200
        assert "text/csv" in resp["Content-Type"]
        content = b"".join(resp.streaming_content).decode() if hasattr(resp, "streaming_content") else resp.content.decode()
        assert "Malaysia" in content

    def test_import_csv(self, client, db):
        csv_content = b"ImportCountry1,CityA,CityB\nImportCountry2,CityC\n"
        f = io.BytesIO(csv_content)
        f.name = "countries.csv"
        resp = client.post("/api/system-settings/countries/import/", {"file": f}, format="multipart")
        assert resp.status_code == 201
        assert Country.objects.filter(name="ImportCountry1").exists()
        assert Country.objects.filter(name="ImportCountry2").exists()

    def test_import_no_file_returns_400(self, client, db):
        resp = client.post("/api/system-settings/countries/import/", {}, format="multipart")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Climate Types
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestClimateTypeList:
    url = "/api/system-settings/climate-types/"

    def test_list_climate_types(self, client, climate):
        resp = client.get(self.url)
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] >= 1

    def test_search(self, client, climate):
        resp = client.get(self.url + "?search=tropical")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] >= 1

    def test_list_includes_usage_count(self, client, climate):
        resp = client.get(self.url + "?search=tropical-wet")
        result = resp.json()["results"][0]
        assert "usage_count" in result
        assert "status" in result


@pytest.mark.django_db
class TestClimateTypeCreate:
    url = "/api/system-settings/climate-types/"

    def test_create(self, client):
        resp = client.post(self.url, {"name": "alpine", "description": "Cold alpine climate"}, format="json")
        assert resp.status_code == 201
        assert resp.json()["name"] == "alpine"

    def test_duplicate_name_returns_400(self, client, climate):
        resp = client.post(self.url, {"name": "tropical-wet"}, format="json")
        assert resp.status_code == 400

    def test_missing_name_returns_400(self, client):
        resp = client.post(self.url, {}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestClimateTypeDetail:

    def test_get(self, client, climate):
        resp = client.get(f"/api/system-settings/climate-types/{climate.id}/")
        assert resp.status_code == 200
        assert resp.json()["name"] == "tropical-wet"

    def test_get_nonexistent_returns_404(self, client, db):
        resp = client.get("/api/system-settings/climate-types/999999/")
        assert resp.status_code == 404

    def test_patch_name(self, client, climate):
        resp = client.patch(f"/api/system-settings/climate-types/{climate.id}/", {"name": "tropical-wet-updated"}, format="json")
        assert resp.status_code == 200
        assert resp.json()["name"] == "tropical-wet-updated"

    def test_patch_description(self, client, climate):
        resp = client.patch(f"/api/system-settings/climate-types/{climate.id}/", {"description": "Updated desc"}, format="json")
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated desc"

    def test_duplicate_name_on_patch_returns_400(self, client, climate, db):
        ClimateType.objects.get_or_create(name="cold")
        resp = client.patch(f"/api/system-settings/climate-types/{climate.id}/", {"name": "cold"}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestClimateTypeImportExport:

    def test_export_csv(self, client, climate):
        resp = client.get("/api/system-settings/climate-types/export/")
        assert resp.status_code == 200
        assert "text/csv" in resp["Content-Type"]

    def test_import_csv(self, client, db):
        csv_content = b"monsoon,A monsoon climate\narctic,Extremely cold\n"
        f = io.BytesIO(csv_content)
        f.name = "climate_types.csv"
        resp = client.post("/api/system-settings/climate-types/import/", {"file": f}, format="multipart")
        assert resp.status_code == 201
        assert ClimateType.objects.filter(name="monsoon").exists()

    def test_import_no_file_returns_400(self, client, db):
        resp = client.post("/api/system-settings/climate-types/import/", {}, format="multipart")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Building Types
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBuildingTypeList:
    url = "/api/system-settings/building-types/"

    def test_list(self, client, building_type):
        resp = client.get(self.url)
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] >= 1

    def test_search(self, client, building_type):
        resp = client.get(self.url + "?search=Residential")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] >= 1

    def test_list_includes_subtype_count(self, client, building_type):
        resp = client.get(self.url + "?search=Residential")
        result = resp.json()["results"][0]
        assert "subtype_count" in result
        assert "has_subtypes" in result


@pytest.mark.django_db
class TestBuildingTypeCreate:
    url = "/api/system-settings/building-types/"

    def test_create_without_subtypes(self, client):
        resp = client.post(self.url, {"name": "Commercial"}, format="json")
        assert resp.status_code == 201
        assert resp.json()["name"] == "Commercial"

    def test_create_with_subtypes(self, client):
        resp = client.post(self.url, {
            "name": "Test Mixed Use XYZ",
            "has_subtypes": True,
            "subtypes": ["Office XYZ", "Retail XYZ"],
        }, format="json")
        assert resp.status_code == 201
        subtypes = [s["name"] for s in resp.json()["subtypes"]]
        assert "Office XYZ" in subtypes
        assert "Retail XYZ" in subtypes

    def test_has_subtypes_true_requires_subtypes(self, client):
        resp = client.post(self.url, {"name": "Empty Sub", "has_subtypes": True, "subtypes": []}, format="json")
        assert resp.status_code == 400

    def test_duplicate_name_returns_400(self, client, building_type):
        resp = client.post(self.url, {"name": "Residential"}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestBuildingTypeDetail:

    def test_get(self, client, building_type):
        resp = client.get(f"/api/system-settings/building-types/{building_type.id}/")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Residential"

    def test_get_nonexistent_returns_404(self, client, db):
        resp = client.get("/api/system-settings/building-types/999999/")
        assert resp.status_code == 404

    def test_patch_name(self, client, building_type):
        resp = client.patch(f"/api/system-settings/building-types/{building_type.id}/", {"name": "Residential Updated"}, format="json")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Residential Updated"

    def test_patch_add_subtypes(self, client, building_type):
        resp = client.patch(f"/api/system-settings/building-types/{building_type.id}/", {
            "add_subtypes": ["Apartment", "Villa"]
        }, format="json")
        assert resp.status_code == 200
        subtypes = [s["name"] for s in resp.json()["subtypes"]]
        assert "Apartment" in subtypes
        assert "Villa" in subtypes

    def test_patch_remove_subtype(self, client, building_type):
        sub = BuildingSubcategory.objects.create(name="To Remove")
        CategorySubcategory.objects.create(category=building_type, subcategory=sub)
        resp = client.patch(f"/api/system-settings/building-types/{building_type.id}/", {
            "remove_subtype_ids": [sub.id]
        }, format="json")
        assert resp.status_code == 200
        subtypes = [s["name"] for s in resp.json()["subtypes"]]
        assert "To Remove" not in subtypes

    def test_patch_update_subtype_name(self, client, building_type):
        sub = BuildingSubcategory.objects.create(name="Old Name")
        CategorySubcategory.objects.create(category=building_type, subcategory=sub)
        resp = client.patch(f"/api/system-settings/building-types/{building_type.id}/", {
            "update_subtypes": [{"id": str(sub.id), "name": "New Name"}]
        }, format="json")
        assert resp.status_code == 200
        subtypes = [s["name"] for s in resp.json()["subtypes"]]
        assert "New Name" in subtypes
        assert "Old Name" not in subtypes


@pytest.mark.django_db
class TestBuildingTypeImportExport:

    def test_export_csv(self, client, building_type):
        resp = client.get("/api/system-settings/building-types/export/")
        assert resp.status_code == 200
        assert "text/csv" in resp["Content-Type"]

    def test_import_csv(self, client, db):
        csv_content = b"Industrial,Factory,Warehouse\nHospitality,Hotel\n"
        f = io.BytesIO(csv_content)
        f.name = "building_types.csv"
        resp = client.post("/api/system-settings/building-types/import/", {"file": f}, format="multipart")
        assert resp.status_code == 201
        assert BuildingCategory.objects.filter(name="Industrial").exists()
        assert BuildingCategory.objects.filter(name="Hospitality").exists()

    def test_import_no_file_returns_400(self, client, db):
        resp = client.post("/api/system-settings/building-types/import/", {}, format="multipart")
        assert resp.status_code == 400
