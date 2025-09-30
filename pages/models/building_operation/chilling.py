from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building

class RefrigerantType(models.TextChoices):
    R290 = "R-290", _("R-290 (Propane)")
    R600A = "R-600a", _("R-600a (Isobutane)")
    R717 = "R-717", _("R-717 (Ammonia)")
    R744 = "R-744", _("R-744 (CO2)")
    R12 = "R-12", _("R-12")
    R13 = "R-13", _("R-13")
    R22 = "R-22", _("R-22")
    R23 = "R-23", _("R-23")
    R32 = "R-32", _("R-32")
    R41 = "R-41", _("R-41")
    R125 = "R-125", _("R-125")
    R134A = "R-134a", _("R-134a")
    R143A = "R-143a", _("R-143a")
    R227EA = "R-227EA", _("R-227EA")
    R236CB = "R-236CB", _("R-236CB")
    R236EA = "R-236EA", _("R-236EA")
    R236FA = "R-236FA", _("R-236FA")
    R245CA = "R-245CA", _("R-245CA")
    R245FA = "R-245FA", _("R-245FA")
    R404A = "R-404A", _("R-404A")
    R407A = "R-407A", _("R-407A")
    R407B = "R-407B", _("R-407B")
    R407C = "R-407C", _("R-407C")
    R407D = "R-407D", _("R-407D")
    R407E = "R-407E", _("R-407E")
    R407F = "R-407F", _("R-407F")
    R407G = "R-407G", _("R-407G")
    R410A = "R-410A", _("R-410A")
    R410B = "R-410B", _("R-410B")
    R413A = "R-413A", _("R-413A")
    R417A = "R-417A", _("R-417A")
    R417B = "R-417B", _("R-417B")
    R417C = "R-417C", _("R-417C")
    R419A = "R-419A", _("R-419A")
    R419B = "R-419B", _("R-419B")
    R421A = "R-421A", _("R-421A")
    R421B = "R-421B", _("R-421B")
    R422A = "R-422A", _("R-422A")
    R422B = "R-422B", _("R-422B")
    R422C = "R-422C", _("R-422C")
    R422D = "R-422D", _("R-422D")
    R423A = "R-423A", _("R-423A")
    R424A = "R-424A", _("R-424A")
    R425A = "R-425A", _("R-425A")
    R426A = "R-426A", _("R-426A")
    R427A = "R-427A", _("R-427A")
    R428A = "R-428A", _("R-428A")
    R429A = "R-429A", _("R-429A")
    R430A = "R-430A", _("R-430A")
    R431A = "R-431A", _("R-431A")
    R434A = "R-434A", _("R-434A")
    R435A = "R-435A", _("R-435A")
    R437A = "R-437A", _("R-437A")
    R438A = "R-438A", _("R-438A")
    R439A = "R-439A", _("R-439A")
    R440A = "R-440A", _("R-440A")
    R442A = "R-442A", _("R-442A")
    R444A = "R-444A", _("R-444A")
    R444B = "R-444B", _("R-444B")
    R445A = "R-445A", _("R-445A")
    R446A = "R-446A", _("R-446A")
    R447A = "R-447A", _("R-447A")
    R447B = "R-447B", _("R-447B")
    R448A = "R-448A", _("R-448A")
    R449A = "R-449A", _("R-449A")
    R449B = "R-449B", _("R-449B")
    R449C = "R-449C", _("R-449C")
    R450A = "R-450A", _("R-450A")
    R451A = "R-451A", _("R-451A")
    R451B = "R-451B", _("R-451B")
    R452A = "R-452A", _("R-452A")
    R452B = "R-452B", _("R-452B")
    R452C = "R-452C", _("R-452C")
    R453A = "R-453A", _("R-453A")
    R454A = "R-454A", _("R-454A")
    R454B = "R-454B", _("R-454B")
    R454C = "R-454C", _("R-454C")
    R455A = "R-455A", _("R-455A")
    R456A = "R-456A", _("R-456A")
    R457A = "R-457A", _("R-457A")
    R458A = "R-458A", _("R-458A")
    R500 = "R-500", _("R-500")
    R502 = "R-502", _("R-502")
    R503 = "R-503", _("R-503")
    R507A = "R-507A", _("R-507A")
    R508A = "R-508A", _("R-508A")
    R508B = "R-508B", _("R-508B")
    R512A = "R-512A", _("R-512A")
    R513A = "R-513A", _("R-513A")
    R513B = "R-513B", _("R-513B")
    R515A = "R-515A", _("R-515A")
    OTHER = "OTHER", _("Other")


class CoolingSystemChiller(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="chillers",
                                 verbose_name=_("Building"))
    chiller_type = models.CharField(
        max_length=50,
        choices=[
            ('water_cooled', _("Water Cooled Chillers")),
            ('air_cooled', _("Air Cooled Chillers"))
        ],
        verbose_name=_("Chiller Type")
    )
    year_of_installation = models.PositiveIntegerField(verbose_name=_("Year of Installation"))
    operation_hours_per_workday = models.PositiveSmallIntegerField(null=True, blank=True,
                                                                   verbose_name=_("Operation Hours per Workday"))
    workdays_per_week = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Workdays per Week"))
    workweeks_per_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Workweeks per Year"))
    refrigerant_type = models.CharField(
        max_length=50,
        choices=RefrigerantType.choices,
        verbose_name=_("Type of Refrigerants")
    )
    refrigerant_quantity_kg = models.PositiveIntegerField(verbose_name=_("Refrigerant Quantity (Kg)"))
    total_cooling_load_rt = models.PositiveIntegerField(verbose_name=_("Total Cooling Load for Chiller System (RT)"))
    baseline_cooling_efficiency_kw_h = models.PositiveIntegerField(null=True, blank=True,
                                                                   verbose_name=_("Baseline Cooling Efficiency (kW/h)"))
    variable_speed_drives = models.BooleanField(verbose_name=_("Installation of Variable Speed Drives (VSDs)"),
                                                default=False)
    heat_recovery_system = models.BooleanField(verbose_name=_("Installation of Heat Recovery Systems"), default=False)
    baseline_refrigerant_emission_factor = models.PositiveIntegerField(null=True, blank=True, verbose_name=_(
        "Baseline Refrigerant Emission Factor (GWP)"))
    baseline_leakage_factor_percent = models.PositiveIntegerField(default=2,
                                                                  verbose_name=_("Baseline Leakage Factor (%)"))
    total_energy_consumption_kwh_per_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_(
        "Total Energy Consumption of Chiller System Annually (kWh/year)"))
    number_of_chillers = models.PositiveIntegerField(verbose_name=_("Number of Chillers"))
    water_cooled_chiller_cooling_load_factor_percent = models.PositiveIntegerField(null=True, blank=True,
                                                                                   verbose_name=_(
                                                                                       "Water-Cooled Chiller Cooling Load Factor (%)"))
    total_chiller_system_power_input_kw = models.PositiveIntegerField(null=True, blank=True, verbose_name=_(
        "Total Chiller System Power Input (kW)"))
    cop = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("COP"))
    ip_lv = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("IPLV"))
    energy_efficiency_label = models.PositiveSmallIntegerField(null=True, blank=True,
                                                               choices=[(i, _(str(i))) for i in range(1, 6)],
                                                               verbose_name=_("Energy Efficiency Label"))