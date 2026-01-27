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
            'operation_hours_per_workday',
            'workdays_per_week',
            'workweeks_per_year',
            'light_bulb_power_rating_w',
            'baseline_lighting_power_density',
            'sensors_installed',
            'total_energy_consumption_kwh_per_year',
            'energy_efficiency_label',
        ]

    def __init__(self, data=None, *args, **kwargs):
        # Handle the field name mapping from frontend
        if data is not None:
            data = data.copy()

            # Map frontend field names to model field names
            field_mapping = {
                'lighting_type': 'lighting_bulb_type',
                'bulb_power_rating': 'light_bulb_power_rating_w',
                'operating_hours_per_day': 'operation_hours_per_workday',
                'operating_days_per_week': 'workdays_per_week',
                'operating_weeks_per_year': 'workweeks_per_year',
                'installation_of_sensors': 'sensors_installed',
                'baseline_lpd': 'baseline_lighting_power_density',
                'annual_energy_consumption': 'total_energy_consumption_kwh_per_year',
                'number_of_stars': 'energy_efficiency_label',
            }

            for frontend_name, model_name in field_mapping.items():
                if frontend_name in data:
                    data[model_name] = data.pop(frontend_name)

        super().__init__(data=data, *args, **kwargs)

    def clean_sensors_installed(self):
        """Convert 'yes'/'no' string values to boolean."""
        value = self.data.get('sensors_installed') or self.data.get('installation_of_sensors', '')

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower == 'yes':
                return True
            elif value_lower == 'no':
                return False

        # Default to False if not specified
        return False

    def clean_energy_efficiency_label(self):
        """Validate energy efficiency label (number of stars)."""
        # Check both possible field names
        value = self.data.get('energy_efficiency_label') or self.data.get('number_of_stars')

        if value is None or value == '':
            return None

        try:
            value = int(value)
            if value < 1 or value > 5:
                raise forms.ValidationError(_('Energy efficiency label must be between 1 and 5 stars.'))
            return value
        except (ValueError, TypeError):
            raise forms.ValidationError(_('Please enter a valid number for energy efficiency label.'))

    def clean_baseline_lighting_power_density(self):
        """Validate baseline lighting power density."""
        value = self.data.get('baseline_lighting_power_density') or self.data.get('baseline_lpd')

        if value is None or value == '':
            return None

        try:
            value = int(value)
            if value < 0:
                raise forms.ValidationError(_('Baseline lighting power density cannot be negative.'))
            return value
        except (ValueError, TypeError):
            raise forms.ValidationError(_('Please enter a valid number.'))

    def clean_total_energy_consumption_kwh_per_year(self):
        """Validate total energy consumption."""
        value = self.data.get('total_energy_consumption_kwh_per_year') or self.data.get('annual_energy_consumption')

        if value is None or value == '':
            return None

        try:
            value = int(value)
            if value < 0:
                raise forms.ValidationError(_('Total energy consumption cannot be negative.'))
            return value
        except (ValueError, TypeError):
            raise forms.ValidationError(_('Please enter a valid number.'))