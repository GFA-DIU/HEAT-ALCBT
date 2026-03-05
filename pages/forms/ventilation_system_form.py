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
            'total_power_input_kw',
            'air_flow_rate',
            'demand_controlled_ventilation',
            'variable_speed_drives',
            'number_of_units_installed',
            'total_energy_consumption_kwh_per_year',
            'fresh_air_ratio_percent',
            'number_of_stars',
        ]

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()

            field_mapping = {
                'baseline_efficiency': 'baseline_efficiency_w_cmh',
                'operating_hours_per_day': 'operation_hours_per_workday',
                'operating_days_per_week': 'workdays_per_week',
                'operating_weeks_per_year': 'workweeks_per_year',
                'power_input': 'total_power_input_kw',
                'airflow_rate': 'air_flow_rate',
                'number_of_units': 'number_of_units_installed',
                'annual_energy_consumption': 'total_energy_consumption_kwh_per_year',
                'fresh_air_ratio': 'fresh_air_ratio_percent',
            }

            for frontend_name, model_name in field_mapping.items():
                if frontend_name in data:
                    data[model_name] = data.pop(frontend_name)

        super().__init__(data=data, *args, **kwargs)

    def clean_demand_controlled_ventilation(self):
        value = self.data.get('demand_controlled_ventilation', '')
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() == 'yes':
                return True
            elif value.lower() == 'no':
                return False
        return False

    def clean_variable_speed_drives(self):
        value = self.data.get('variable_speed_drives', '')
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() == 'yes':
                return True
            elif value.lower() == 'no':
                return False
        return False

    def clean_number_of_stars(self):
        value = self.cleaned_data.get('number_of_stars')
        if value is None:
            return None
        try:
            value = int(value)
            if value < 1 or value > 5:
                raise forms.ValidationError(_('Number of stars must be between 1 and 5.'))
            return value
        except (ValueError, TypeError):
            raise forms.ValidationError(_('Please enter a valid number for stars.'))