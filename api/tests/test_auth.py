import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.account.models import EmailAddress

from accounts.models import CustomUser, UserProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    user = CustomUser.objects.create_user(
        username="adminuser",
        email="admin@example.com",
        password="AdminPass123!",
        is_staff=True,
    )
    # Mark email as verified
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    # Ensure role is synced
    user.userprofile.role = UserProfile.Role.ADMIN
    user.userprofile.save()
    return user


@pytest.fixture
def superadmin_user(db):
    user = CustomUser.objects.create_user(
        username="superadmin",
        email="superadmin@example.com",
        password="SuperPass123!",
        is_staff=True,
        is_superuser=True,
    )
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    user.userprofile.role = UserProfile.Role.SUPERADMIN
    user.userprofile.save()
    return user


@pytest.fixture
def viewer_user(db):
    user = CustomUser.objects.create_user(
        username="viewer",
        email="viewer@example.com",
        password="ViewerPass123!",
        is_staff=False,
    )
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


@pytest.fixture
def unverified_admin_user(db):
    user = CustomUser.objects.create_user(
        username="unverifiedadmin",
        email="unverified@example.com",
        password="AdminPass123!",
        is_staff=True,
    )
    # No EmailAddress record — not verified
    user.userprofile.role = UserProfile.Role.ADMIN
    user.userprofile.save()
    return user


