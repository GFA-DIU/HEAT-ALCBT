"""
Forms for validating and saving Cooling System data (Chiller and Air Conditioner).
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from pages.models.building_operation import CoolingSystemChiller, CoolingSystemAirConditioner


class CoolingSystemChillerForm(forms.ModelForm):
    """
    Form for creating and updating Chiller Cooling Systems.
    Handles conversion of yes/no strings to boolean values and field name mapping.
    """

    class Meta:
        model = CoolingSystemChiller
        fields = [
            'chiller_type',
            'year_of_installation',
            'refrigerant_type',
            'refrigerant_quantity_kg',
            'variable_speed_drives',
            'heat_recovery_system',
            'total_cooling_load_rt',
            'baseline_leakage_factor_percent',
            'operation_hours_per_workday',
            'workdays_per_week',
            'workweeks_per_year',
            'baseline_cooling_efficiency_kw_h',
            'number_of_chillers',
            'total_chiller_system_power_input_kw',
            'water_cooled_chiller_cooling_load_factor_percent',
            'cop',
            'ip_lv',
            'energy_efficiency_label',
            'total_energy_consumption_kwh_per_year',
            'baseline_refrigerant_emission_factor',
        ]

    def __init__(self, data=None, *args, **kwargs):
        # Handle the field name mapping from frontend
        if data is not None:
            data = data.copy()

            # Map frontend field names to model field names
            field_mapping = {
                'chiller_system': 'chiller_type',
                'type_of_refrigerants': 'refrigerant_type',
                'refrigerant_quantity': 'refrigerant_quantity_kg',
                'installation_of_variable_speed_drives': 'variable_speed_drives',
                'installation_of_heat_recovery_systems': 'heat_recovery_system',
                'total_chiller_system': 'total_cooling_load_rt',
                'baseline_leakage_factor': 'baseline_leakage_factor_percent',
                'annual_operating_hours_per_day': 'operation_hours_per_workday',
                'annual_operating_days_per_week': 'workdays_per_week',
                'annual_operating_weeks_per_year': 'workweeks_per_year',
                'baseline_cooling_efficiency': 'baseline_cooling_efficiency_kw_h',
                'total_chiller_system_power_input': 'total_chiller_system_power_input_kw',
                'water_cooled_chiller_cooling_load_factor': 'water_cooled_chiller_cooling_load_factor_percent',
                'ipvl': 'ip_lv',
                'number_of_stars': 'energy_efficiency_label',
                'total_energy_consumption_of_chiller_system_annually': 'total_energy_consumption_kwh_per_year',
            }

            for frontend_name, model_name in field_mapping.items():
                if frontend_name in data:
                    data[model_name] = data.pop(frontend_name)

            # Convert chiller system types
            if 'chiller_type' in data:
                type_mapping = {
                    'water-cooled': 'water_cooled',
                    'air-cooled': 'air_cooled',
                }
                if data['chiller_type'] in type_mapping:
                    data['chiller_type'] = type_mapping[data['chiller_type']]

        super().__init__(data=data, *args, **kwargs)

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

        # Default to False if not specified
        return False

    def clean_energy_efficiency_label(self):
        """Validate energy efficiency label (number of stars)."""
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


class CoolingSystemAirConditionerForm(forms.ModelForm):
    """
    Form for creating and updating Air Conditioner Cooling Systems.
    Handles field name mapping.
    """

    class Meta:
        model = CoolingSystemAirConditioner
        fields = [
            'ac_type',
            'year_of_installation',
            'operation_hours_per_workday',
            'workdays_per_week',
            'workweeks_per_year',
            'refrigerant_type',
            'refrigerant_quantity_kg',
            'total_cooling_load_rt',
            'baseline_efficiency_kw_per_rt',
            'baseline_refrigerant_emission_factor',
            'baseline_leakage_factor_percent',
            'total_energy_consumption_kwh_per_year',
            'number_of_units',
            'total_system_power_kw',
            'cop',
            'iseer_rating',
            'energy_efficiency_label',
        ]

    def __init__(self, data=None, *args, **kwargs):
        # Handle the field name mapping from frontend
        if data is not None:
            data = data.copy()

            # Map frontend field names to model field names
            field_mapping = {
                'type_of_air_condition': 'ac_type',
                'hours_per_day': 'operation_hours_per_workday',
                'days_per_week': 'workdays_per_week',
                'weeks_per_year': 'workweeks_per_year',
                'type_of_refrigerants': 'refrigerant_type',
                'refrigerant_quantity': 'refrigerant_quantity_kg',
                'total_cooling_load_for_split_vrv': 'total_cooling_load_rt',
                'baseline_split_unit_system_efficiency': 'baseline_efficiency_kw_per_rt',
                'baseline_leakage_factor': 'baseline_leakage_factor_percent',
                'total_energy_consumption_of_split_vrv_annually': 'total_energy_consumption_kwh_per_year',
                'number_of_split_vrv_units': 'number_of_units',
                'total_split_unit_system_power': 'total_system_power_kw',
                'iseer': 'iseer_rating',
                'number_of_stars': 'energy_efficiency_label',
            }

            for frontend_name, model_name in field_mapping.items():
                if frontend_name in data:
                    data[model_name] = data.pop(frontend_name)

        super().__init__(data=data, *args, **kwargs)

    def clean_energy_efficiency_label(self):
        """Validate energy efficiency label (number of stars)."""
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