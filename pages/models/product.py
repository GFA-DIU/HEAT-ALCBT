from django.db import models
from django.utils.translation import gettext as _

from .epd import EPD, Unit


class BaseProduct(models.Model):
    """Join Table connecting EPDs to a different different object. Products are EPDs with quantity and results."""
    description = models.CharField(
        _("Description"), max_length=255, null=True, blank=True
    )
    epd = models.ForeignKey(EPD, on_delete=models.CASCADE)
    input_unit = models.CharField(
        _("Unit for quantity of EPD"),
        max_length=20,
        choices=Unit.choices,
        default=Unit.UNKNOWN,
    )
    quantity = models.DecimalField(
        _("Quantity of EPD"),
        max_digits=10,
        decimal_places=2,
        null=False,
        blank=False,
    )

    class Meta:
        abstract = True  # This ensures it won't create its own table.