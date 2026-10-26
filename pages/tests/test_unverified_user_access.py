"""An unconfirmed email address must not lock a user out of BEAT.

accounts.middleware.EmailVerificationMiddleware used to redirect every
authenticated non-staff user without a verified EmailAddress to a dead-end
confirmation page, whose Resend button only appeared after seven days. On
2026-10-26 that was 359 of 1,205 production accounts.

These tests fail if the gate - or anything like it - comes back.
"""
import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.urls import NoReverseMatch, reverse

pytestmark = pytest.mark.django_db


def _unverified_user(email="unconfirmed@example.com"):
    """A user in exactly the state the old gate blocked: signed up, logged in,
    never clicked the confirmation link."""
    user = get_user_model().objects.create_user(
        username=email, email=email, password="pw-for-test-only")
    EmailAddress.objects.create(
        user=user, email=email, verified=False, primary=True)
    return user


def test_an_unverified_user_reaches_the_app_instead_of_a_confirmation_wall(client):
    client.force_login(_unverified_user())

    response = client.get("/", follow=False)

    assert response.status_code != 302 or "verify" not in (
        response.get("Location") or ""), (
        "an unverified user was redirected to %s" % response.get("Location"))


def test_no_middleware_gates_the_app_on_email_verification(settings):
    """Named explicitly: re-adding the class to MIDDLEWARE is the one change
    that would silently restore the lockout."""
    gates = [m for m in settings.MIDDLEWARE if "EmailVerification" in m]
    assert not gates, "an email verification gate is back in MIDDLEWARE: %s" % gates


def test_the_confirmation_wall_has_no_url_left():
    for name in ("verify_email", "resend_confirmation_email"):
        with pytest.raises(NoReverseMatch):
            reverse(name)


def test_verification_is_optional_not_mandatory(settings):
    """'mandatory' would block sign-in at the allauth layer instead, which is
    the same lockout by another route."""
    assert settings.ACCOUNT_EMAIL_VERIFICATION == "optional"
