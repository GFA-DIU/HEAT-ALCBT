from allauth.account.models import EmailAddress
from django.contrib.messages import get_messages
from django.http import HttpResponse
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


class HtmxLoginRedirectMiddleware:
    """
    When an HTMX request is redirected to the login page (session expired),
    Django returns a 302 which HTMX would render inline. Instead, return a
    200 with HX-Redirect so the browser does a full-page redirect to login.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        is_htmx = request.headers.get('HX-Request') == 'true'
        if response.status_code == 302 and is_htmx:
            location = response.get('Location') or ''
            if '/accounts/login/' in location:
                redirect_response = HttpResponse(status=200)
                redirect_response['HX-Redirect'] = location
                return redirect_response
        return response


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
                    list(get_messages(request))
                    return redirect(reverse("verify_email"))

        return self.get_response(request)
