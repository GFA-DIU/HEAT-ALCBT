"""
Form for validating and saving Lighting System data.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from pages.models.building_operation import LightingSystem


class LightingSystemForm(forms.ModelForm):
    """
    Form for creating and updating Lighting Systems.
    Handles conversion of yes/no strings to boolean values and field name mapping.
    """

    class Meta:
        model = LightingSystem
        fields = [
            'room_type',
            'area_of_room',
            'lighting_bulb_type',
            'number_of_bulbs',
            'tubes_per_fixture',
            'light_bulb_power_rating_w',
            'total_lighting_power_kw',
            'baseline_lighting_power_density',
            'operation_hours_per_workday',
            'workdays_per_week',
            'workweeks_per_year',
            'sensors_installed',
            'total_energy_consumption_kwh_per_year',
            'energy_efficiency_label',
            'number_of_stars',
        ]

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()

            field_mapping = {
                'lighting_type': 'lighting_bulb_type',
                'number_of_fixtures': 'number_of_bulbs',
                'bulb_power_rating': 'light_bulb_power_rating_w',
                'total_lighting_power': 'total_lighting_power_kw',
                'baseline_lpd': 'baseline_lighting_power_density',
                'operating_hours_per_day': 'operation_hours_per_workday',
                'operating_days_per_week': 'workdays_per_week',
                'operating_weeks_per_year': 'workweeks_per_year',
                'installation_of_sensors': 'sensors_installed',
                'annual_energy_consumption': 'total_energy_consumption_kwh_per_year',
            }

            for frontend_name, model_name in field_mapping.items():
                if frontend_name in data:
                    data[model_name] = data.pop(frontend_name)

        super().__init__(data=data, *args, **kwargs)

    def clean_sensors_installed(self):
        value = self.data.get('sensors_installed') or self.data.get('installation_of_sensors', '')

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower == 'yes':
                return True
            elif value_lower == 'no':
                return False

        return False

    def clean_number_of_stars(self):
        value = self.cleaned_data.get('number_of_stars')
        if value is None or value == '':
            return None
        try:
            value = int(value)
            if value < 1 or value > 5:
                raise forms.ValidationError(_('Number of stars must be between 1 and 5.'))
            return value
        except (ValueError, TypeError):
            raise forms.ValidationError(_('Please enter a valid number for stars.'))

    def clean_total_lighting_power_kw(self):
        value = self.cleaned_data.get('total_lighting_power_kw')
        if value is None or value == '':
            return None
        try:
            from decimal import Decimal
            value = Decimal(str(value))
            if value < 0:
                raise forms.ValidationError(_('Total lighting power cannot be negative.'))
            return value
        except Exception:
            raise forms.ValidationError(_('Please enter a valid number.'))

    def clean_baseline_lighting_power_density(self):
        value = self.cleaned_data.get('baseline_lighting_power_density')
        if value is None or value == '':
            return None
        try:
            from decimal import Decimal
            value = Decimal(str(value))
            if value < 0:
                raise forms.ValidationError(_('Baseline lighting power density cannot be negative.'))
            return value
        except Exception:
            raise forms.ValidationError(_('Please enter a valid number.'))

    def clean_total_energy_consumption_kwh_per_year(self):
        value = self.cleaned_data.get('total_energy_consumption_kwh_per_year')
        if value is None or value == '':
            return None
        try:
            value = int(value)
            if value < 0:
                raise forms.ValidationError(_('Total energy consumption cannot be negative.'))
            return value
        except (ValueError, TypeError):
            raise forms.ValidationError(_('Please enter a valid number.'))