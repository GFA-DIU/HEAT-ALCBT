"""
Tests for Organisation API endpoints.
GET/POST /api/organisations/
GET/PATCH /api/organisations/<pk>/
GET /api/organisations/<pk>/buildings/
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.account.models import EmailAddress

from accounts.models import CustomUser, UserProfile
from pages.models.organisation import Organisation, OrganisationMembership
from pages.models.building import Building
from cities_light.models import Country


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_admin(username, email, password="AdminPass123!", superuser=False):
    user = CustomUser.objects.create_user(
        username=username, email=email, password=password,
        is_staff=True, is_superuser=superuser,
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    user.userprofile.role = UserProfile.Role.SUPERADMIN if superuser else UserProfile.Role.ADMIN
    user.userprofile.save()
    return user


def _make_viewer(username, email):
    user = CustomUser.objects.create_user(
        username=username, email=email, password="ViewerPass123!", is_staff=False,
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def _auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


@pytest.fixture
def superadmin(db):
    return _make_admin("superadmin", "super@example.com", superuser=True)


@pytest.fixture
def admin(db):
    return _make_admin("admin1", "admin1@example.com")


@pytest.fixture
def admin2(db):
    return _make_admin("admin2", "admin2@example.com")


@pytest.fixture
def viewer(db):
    return _make_viewer("viewer1", "viewer1@example.com")


@pytest.fixture
def superadmin_client(superadmin):
    return _auth_client(superadmin)


@pytest.fixture
def admin_client(admin):
    return _auth_client(admin)


@pytest.fixture
def country(db):
    c, _ = Country.objects.get_or_create(
        code2="SG", defaults={"name": "Singapore", "continent": "AS", "slug": "singapore"}
    )
    return c


@pytest.fixture
def org(db, country):
    return Organisation.objects.create(name="Acme Corp", industry="construction", country=country)


@pytest.fixture
def org_with_admin(db, org, admin):
    OrganisationMembership.objects.create(organisation=org, user=admin, role="admin")
    return org


@pytest.fixture
def building(db, org, admin):
    from pages.models.climate_type import ClimateType
    ct, _ = ClimateType.objects.get_or_create(name="tropical-wet")
    b = Building.objects.create(
        name="Test Building",
        total_floor_area=500,
        organisation=org,
        created_by=admin,
        climate_zone=ct,
    )
    return b


# ---------------------------------------------------------------------------
# List / Create
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrganisationList:
    url = "/api/organisations/"

    def test_superadmin_sees_all_orgs(self, superadmin_client, org):
        resp = superadmin_client.get(self.url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] >= 1
        names = [r["name"] for r in data["results"]]
        assert "Acme Corp" in names

    def test_admin_sees_only_own_orgs(self, admin_client, admin, org, db):
        # org_with_admin fixture not used — admin not a member yet
        other_org = Organisation.objects.create(name="Other Corp", industry="technology")
        OrganisationMembership.objects.create(organisation=org, user=admin, role="admin")
        resp = admin_client.get(self.url)
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()["results"]]
        assert "Acme Corp" in names
        assert "Other Corp" not in names

    def test_unauthenticated_returns_401(self, db):
        resp = APIClient().get(self.url)
        assert resp.status_code == 401

    def test_viewer_returns_403(self, viewer, db):
        resp = _auth_client(viewer).get(self.url)
        assert resp.status_code == 403

    def test_search_filter(self, superadmin_client, org, db):
        Organisation.objects.create(name="Beta Ltd", industry="technology")
        resp = superadmin_client.get(self.url + "?search=Acme")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert all("Acme" in r["name"] for r in results)

    def test_pagination_meta(self, superadmin_client, db):
        for i in range(3):
            Organisation.objects.create(name=f"Org {i}", industry="other")
        resp = superadmin_client.get(self.url + "?page_size=2&page=1")
        meta = resp.json()["pagination"]
        assert meta["page"] == 1
        assert meta["page_size"] == 2
        assert "total" in meta
        assert "total_pages" in meta


@pytest.mark.django_db
class TestOrganisationCreate:
    url = "/api/organisations/"

    def test_create_org_minimal(self, superadmin_client, country):
        resp = superadmin_client.post(self.url, {
            "name": "New Corp",
            "industry": "construction",
            "country": country.id,
        }, format="json")
        assert resp.status_code == 201
        assert resp.json()["name"] == "New Corp"

    def test_create_org_with_invited_member(self, superadmin_client, admin, country):
        resp = superadmin_client.post(self.url, {
            "name": "Invite Corp",
            "industry": "technology",
            "country": country.id,
            "invite_users": [{"email": admin.email, "role": "admin"}],
        }, format="json")
        assert resp.status_code == 201
        org_id = resp.json()["id"]
        assert OrganisationMembership.objects.filter(
            organisation_id=org_id, user=admin
        ).exists()

    def test_create_org_missing_name_returns_400(self, superadmin_client):
        resp = superadmin_client.post(self.url, {"industry": "construction"}, format="json")
        assert resp.status_code == 400

    def test_create_org_duplicate_name_returns_400(self, superadmin_client, org):
        resp = superadmin_client.post(self.url, {
            "name": "Acme Corp", "industry": "construction"
        }, format="json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Detail / Update
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrganisationDetail:

    def test_get_own_org(self, admin_client, org_with_admin):
        resp = admin_client.get(f"/api/organisations/{org_with_admin.id}/")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Acme Corp"

    def test_superadmin_gets_any_org(self, superadmin_client, org):
        resp = superadmin_client.get(f"/api/organisations/{org.id}/")
        assert resp.status_code == 200

    def test_admin_cannot_get_unrelated_org(self, admin_client, org):
        # admin is not a member of org
        resp = admin_client.get(f"/api/organisations/{org.id}/")
        assert resp.status_code == 404

    def test_get_nonexistent_org_returns_404(self, superadmin_client):
        import uuid
        resp = superadmin_client.get(f"/api/organisations/{uuid.uuid4()}/")
        assert resp.status_code == 404

    def test_patch_org_name(self, superadmin_client, org):
        resp = superadmin_client.patch(f"/api/organisations/{org.id}/", {"name": "Renamed Corp"}, format="json")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed Corp"

    def test_patch_add_member(self, superadmin_client, org, viewer):
        resp = superadmin_client.patch(
            f"/api/organisations/{org.id}/",
            {"invite_users": [{"email": viewer.email, "role": "viewer"}]},
            format="json",
        )
        assert resp.status_code == 200
        assert OrganisationMembership.objects.filter(organisation=org, user=viewer).exists()

    def test_detail_includes_members(self, superadmin_client, org_with_admin, admin):
        resp = superadmin_client.get(f"/api/organisations/{org_with_admin.id}/")
        assert resp.status_code == 200
        member_ids = [str(m["user"]["id"]) for m in resp.json()["members"]]
        assert str(admin.id) in member_ids


# ---------------------------------------------------------------------------
# Organisation Buildings
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrganisationBuildings:

    def test_list_buildings(self, superadmin_client, org, building):
        resp = superadmin_client.get(f"/api/organisations/{org.id}/buildings/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] == 1
        assert data["results"][0]["name"] == "Test Building"

    def test_admin_sees_buildings_in_own_org(self, admin_client, org_with_admin, building):
        resp = admin_client.get(f"/api/organisations/{org_with_admin.id}/buildings/")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 1

    def test_admin_cannot_see_unrelated_org_buildings(self, admin_client, org, building):
        resp = admin_client.get(f"/api/organisations/{org.id}/buildings/")
        assert resp.status_code == 404

    def test_buildings_search(self, superadmin_client, org, building):
        resp = superadmin_client.get(f"/api/organisations/{org.id}/buildings/?search=Test")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 1

    def test_buildings_no_match_search(self, superadmin_client, org, building):
        resp = superadmin_client.get(f"/api/organisations/{org.id}/buildings/?search=ZZZNOMATCH")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 0

    def test_buildings_response_has_stats(self, superadmin_client, org, building):
        resp = superadmin_client.get(f"/api/organisations/{org.id}/buildings/")
        result = resp.json()["results"][0]
        assert "total_carbon_footprint" in result
        assert "total_embodied_carbon" in result
        assert "total_operational_carbon" in result

    def test_nonexistent_org_returns_404(self, superadmin_client):
        import uuid
        resp = superadmin_client.get(f"/api/organisations/{uuid.uuid4()}/buildings/")
        assert resp.status_code == 404