@pytest.fixture
def admin_tokens(admin_user):
    refresh = RefreshToken.for_user(admin_user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


@pytest.fixture
def authenticated_admin_client(api_client, admin_user, admin_tokens):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_tokens['access']}")
    return api_client


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAdminLogin:
    url = "/api/auth/login/"

    def test_login_success_returns_tokens_and_user(self, api_client, admin_user):
        response = api_client.post(self.url, {"email": "admin@example.com", "password": "AdminPass123!"})
        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert "refresh" in data
        assert data["user"]["email"] == "admin@example.com"
        assert data["user"]["is_staff"] is True
        assert data["user"]["role"] == UserProfile.Role.ADMIN

    def test_login_superadmin_success(self, api_client, superadmin_user):
        response = api_client.post(self.url, {"email": "superadmin@example.com", "password": "SuperPass123!"})
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["is_superuser"] is True
        assert data["user"]["role"] == UserProfile.Role.SUPERADMIN

    def test_login_wrong_password_returns_400(self, api_client, admin_user):
        response = api_client.post(self.url, {"email": "admin@example.com", "password": "WrongPass!"})
        assert response.status_code == 400

    def test_login_nonexistent_email_returns_400(self, api_client, db):
        response = api_client.post(self.url, {"email": "nobody@example.com", "password": "SomePass123!"})
        assert response.status_code == 400

    def test_login_non_staff_user_returns_403(self, api_client, viewer_user):
        response = api_client.post(self.url, {"email": "viewer@example.com", "password": "ViewerPass123!"})
        assert response.status_code == 403
        assert "Access restricted" in response.json().get("detail", "")

    def test_login_unverified_email_returns_400(self, api_client, unverified_admin_user):
        response = api_client.post(self.url, {"email": "unverified@example.com", "password": "AdminPass123!"})
        assert response.status_code == 400
        data = response.json()
        # Error should mention email verification
        errors_str = str(data)
        assert "verified" in errors_str.lower() or "email" in errors_str.lower()

    def test_login_missing_email_returns_400(self, api_client, db):
        response = api_client.post(self.url, {"password": "SomePass123!"})
        assert response.status_code == 400

    def test_login_missing_password_returns_400(self, api_client, db):
        response = api_client.post(self.url, {"email": "admin@example.com"})
        assert response.status_code == 400

    def test_login_empty_body_returns_400(self, api_client, db):
        response = api_client.post(self.url, {})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Logout tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAdminLogout:
    url = "/api/auth/logout/"

    def test_logout_success(self, authenticated_admin_client, admin_tokens):
        response = authenticated_admin_client.post(self.url, {"refresh": admin_tokens["refresh"]})
        assert response.status_code == 200
        assert "logged out" in response.json().get("detail", "").lower()

    def test_logout_without_auth_returns_401(self, api_client, admin_tokens):
        response = api_client.post(self.url, {"refresh": admin_tokens["refresh"]})
        assert response.status_code == 401

    def test_logout_missing_refresh_token_returns_400(self, authenticated_admin_client):
        response = authenticated_admin_client.post(self.url, {})
        assert response.status_code == 400

    def test_logout_invalid_refresh_token_returns_400(self, authenticated_admin_client):
        response = authenticated_admin_client.post(self.url, {"refresh": "invalidtoken"})
        assert response.status_code == 400

    def test_logout_non_admin_returns_403(self, api_client, viewer_user, db):
        refresh = RefreshToken.for_user(viewer_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        response = api_client.post(self.url, {"refresh": str(refresh)})
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Token refresh tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTokenRefresh:
    url = "/api/auth/token/refresh/"

    def test_refresh_with_valid_token_returns_new_access(self, api_client, admin_tokens):
        response = api_client.post(self.url, {"refresh": admin_tokens["refresh"]})
        assert response.status_code == 200
        assert "access" in response.json()

    def test_refresh_with_invalid_token_returns_401(self, api_client, db):
        response = api_client.post(self.url, {"refresh": "notavalidtoken"})
        assert response.status_code == 401

    def test_refresh_missing_token_returns_400(self, api_client, db):
        response = api_client.post(self.url, {})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Forgot password tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAdminForgotPassword:
    url = "/api/auth/forgot-password/"

    def test_valid_admin_email_returns_200(self, api_client, admin_user, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        response = api_client.post(self.url, {"email": "admin@example.com"})
        assert response.status_code == 200
        assert "password reset" in response.json().get("detail", "").lower()

    def test_non_admin_email_returns_403(self, api_client, viewer_user):
        response = api_client.post(self.url, {"email": "viewer@example.com"})
        assert response.status_code == 403
        assert "Access restricted" in response.json().get("detail", "")

    def test_nonexistent_email_returns_200_no_info_leak(self, api_client, db):
        # Should return 200 and not reveal whether the account exists
        response = api_client.post(self.url, {"email": "ghost@example.com"})
        assert response.status_code == 200
        assert "password reset" in response.json().get("detail", "").lower()

    def test_missing_email_returns_400(self, api_client, db):
        response = api_client.post(self.url, {})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Profile tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAdminProfile:
    url = "/api/auth/profile/"

    def test_get_profile_returns_user_and_profile(self, authenticated_admin_client, admin_user):
        response = authenticated_admin_client.get(self.url)
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert "profile" in data
        assert data["user"]["email"] == "admin@example.com"
        assert data["user"]["role"] == UserProfile.Role.ADMIN

    def test_get_profile_without_auth_returns_401(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == 401

    def test_get_profile_non_admin_returns_403(self, api_client, viewer_user):
        refresh = RefreshToken.for_user(viewer_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        response = api_client.get(self.url)
        assert response.status_code == 403

    def test_patch_profile_updates_username(self, authenticated_admin_client, admin_user):
        response = authenticated_admin_client.patch(self.url, {"username": "newusername"})
        assert response.status_code == 200
        admin_user.refresh_from_db()
        assert admin_user.username == "newusername"

    def test_patch_profile_updates_first_last_name(self, authenticated_admin_client, admin_user):
        response = authenticated_admin_client.patch(
            self.url, {"first_name": "John", "last_name": "Doe"}
        )
        assert response.status_code == 200
        admin_user.refresh_from_db()
        assert admin_user.first_name == "John"
        assert admin_user.last_name == "Doe"

    def test_patch_profile_duplicate_username_returns_400(self, authenticated_admin_client, viewer_user):
        response = authenticated_admin_client.patch(self.url, {"username": viewer_user.username})
        assert response.status_code == 400

    def test_patch_profile_updates_consent_flag(self, authenticated_admin_client, admin_user):
        original = admin_user.userprofile.consent_flag
        response = authenticated_admin_client.patch(self.url, {"consent_flag": not original})
        assert response.status_code == 200
        admin_user.userprofile.refresh_from_db()
        assert admin_user.userprofile.consent_flag == (not original)