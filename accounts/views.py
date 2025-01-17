import logging

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

from .forms import CustomUserUpdateForm, UserProfileUpdateForm
from pages.models.building import Building
from pages.views.home import _delete_building

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
    if request.method == "DELETE":
        response = handle_delete_user(request)
        return response
    else:
        user_form = CustomUserUpdateForm(instance=request.user)
        profile_form = UserProfileUpdateForm(instance=request.user.userprofile)

    context = {"user_form": user_form, "profile_form": profile_form}

    return render(request, "account/update_profile.html", context)


@transaction.atomic
def handle_delete_user(request):
    User = get_user_model()
    buildings = Building.objects.filter(
        created_by__id=request.user.id
    ).values_list('id', flat=True)
    
    try:
        for building_id in buildings:
            _delete_building(building_id)
        
        # filter to avoid second DB call
        User.objects.filter(id=request.user.id).delete()
        messages.success(request, "Your profile was deleted successfully")
        response = HttpResponse()
        response['HX-Redirect'] = '/'  # Set the HX-Redirect header with the desired URL
        return response
    except:
        logger.exception("Deleting user %s failed", request.user)
        messages.warning(request, "Warning: Deleting Profile failed.")
        return redirect(to="update_profile")