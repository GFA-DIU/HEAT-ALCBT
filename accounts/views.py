import logging
from datetime import timedelta

from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.account.utils import send_email_confirmation
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

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


@login_required
def verify_email(request):
    """Page shown to authenticated users who have not yet verified their email."""
    email_address = EmailAddress.objects.filter(user=request.user).first()

    can_resend = False
    if email_address and not email_address.verified:
        last_confirmation = EmailConfirmation.objects.filter(
            email_address=email_address
        ).order_by("-sent").first()
        if last_confirmation is None or last_confirmation.sent < timezone.now() - timedelta(weeks=1):
            can_resend = True

    return render(request, "account/verify_email.html", {
        "can_resend": can_resend,
        "email": request.user.email,
    })


@login_required
def resend_confirmation_email(request):
    """Resend email confirmation to the current user."""
    email_address = EmailAddress.objects.filter(user=request.user, verified=False).first()

    if email_address:
        last_confirmation = EmailConfirmation.objects.filter(
            email_address=email_address
        ).order_by("-sent").first()

        one_week_ago = timezone.now() - timedelta(weeks=1)
        if last_confirmation is None or last_confirmation.sent < one_week_ago:
            send_email_confirmation(request, request.user, signup=False)
            messages.success(request, "Confirmation email sent. Please check your inbox.")
        else:
            messages.info(request, "A confirmation email was already sent recently. Please check your inbox.")
    else:
        messages.warning(request, "No unverified email address found for your account.")

    return redirect("verify_email")


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