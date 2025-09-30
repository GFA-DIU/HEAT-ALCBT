from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building

class LiftEscalatorSystem(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="lift_escalator_systems",
        verbose_name=_("Building")
    )

    number_of_lifts = models.PositiveIntegerField(verbose_name=_("Number of Lifts"))

    lift_regenerative_features = models.BooleanField(
        verbose_name=_("Installation of Lift Regenerative Features"),
        default=False
    )

    vvvf_sleep_mode = models.BooleanField(
        verbose_name=_("Installation of VVVF and Sleep Mode"),
        default=False
    )

    annual_energy_consumption_kwh = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Annual Lift System Energy Consumption (kWh/year)")
    )

    class Meta:
        verbose_name = _("Lift and Escalator System")
        verbose_name_plural = _("Lift and Escalator Systems")