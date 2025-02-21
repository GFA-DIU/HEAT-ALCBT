from django.shortcuts import redirect
from django.urls import reverse


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            allowed_paths = [
                reverse('account_login'),
                reverse('account_signup'),
                reverse('account_reset_password'),
                reverse('admin:login'),
                reverse('privacy_policy'),
                reverse('terms_of_use'),
                # Add other public paths if necessary
            ]
            if request.path not in allowed_paths:
                return redirect('account_login')
        return self.get_response(request)