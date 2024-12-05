from django.db import models
from django.utils.translation import gettext as _

from accounts.models import CustomUser


class BaseModel(models.Model):
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)
    public = models.BooleanField(
        _("Public"), help_text=_("Is it visible to all roles"), default=False
    )
    draft = models.BooleanField(
        _("Draft"), help_text=_("Is it still a draft"), default=False
    )