from django import forms
from django.utils.translation import gettext as _

from pages.models.building_operation import HotWaterSystem, HotWaterSystemType, FuelType, EnergyEfficiencyLabelType


class HotWaterSystemForm(forms.ModelForm):
    """
    Form for validating Hot Water System data.
    Handles validation for creating and updating HWS records.
    """

    type_of_hot_water_system = forms.ChoiceField(
        label=_("Type of Hot Water System"),
        choices=HotWaterSystemType.choices,
        required=True,
        error_messages={
            'required': _('Type of hot water system is required.'),
            'invalid_choice': _('Invalid hot water system type selected.')
        }
    )

    fuel_type = forms.ChoiceField(
        label=_("Fuel Type"),
        choices=FuelType.choices,
        required=True,
        error_messages={
            'required': _('Fuel type is required.'),
            'invalid_choice': _('Invalid fuel type selected.')
        }
    )

    operating_hours_per_day = forms.DecimalField(
        label=_("Operating Hours per Day"),
        min_value=0,
        max_value=24,
        decimal_places=2,
        required=True,
        error_messages={
            'required': _('Operating hours per day is required.'),
            'min_value': _('Operating hours cannot be negative.'),
            'max_value': _('Operating hours cannot exceed 24 hours per day.')
        }
    )

    operating_days_per_week = forms.IntegerField(
        label=_("Operating Days per Week"),
        min_value=0,
        max_value=7,
        required=True,
        error_messages={
            'required': _('Operating days per week is required.'),
            'min_value': _('Operating days cannot be negative.'),
            'max_value': _('Operating days cannot exceed 7 days per week.')
        }
    )

    operating_weeks_per_year = forms.IntegerField(
        label=_("Operating Weeks per Year"),
        min_value=0,
        max_value=52,
        required=True,
        error_messages={
            'required': _('Operating weeks per year is required.'),
            'min_value': _('Operating weeks cannot be negative.'),
            'max_value': _('Operating weeks cannot exceed 52 weeks per year.')
        }
    )

    fuel_consumption = forms.DecimalField(
        label=_("Fuel Consumption"),
        min_value=0,
        decimal_places=2,
        required=True,
        error_messages={
            'required': _('Fuel consumption is required.'),
            'min_value': _('Fuel consumption cannot be negative.')
        }
    )

    power_input = forms.DecimalField(
        label=_("Power Input (kW)"),
        min_value=0,
        decimal_places=2,
        required=True,
        error_messages={
            'required': _('Power input is required.'),
            'min_value': _('Power input cannot be negative.')
        }
    )

    baseline_efficiency = forms.DecimalField(
        label=_("Baseline Efficiency"),
        min_value=0,
        decimal_places=3,
        required=True,
        error_messages={
            'required': _('Baseline efficiency is required.'),
            'min_value': _('Baseline efficiency cannot be negative.')
        }
    )

    equipment_efficiency_level = forms.DecimalField(
        label=_("Equipment Efficiency Level (%)"),
        min_value=0,
        max_value=100,
        decimal_places=2,
        required=True,
        error_messages={
            'required': _('Equipment efficiency level is required.'),
            'min_value': _('Equipment efficiency level cannot be negative.'),
            'max_value': _('Equipment efficiency level cannot exceed 100%.')
        }
    )

    heat_recovery_system = forms.BooleanField(
        label=_("Heat Recovery System"),
        required=False,
    )

    number_of_equipment = forms.IntegerField(
        label=_("Number of Equipment"),
        min_value=1,
        required=True,
        error_messages={
            'required': _('Number of equipment is required.'),
            'min_value': _('Number of equipment must be at least 1.')
        }
    )

    class Meta:
        model = HotWaterSystem
        fields = [
            'type_of_hot_water_system',
            'fuel_type',
            'operating_hours_per_day',
            'operating_days_per_week',
            'operating_weeks_per_year',
            'fuel_consumption',
            'power_input',
            'baseline_efficiency',
            'equipment_efficiency_level',
            'heat_recovery_system',
            'number_of_equipment',
            'energy_efficiency_label',
        ]

    def __init__(self, data=None, *args, **kwargs):
        # Map number_of_stars to energy_efficiency_label (like lighting system)
        if data is not None:
            data = data.copy()
            if 'number_of_stars' in data:
                data['energy_efficiency_label'] = data.pop('number_of_stars')
        super().__init__(data=data, *args, **kwargs)

    def clean_heat_recovery_system(self):
        """Convert 'yes'/'no' string values to boolean."""
        value = self.data.get('heat_recovery_system', '')

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower == 'yes':
                return True
            elif value_lower == 'no':
                return False

        return False