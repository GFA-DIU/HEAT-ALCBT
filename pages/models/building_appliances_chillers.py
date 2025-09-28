from django.db import models
from .building import (
    Building,
)
from django.core.validators import MinValueValidator, MaxValueValidator

from django.utils.translation import gettext_lazy as _


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


# BuildingOperation
class BuildingOperation(models.Model):
    building = models.OneToOneField(Building, on_delete=models.CASCADE, related_name="operation",
                                    verbose_name=_("Building"))
    number_of_residents = models.PositiveIntegerField(verbose_name=_("Number of Residents"))
    operation_hours_per_workday = models.PositiveSmallIntegerField(
        choices=[(i, _(str(i))) for i in range(1, 25)],
        verbose_name=_("Operation Hours per Workday")
    )
    workdays_per_week = models.PositiveSmallIntegerField(
        choices=[(i, _(str(i))) for i in range(1, 8)],
        verbose_name=_("Workdays per Week")
    )
    workweeks_per_year = models.PositiveSmallIntegerField(
        choices=[(i, _(str(i))) for i in range(1, 53)],
        verbose_name=_("Workweeks per Year")
    )
    renewable_energy_percent = models.PositiveIntegerField(verbose_name=_("Renewable Energy (%)"),
                                                           help_text=_(
                                                               "Percentage of the annual energy consumption of the "
                                                               "building produced on site from renewable sources"))
    energy_monitoring_control_systems = models.BooleanField(verbose_name=_("Energy Monitoring and Control Systems"),
                                                            default=False)


# CoolingSystemChiller
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


# CoolingSystemAirConditioner Model
class CoolingSystemAirConditioner(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="air_conditioners",
                                 verbose_name=_("Building"))
    ac_type = models.CharField(
        max_length=50,
        choices=[
            ('vrv', _("VRV/VRF (Variable Refrigerant Volume/Flow)")),
            ('split', _("Split Air Conditioners"))
        ],
        verbose_name=_("Air Conditioners Type")
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
    total_cooling_load_rt = models.PositiveIntegerField(verbose_name=_("Total Cooling Load for Split/VRV (RT)"))
    baseline_efficiency_kw_per_rt = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                                        verbose_name=_(
                                                            "Baseline Split Unit/VRV System Efficiency (kW/RT)"))
    baseline_refrigerant_emission_factor = models.PositiveIntegerField(null=True, blank=True, verbose_name=_(
        "Baseline Refrigerant Emission Factor (GWP)"))
    baseline_leakage_factor_percent = models.PositiveIntegerField(default=2,
                                                                  verbose_name=_("Baseline Leakage Factor (%)"))
    total_energy_consumption_kwh_per_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_(
        "Total Energy Consumption of Cooling System Annually (kWh/year)"))
    number_of_units = models.PositiveIntegerField(verbose_name=_("Total Number of Split/VRV Units"))
    total_system_power_kw = models.PositiveIntegerField(null=True, blank=True,
                                                        verbose_name=_("Total Split Unit/VRV System Power (kW)"))
    cop = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("COP"))
    iseer_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                       verbose_name=_("ISEER Rating"))
    energy_efficiency_label = models.PositiveSmallIntegerField(null=True, blank=True,
                                                               choices=[(i, _(str(i))) for i in range(1, 6)],
                                                               verbose_name=_("Energy Efficiency Label"))


class VentilationType(models.TextChoices):
    AHU = "AHU", _("Air Handling Units (AHUs)")
    FCU = "FCU", _("Fan Coil Units (FCUs)")
    CASSETTE_AC = "CASSETTE_AC", _("Ceiling or Wall Mounted Cassette ACs")
    DOAS = "DOAS", _("DOAS")
    FAN = "FAN", _("Ceiling/Exhaust/Wall Fan")
    OTHER = "OTHER", _("Other Ventilation Type")


VentilationCapacity = VentilationType


