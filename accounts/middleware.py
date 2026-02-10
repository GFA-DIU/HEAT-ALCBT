from allauth.account.models import EmailAddress
from django.shortcuts import redirect
from django.urls import reverse


ALLOWED_PATHS_WHEN_UNVERIFIED = [
    "/accounts/verify-email/",
    "/accounts/resend-confirmation/",
    "/accounts/confirm-email/",
    "/accounts/logout/",
    "/accounts/login/",
    "/cookies/",
    "/__debug__/",
]


class EmailVerificationMiddleware:
    """
    Redirects authenticated users with unverified emails to the email
    verification page. They cannot access any other part of the platform
    until their email is confirmed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_staff:
            path = request.path

            # Allow access to admin, static files and allowed auth paths
            if not any(path.startswith(allowed) for allowed in ALLOWED_PATHS_WHEN_UNVERIFIED):
                email_verified = EmailAddress.objects.filter(
                    user=request.user, verified=True
                ).exists()

                if not email_verified:
                    return redirect(reverse("verify_email"))

        return self.get_response(request)
