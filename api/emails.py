"""Email sending utilities for the API module."""
import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_organisation_invitation(user, organisation, role, added_by):
    """
    Send an email to a user notifying them they've been added to an organisation.

    Args:
        user: CustomUser instance being invited
        organisation: Organisation instance
        role: MemberRole string (e.g. 'admin', 'data_manager', 'viewer')
        added_by: CustomUser instance who performed the action
    """
    subject = f"You've been added to {organisation.name} on BEAT"

    context = {
        "user_name": user.get_full_name() or user.username,
        "organisation_name": organisation.name,
        "role": role.replace("_", " ").title(),
        "industry": organisation.get_industry_display() if hasattr(organisation, "get_industry_display") else organisation.industry,
        "added_by": added_by.get_full_name() or added_by.username,
        "current_year": datetime.now().year,
    }

    html_body = render_to_string("account/email/organisation_invitation_message.html", context)

    try:
        to_email = str(user.email)
        from_email = settings.DEFAULT_FROM_EMAIL or "noreply@beat.example.com"
        msg = EmailMultiAlternatives(subject=subject, body="", from_email=from_email, to=[to_email])
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        logger.info("Sent organisation invitation email to %s for org %s", user, organisation)
    except Exception:
        logger.exception("Failed to send organisation invitation email to %s", user)