class VentilationSystem(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="ventilation_systems",
                                 verbose_name=_("Building"))

    ventilation_type = models.CharField(
        max_length=50,
        choices=VentilationType.choices,
        verbose_name=_("Ventilation Type")
    )

    ventilation_capacity = models.CharField(
        max_length=50,
        choices=VentilationType.choices,  # or VentilationCapacity if different
        verbose_name=_("Ventilation Capacity")
    )

    baseline_efficiency_w_cmh = models.PositiveIntegerField(
        verbose_name=_("Baseline Ventilation System Efficiency (W/CMH)"))
    operation_hours_per_workday = models.PositiveSmallIntegerField(null=True, blank=True,
                                                                   verbose_name=_("Operation Hours per Workday"))
    workdays_per_week = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Workdays per Week"))
    workweeks_per_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Workweeks per Year"))
    total_power_input_w = models.PositiveIntegerField(verbose_name=_("Total Ventilation System Power Input (W)"))
    air_flow_rate = models.PositiveIntegerField(verbose_name=_("Air Flow Rate (CMH/CFM)"))
    demand_controlled_ventilation = models.BooleanField(
        verbose_name=_("Installation of Demand Controlled Ventilation (DCV)"), default=False)
    variable_speed_drives = models.BooleanField(verbose_name=_("Installation of Variable Speed Drives (VSDs)"),
                                                default=False)
    number_of_units_installed = models.PositiveIntegerField(
        verbose_name=_("Total Number of Ventilation Type Installed"))
    total_energy_consumption_kwh_per_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_(
        "Total Energy Consumption of Ventilation System Annually (kWh/year)"))
    energy_efficiency_label = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Energy Efficiency Label")
    )


class RoomType(models.TextChoices):
    OFFICE_CONFERENCE = "OFFICE_CONFERENCE", _("Office: Conference Room")
    HOSPITAL_PATIENT = "HOSPITAL_PATIENT", _("Hospital: Patient Room")
    RESIDENTIAL_KITCHEN = "RESIDENTIAL_KITCHEN", _("Residential: Kitchen")
    RESIDENTIAL_DINING = "RESIDENTIAL_DINING", _("Residential: Dining")


class LightingBulbType(models.TextChoices):
    CFL = "CFL", _("CFL (Compact Fluorescent Lamp) Lights")
    LED = "LED", _("LED (Light Emitting Diode) Lights")
    T5_T8 = "T5_T8", _("T5 and T8 Fluorescent Tube Lights")
    OTHER = "OTHER", _("Other Lighting Type")


class LightingSystem(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="lighting_systems",
                                 verbose_name=_("Building"))

    room_type = models.CharField(
        max_length=50,
        choices=RoomType.choices,
        verbose_name=_("Room Type")
    )

    area_of_room = models.PositiveIntegerField(verbose_name=_("Area of Room (m²)"))

    lighting_bulb_type = models.CharField(
        max_length=50,
        choices=LightingBulbType.choices,
        verbose_name=_("Lighting Bulb Type")
    )

    number_of_bulbs = models.PositiveIntegerField(verbose_name=_("Number of Lighting Bulbs"))
    operation_hours_per_workday = models.PositiveSmallIntegerField(verbose_name=_("Operation Hours per Workday"))
    workdays_per_week = models.PositiveSmallIntegerField(verbose_name=_("Workdays per Week"))
    workweeks_per_year = models.PositiveSmallIntegerField(verbose_name=_("Workweeks per Year"))
    light_bulb_power_rating_w = models.PositiveIntegerField(verbose_name=_("Light Bulb Power Rating (W)"))
    baseline_lighting_power_density = models.PositiveIntegerField(null=True, blank=True, verbose_name=_(
        "Baseline Lighting Power Density (W/m²)"))
    sensors_installed = models.BooleanField(verbose_name=_("Installation of Sensors"), default=False)
    total_energy_consumption_kwh_per_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_(
        "Total Energy Consumption of Lighting System Annually (kWh/year)"))
    energy_efficiency_label = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Energy Efficiency Label")
    )


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


class HotWaterSystemType(models.TextChoices):
    HEAT_PUMP = "HEAT_PUMP", _("Heat Pump Water Heater")
    BOILER = "BOILER", _("Boiler")
    SOLAR = "SOLAR", _("Solar Water Heaters")


class FuelType(models.TextChoices):
    ELECTRICITY = "ELECTRICITY", _("Electricity")
    LIGHT_FUEL_OIL = "LIGHT_FUEL_OIL", _("Light Fuel Oil")
    HEAVY_FUEL_OIL = "HEAVY_FUEL_OIL", _("Heavy Fuel Oil")
    LPG = "LPG", _("Liquefied Petroleum Gas (LPG)")
    NATURAL_GAS = "NATURAL_GAS", _("Natural Gas")
    COAL = "COAL", _("Coal")
    LIGNITE = "LIGNITE", _("Lignite")
    DIESEL = "DIESEL", _("Diesel")
    KEROSENE = "KEROSENE", _("Kerosene")
    FIRE_WOOD_LOG = "FIRE_WOOD_LOG", _("Fire Wood (Log Wood)")
    FIRE_WOOD_CHIPS = "FIRE_WOOD_CHIPS", _("Fire Wood (Wood Chips)")
    FIRE_WOOD_PELLETS = "FIRE_WOOD_PELLETS", _("Fire Wood (Wood Pellets)")
    CHAR_COAL = "CHAR_COAL", _("Char Coal")
    OTHER = "OTHER", _("Other")


