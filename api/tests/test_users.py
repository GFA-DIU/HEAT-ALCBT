"""
Tests for User management API endpoints.
GET/POST /api/users/
GET/PATCH /api/users/<pk>/
GET /api/users/export/
POST /api/users/import/
"""
import io
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.account.models import EmailAddress

from accounts.models import CustomUser, UserProfile
from pages.models.organisation import Organisation, OrganisationMembership


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_admin(username, email, superuser=False):
    user = CustomUser.objects.create_user(
        username=username, email=email, password="Pass123!", is_staff=True, is_superuser=superuser,
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    user.userprofile.role = UserProfile.Role.SUPERADMIN if superuser else UserProfile.Role.ADMIN
    user.userprofile.save()
    return user


def _make_viewer(username, email):
    user = CustomUser.objects.create_user(
        username=username, email=email, password="Pass123!", is_staff=False,
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
    return _make_admin("su_users", "su_users@example.com", superuser=True)


@pytest.fixture
def admin(db):
    return _make_admin("adm_users", "adm_users@example.com")


@pytest.fixture
def viewer(db):
    return _make_viewer("viewer_users", "viewer_users@example.com")


@pytest.fixture
def superadmin_client(superadmin):
    return _auth_client(superadmin)


@pytest.fixture
def admin_client(admin):
    return _auth_client(admin)


@pytest.fixture
def org(db):
    return Organisation.objects.create(name="Test Org Users", industry="construction")


@pytest.fixture
def org_with_admin(db, org, admin):
    OrganisationMembership.objects.create(organisation=org, user=admin, role="admin")
    return org


@pytest.fixture
def viewer_in_org(db, org_with_admin, viewer):
    OrganisationMembership.objects.create(organisation=org_with_admin, user=viewer, role="viewer")
    return viewer


# ---------------------------------------------------------------------------
# List users
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUserList:
    url = "/api/users/"

    def test_superadmin_sees_all_users(self, superadmin_client, viewer):
        resp = superadmin_client.get(self.url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] >= 2  # superadmin + viewer at minimum
        assert "results" in data

    def test_admin_sees_only_org_users(self, admin_client, admin, org_with_admin, viewer_in_org, db):
        # Create a user NOT in admin's org
        outsider = _make_viewer("outsider", "outsider@example.com")
        resp = admin_client.get(self.url)
        assert resp.status_code == 200
        emails = [r["email"] for r in resp.json()["results"]]
        assert admin.email in emails
        assert viewer_in_org.email in emails
        assert outsider.email not in emails

    def test_search_by_email(self, superadmin_client, viewer):
        resp = superadmin_client.get(self.url + f"?search={viewer.email}")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] >= 1

    def test_search_by_name(self, superadmin_client, db):
        u = _make_viewer("searchable", "searchable@example.com")
        u.first_name = "UniqueFirstName"
        u.save()
        resp = superadmin_client.get(self.url + "?search=UniqueFirstName")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] >= 1

    def test_filter_by_role(self, superadmin_client, viewer):
        resp = superadmin_client.get(self.url + "?role=viewer")
        assert resp.status_code == 200
        for r in resp.json()["results"]:
            assert r["role"] == "viewer"

    def test_filter_by_organisation(self, superadmin_client, org_with_admin, admin):
        resp = superadmin_client.get(self.url + f"?organisation={org_with_admin.id}")
        assert resp.status_code == 200
        emails = [r["email"] for r in resp.json()["results"]]
        assert admin.email in emails

    def test_unauthenticated_returns_401(self, db):
        resp = APIClient().get(self.url)
        assert resp.status_code == 401

    def test_viewer_returns_403(self, viewer):
        resp = _auth_client(viewer).get(self.url)
        assert resp.status_code == 403

    def test_pagination(self, superadmin_client, db):
        for i in range(5):
            _make_viewer(f"pag{i}", f"pag{i}@example.com")
        resp = superadmin_client.get(self.url + "?page_size=2&page=1")
        data = resp.json()
        assert len(data["results"]) <= 2
        assert "total_pages" in data["pagination"]

    def test_response_fields(self, superadmin_client, viewer):
        resp = superadmin_client.get(self.url + f"?search={viewer.email}")
        result = resp.json()["results"][0]
        for field in ["id", "email", "full_name", "role", "organisations", "countries", "app_access", "is_active"]:
            assert field in result

    def test_app_access_admin_has_admin_app(self, superadmin_client, admin):
        resp = superadmin_client.get(self.url + f"?search={admin.email}")
        result = resp.json()["results"][0]
        assert "admin" in result["app_access"]
        assert "web" in result["app_access"]

    def test_app_access_viewer_has_web_only(self, superadmin_client, viewer):
        resp = superadmin_client.get(self.url + f"?search={viewer.email}")
        result = resp.json()["results"][0]
        assert result["app_access"] == ["web"]

    def test_is_active_true_for_verified_user(self, superadmin_client, viewer):
        resp = superadmin_client.get(self.url + f"?search={viewer.email}")
        result = resp.json()["results"][0]
        assert result["is_active"] is True


