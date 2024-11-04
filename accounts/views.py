import logging

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .forms import CustomUserUpdateForm, UserProfileUpdateForm

logger = logging.getLogger(__name__)


@login_required
def update_profile(request):
    if request.method == "POST":
        user_form = CustomUserUpdateForm(request.POST, instance=request.user)
        profile_form = UserProfileUpdateForm(
            request.POST, instance=request.user.userprofile
        )
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            logger.info("Successfully updated user %s", request.user)
            messages.success(request, "Your profile is updated successfully")
            return redirect(to="update_profile")
    else:
        user_form = CustomUserUpdateForm(instance=request.user)
        profile_form = UserProfileUpdateForm(instance=request.user.userprofile)

    context = {"user_form": user_form, "profile_form": profile_form}

    return render(request, "account/update_profile.html", context)
