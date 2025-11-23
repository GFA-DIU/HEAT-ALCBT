from django import forms
from django.utils.translation import gettext as _

from pages.models.building_operation.hot_water import HotWaterSystem, HotWaterSystemType, FuelType


class HotWaterSystemForm(forms.ModelForm):

    system_type = forms.ChoiceField(
        label="Type of Hot Water System",
        choices=[('', '---------')] + HotWaterSystemType.choices,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    fuel_type = forms.ChoiceField(
        label="Fuel Type",
        choices=[('', '---------')] + FuelType.choices,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    operation_hours_per_workday = forms.IntegerField(
        label="Operation Hours per Workday",
        help_text="hours per day",
        min_value=0,
        max_value=24,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    workdays_per_week = forms.IntegerField(
        label="Workdays per Week",
        help_text="days per week",
        min_value=0,
        max_value=7,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    workweeks_per_year = forms.IntegerField(
        label="Workweeks per Year",
        help_text="weeks per year",
        min_value=0,
        max_value=52,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    fuel_consumption = forms.IntegerField(
        label="Fuel Consumption",
        help_text="Liters/m³",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    power_input_kw = forms.IntegerField(
        label="Hot Water System Power Input",
        help_text="kW",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    baseline_efficiency_cop = forms.IntegerField(
        label="Baseline Hot Water System Efficiency (COP)",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    baseline_equipment_efficiency_percentage = forms.IntegerField(
        label="Baseline Equipment Efficiency Level",
        help_text="%",
        min_value=0,
        max_value=100,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    heat_recovery_installed = forms.BooleanField(
        label="Installation of Heat Recovery Systems",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    number_of_equipments = forms.IntegerField(
        label="Number of Hot Water Equipment Installed",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    energy_efficiency_label = forms.ChoiceField(
        label="Energy Efficiency Label (Number of Stars)",
        choices=[('', '---------')] + [(i, str(i)) for i in range(1, 6)],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = HotWaterSystem
        fields = [
            "system_type",
            "fuel_type",
            "operation_hours_per_workday",
            "workdays_per_week",
            "workweeks_per_year",
            "fuel_consumption",
            "power_input_kw",
            "baseline_efficiency_cop",
            "baseline_equipment_efficiency_percentage",
            "heat_recovery_installed",
            "number_of_equipments",
            "energy_efficiency_label",
        ]