# ---------------------------------------------------------------------------
# Create user
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUserCreate:
    url = "/api/users/"

    def test_create_viewer(self, superadmin_client, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        resp = superadmin_client.post(self.url, {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "janedoe@example.com",
            "role": "viewer",
        }, format="json")
        assert resp.status_code == 201
        assert EmailAddress.objects.filter(email="janedoe@example.com").exists()

    def test_create_admin_user(self, superadmin_client, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        resp = superadmin_client.post(self.url, {
            "first_name": "New",
            "last_name": "Admin",
            "email": "newadmin@example.com",
            "role": "admin",
        }, format="json")
        assert resp.status_code == 201
        user = EmailAddress.objects.get(email="newadmin@example.com").user
        assert user.is_staff is True

    def test_create_with_organisation(self, superadmin_client, org, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        resp = superadmin_client.post(self.url, {
            "first_name": "Org",
            "last_name": "Member",
            "email": "orgmember@example.com",
            "role": "viewer",
            "organisation_id": str(org.id),
            "organisation_role": "viewer",
        }, format="json")
        assert resp.status_code == 201
        user = EmailAddress.objects.get(email="orgmember@example.com").user
        assert OrganisationMembership.objects.filter(organisation=org, user=user).exists()

    def test_duplicate_email_returns_400(self, superadmin_client, viewer):
        viewer_email = EmailAddress.objects.get(user=viewer).email
        resp = superadmin_client.post(self.url, {
            "first_name": "Dup",
            "email": viewer_email,
            "role": "viewer",
        }, format="json")
        assert resp.status_code == 400

    def test_missing_email_returns_400(self, superadmin_client):
        resp = superadmin_client.post(self.url, {"first_name": "NoEmail", "role": "viewer"}, format="json")
        assert resp.status_code == 400

    def test_invalid_role_returns_400(self, superadmin_client):
        resp = superadmin_client.post(self.url, {
            "first_name": "Bad",
            "email": "badrole@example.com",
            "role": "god_mode",
        }, format="json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Detail / Update
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUserDetail:

    def test_superadmin_gets_any_user(self, superadmin_client, viewer):
        resp = superadmin_client.get(f"/api/users/{viewer.id}/")
        assert resp.status_code == 200
        assert resp.json()["email"] == viewer.email

    def test_admin_gets_user_in_own_org(self, admin_client, viewer_in_org):
        resp = admin_client.get(f"/api/users/{viewer_in_org.id}/")
        assert resp.status_code == 200

    def test_admin_cannot_get_unrelated_user(self, admin_client, db):
        outsider = _make_viewer("out2", "out2@example.com")
        resp = admin_client.get(f"/api/users/{outsider.id}/")
        assert resp.status_code == 404

    def test_get_nonexistent_returns_404(self, superadmin_client, db):
        import uuid
        resp = superadmin_client.get(f"/api/users/{uuid.uuid4()}/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestUserUpdate:

    def test_patch_name(self, superadmin_client, viewer):
        resp = superadmin_client.patch(f"/api/users/{viewer.id}/", {
            "first_name": "Updated", "last_name": "Name"
        }, format="json")
        assert resp.status_code == 200
        viewer.refresh_from_db()
        assert viewer.first_name == "Updated"

    def test_patch_role_promotes_to_admin(self, superadmin_client, viewer):
        resp = superadmin_client.patch(f"/api/users/{viewer.id}/", {"role": "admin"}, format="json")
        assert resp.status_code == 200
        viewer.refresh_from_db()
        assert viewer.is_staff is True
        assert viewer.userprofile.role == UserProfile.Role.ADMIN

    def test_patch_add_to_organisation(self, superadmin_client, viewer, org):
        resp = superadmin_client.patch(f"/api/users/{viewer.id}/", {
            "organisation_id": str(org.id),
            "organisation_role": "viewer",
        }, format="json")
        assert resp.status_code == 200
        assert OrganisationMembership.objects.filter(organisation=org, user=viewer).exists()

    def test_patch_duplicate_email_returns_400(self, superadmin_client, viewer, admin):
        resp = superadmin_client.patch(f"/api/users/{viewer.id}/", {"email": admin.email}, format="json")
        assert resp.status_code == 400

    def test_patch_is_active_false(self, superadmin_client, viewer):
        resp = superadmin_client.patch(f"/api/users/{viewer.id}/", {"is_active": False}, format="json")
        assert resp.status_code == 200
        viewer.refresh_from_db()
        assert viewer.is_active is False


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUserExport:
    url = "/api/users/export/"

    def test_export_returns_csv(self, superadmin_client, viewer):
        resp = superadmin_client.get(self.url)
        assert resp.status_code == 200
        assert "text/csv" in resp["Content-Type"]

    def test_export_contains_user_data(self, superadmin_client, viewer):
        resp = superadmin_client.get(self.url)
        content = resp.content.decode()
        assert viewer.email in content

    def test_unauthenticated_returns_401(self, db):
        resp = APIClient().get(self.url)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUserImport:
    url = "/api/users/import/"

    def test_import_csv_creates_users(self, superadmin_client, settings, db):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        csv_content = (
            b"first_name,last_name,email,role,organisation_name,organisation_role\n"
            b"Alice,Smith,alice.import@example.com,viewer,,\n"
            b"Bob,Jones,bob.import@example.com,data_manager,,\n"
        )
        f = io.BytesIO(csv_content)
        f.name = "users.csv"
        resp = superadmin_client.post(self.url, {"file": f}, format="multipart")
        assert resp.status_code == 201
        assert resp.json()["created"] == 2
        assert EmailAddress.objects.filter(email="alice.import@example.com").exists()
        assert EmailAddress.objects.filter(email="bob.import@example.com").exists()

    def test_import_csv_skips_duplicate_emails(self, superadmin_client, viewer, settings, db):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        # viewer's plaintext email is stored in allauth EmailAddress
        viewer_email = EmailAddress.objects.get(user=viewer).email
        csv_content = (
            b"first_name,last_name,email,role\n"
            + f"Existing,User,{viewer_email},viewer\n".encode()
        )
        f = io.BytesIO(csv_content)
        f.name = "users.csv"
        resp = superadmin_client.post(self.url, {"file": f}, format="multipart")
        # Should have errors for the duplicate
        data = resp.json()
        assert "errors" in data

    def test_import_no_file_returns_400(self, superadmin_client, db):
        resp = superadmin_client.post(self.url, {}, format="multipart")
        assert resp.status_code == 400

    def test_import_csv_with_organisation(self, superadmin_client, org, settings, db):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        csv_content = (
            b"first_name,last_name,email,role,organisation_name,organisation_role\n"
            + f"Org,Member,orgmember2@example.com,viewer,{org.name},viewer\n".encode()
        )
        f = io.BytesIO(csv_content)
        f.name = "users.csv"
        resp = superadmin_client.post(self.url, {"file": f}, format="multipart")
        assert resp.status_code == 201
        user = EmailAddress.objects.get(email="orgmember2@example.com").user
        assert OrganisationMembership.objects.filter(organisation=org, user=user).exists()
