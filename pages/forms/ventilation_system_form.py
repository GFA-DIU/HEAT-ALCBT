"""
Form for validating and saving Ventilation System data.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from pages.models.building_operation import VentilationSystem


class VentilationSystemForm(forms.ModelForm):
    """
    Form for creating and updating Ventilation Systems.
    Handles conversion of yes/no strings to boolean values and field name mapping.
    """

    class Meta:
        model = VentilationSystem
        fields = [
            'ventilation_type',
            'ventilation_capacity',
            'baseline_efficiency_w_cmh',
            'operation_hours_per_workday',
            'workdays_per_week',
            'workweeks_per_year',
            'total_power_input_w',
            'air_flow_rate',
            'demand_controlled_ventilation',
            'variable_speed_drives',
            'number_of_units_installed',
            'total_energy_consumption_kwh_per_year',
            'energy_efficiency_label',
        ]

    def __init__(self, data=None, *args, **kwargs):
        # Handle the field name mapping from frontend
        if data is not None:
            data = data.copy()

            # Map frontend field names to model field names
            field_mapping = {
                'baseline_efficiency': 'baseline_efficiency_w_cmh',
                'operating_hours_per_day': 'operation_hours_per_workday',
                'operating_days_per_week': 'workdays_per_week',
                'operating_weeks_per_year': 'workweeks_per_year',
                'power_input': 'total_power_input_w',
                'airflow_rate': 'air_flow_rate',
                'number_of_units': 'number_of_units_installed',
                'annual_energy_consumption': 'total_energy_consumption_kwh_per_year',
                'number_of_stars': 'energy_efficiency_label',
            }

            for frontend_name, model_name in field_mapping.items():
                if frontend_name in data:
                    data[model_name] = data.pop(frontend_name)

        super().__init__(data=data, *args, **kwargs)

    def clean_demand_controlled_ventilation(self):
        """Convert 'yes'/'no' string values to boolean."""
        value = self.data.get('demand_controlled_ventilation', '')

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

    def clean_variable_speed_drives(self):
        """Convert 'yes'/'no' string values to boolean."""
        value = self.data.get('variable_speed_drives', '')

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