class HotWaterSystem(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="hot_water_systems",
        verbose_name=_("Building")
    )

    system_type = models.CharField(
        max_length=50,
        choices=HotWaterSystemType.choices,
        verbose_name=_("Type of Hot Water System")
    )

    operation_hours_per_workday = models.PositiveSmallIntegerField(
        verbose_name=_("Operation Hours for Hot Water per Workday")
    )
    workdays_per_week = models.PositiveSmallIntegerField(verbose_name=_("Workdays per Week"))
    workweeks_per_year = models.PositiveSmallIntegerField(verbose_name=_("Workweeks per Year"))

    fuel_type = models.CharField(
        max_length=50,
        choices=FuelType.choices,
        verbose_name=_("Fuel Type")
    )

    fuel_consumption = models.PositiveIntegerField(verbose_name=_("Fuel Consumption (Liters/m³)"))

    power_input_kw = models.PositiveIntegerField(verbose_name=_("Hot Water System Power Input (kW)"))
    baseline_efficiency_cop = models.PositiveIntegerField(verbose_name=_("Baseline Hot Water System Efficiency (COP)"))
    baseline_equipment_efficiency_percentage = models.PositiveIntegerField(
        verbose_name=_("Baseline Hot Water System Equipment Efficiency Level (%)"))

    heat_recovery_installed = models.BooleanField(
        verbose_name=_("Installation of Heat Recovery Systems"),
        default=False
    )

    number_of_equipments = models.PositiveIntegerField(verbose_name=_("Number of Hot Water Equipment Installed"))

    energy_efficiency_label = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Energy Efficiency Label")
    )

    class Meta:
        verbose_name = _("Hot Water System")
        verbose_name_plural = _("Hot Water Systems")


class EnergySourceType(models.TextChoices):
    ELECTRICITY = "ELECTRICITY", _("Electricity")
    LIGHT_FUEL_OIL = "LIGHT_FUEL_OIL", _("Light Fuel Oil")
    HEAVY_FUEL_OIL = "HEAVY_FUEL_OIL", _("Heavy Fuel Oil")
    LPG = "LPG", _("Liquefied Petroleum Gas (LPG)")
    NATURAL_GAS = "NATURAL_GAS", _("Natural Gas")
    COAL = "COAL", _("Coal")
    LIGNITE = "LIGNITE", _("Lignite")
    DIESEL = "DIESEL", _("Diesel")
    KEROSENE = "KEROSENE", _("Kerosene")
    FIRE_WOOD_LOG = "FIRE_WOOD_LOG", _("Fire Wood (Log Wood)")
    FIRE_WOOD_CHIPS = "FIRE_WOOD_CHIPS", _("Fire Wood (Wood Chips)")
    FIRE_WOOD_PELLETS = "FIRE_WOOD_PELLETS", _("Fire Wood (Wood Pellets)")
    CHAR_COAL = "CHAR_COAL", _("Char Coal")
    OTHER = "OTHER", _("Other")


class EnergyUnit(models.TextChoices):
    KWH_A = "KWH_A", _("kWh/a")
    KG_A = "KG_A", _("kg/a")
    M3_A = "M3_A", _("m³/a")
    LITER_A = "LITER_A", _("liter/a")


# Parent Model: OperationEnergyDemand
class OperationEnergyDemand(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="operation_energy_demands",
        verbose_name=_("Building")
    )

    # This is calculated (not inputted manually)
    energy_use_intensity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Energy Use Intensity (EUI) (kWh/m²/a)")
    )

    renewable_energy_adoption = models.PositiveIntegerField(
        verbose_name=_("Renewable Energy Adoption (%)")
    )

    class Meta:
        verbose_name = _("Operation Energy Demand")
        verbose_name_plural = _("Operation Energy Demands")


# Child Model: EnergyConsumption
class EnergyConsumption(models.Model):
    operation_demand = models.ForeignKey(
        OperationEnergyDemand,
        on_delete=models.CASCADE,
        related_name="consumptions",
        verbose_name=_("Operation Energy Demand")
    )

    energy_source = models.CharField(
        max_length=50,
        choices=EnergySourceType.choices,
        verbose_name=_("Energy Source Type")
    )

    consumption_value = models.PositiveIntegerField(
        verbose_name=_("Consumption Value (End Energy Value from Bill)")
    )

    unit = models.CharField(
        max_length=20,
        choices=EnergyUnit.choices,
        verbose_name=_("Unit")
    )

    class Meta:
        verbose_name = _("Energy Consumption")
        verbose_name_plural = _("Energy Consumptions")
