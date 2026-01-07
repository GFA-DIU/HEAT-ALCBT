import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from accounts.forms import CustomUserUpdateForm, UserProfileUpdateForm

logger = logging.getLogger(__name__)


@login_required
def view_profile(request):
    """Display and update user profile"""
    user = request.user
    profile = user.userprofile

    if request.method == "POST":
        user_form = CustomUserUpdateForm(request.POST, instance=user)
        profile_form = UserProfileUpdateForm(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            logger.info(f"Profile updated successfully for user: {user.email}")

            # Check if this is an AJAX request from the modal
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    "success": True,
                    "message": "Your profile has been updated successfully!"
                })

            messages.success(request, "Your profile has been updated successfully!")
            return redirect("profile")
        else:
            logger.warning(f"Profile update failed for user: {user.email}. Errors: {user_form.errors}, {profile_form.errors}")

            # Check if this is an AJAX request from the modal
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                if user_form.errors:
                    errors.update(user_form.errors)
                if profile_form.errors:
                    errors.update(profile_form.errors)
                return JsonResponse({
                    "success": False,
                    "errors": errors
                }, status=400)

            messages.error(request, "Please correct the errors below.")
    else:
        user_form = CustomUserUpdateForm(instance=user)
        profile_form = UserProfileUpdateForm(instance=profile)

    context = {
        "user_form": user_form,
        "profile_form": profile_form,
        "user": user,
        "profile": profile,
    }
    return render(request, "pages/profile/profile.html", context)