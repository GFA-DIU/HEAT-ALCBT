"""Signal handlers for user account events."""
import logging

from allauth.account.signals import user_signed_up
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(user_signed_up)
def set_new_user_flag(request, user, **kwargs):
    """
    Set a session flag when a new user signs up.
    This flag will be used to show the account success modal on first home page visit.
    """
    if request:
        request.session['show_account_success_modal'] = True
        logger.info(f"New user signup detected: {user.email}. Session flag set.")
