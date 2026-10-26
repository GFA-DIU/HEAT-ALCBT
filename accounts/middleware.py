from django.http import HttpResponse


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


# EmailVerificationMiddleware used to live here. It redirected every
# authenticated non-staff user whose address was not confirmed to a dead-end
# "Confirm your email address" page, and the Resend button on that page only
# appeared after seven days - so anyone whose confirmation mail went to spam
# was locked out of BEAT for a week with no way to ask for another one.
#
# On 2026-10-26 it was blocking 359 of 1,205 production accounts, 30% of the
# user base, and only 20 of those had signed up in the previous 90 days: the
# rest had hit the wall and never come back. The gate was removed rather than
# repaired. Confirmation mail still goes out (ACCOUNT_EMAIL_VERIFICATION is
# "optional" in settings.py) and people can still confirm, it is simply no
# longer a condition of using the tool.
#
# The trade-off, recorded deliberately: nothing now proves a signup address is
# real, so typo'd and invented addresses create working accounts.
