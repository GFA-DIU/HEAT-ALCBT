"""
Forms for validating and saving Cooling System data (Chiller and Air Conditioner).
"""
from decimal import Decimal, InvalidOperation
from django import forms
from django.utils.translation import gettext_lazy as _

from pages.models.building_operation import CoolingSystemChiller, CoolingSystemAirConditioner

# Acceptable baseline cooling efficiency ranges per system type (kW/RT)
EFFICIENCY_RANGES = {
    'water_cooled': (Decimal('0.40'), Decimal('1.00')),
    'air_cooled':   (Decimal('0.60'), Decimal('1.50')),
}

AC_EFFICIENCY_RANGES = {
    'window':   (Decimal('0.85'), Decimal('2.00')),
    'split':    (Decimal('0.75'), Decimal('1.80')),
    'vrv':      (Decimal('0.65'), Decimal('1.40')),
    'packaged': (Decimal('0.75'), Decimal('1.70')),
}

# Cooling capacity unit conversion to kW
# 1 Ton = 3.516 kW, 1 BTU/hr = 3.516/12000 kW
CAPACITY_CONVERSION = {
    'ton':    Decimal('3.516'),
    'btu_hr': Decimal('3.516') / Decimal('12000'),
    'kw':     Decimal('1'),
}


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
            'number_of_stars',
            'total_energy_consumption_kwh_per_year',
            'baseline_refrigerant_emission_factor',
        ]

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()

            field_mapping = {
                'chiller_system': 'chiller_type',
                'type_of_refrigerants': 'refrigerant_type',
                'refrigerant_quantity': 'refrigerant_quantity_kg',
                'installation_of_variable_speed_drives': 'variable_speed_drives',
                'installation_of_heat_recovery_systems': 'heat_recovery_system',
                'baseline_leakage_factor': 'baseline_leakage_factor_percent',
                'annual_operating_hours_per_day': 'operation_hours_per_workday',
                'annual_operating_days_per_week': 'workdays_per_week',
                'annual_operating_weeks_per_year': 'workweeks_per_year',
                'baseline_cooling_efficiency': 'baseline_cooling_efficiency_kw_h',
                'total_cooling_load': 'total_cooling_load_rt',
                'total_chiller_system_power_input': 'total_chiller_system_power_input_kw',
                'water_cooled_chiller_cooling_load_factor': 'water_cooled_chiller_cooling_load_factor_percent',
                'ipvl': 'ip_lv',
                'total_energy_consumption_of_chiller_system_annually': 'total_energy_consumption_kwh_per_year',
            }

            for frontend_name, model_name in field_mapping.items():
                if frontend_name in data:
                    data[model_name] = data.pop(frontend_name)

            # Normalise chiller sub-type value
            if 'chiller_type' in data:
                type_mapping = {
                    'water-cooled': 'water_cooled',
                    'air-cooled': 'air_cooled',
                }
                if data['chiller_type'] in type_mapping:
                    data['chiller_type'] = type_mapping[data['chiller_type']]

        super().__init__(data=data, *args, **kwargs)

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

    def clean_heat_recovery_system(self):
        value = self.data.get('heat_recovery_system', '')
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() == 'yes':
                return True
            elif value.lower() == 'no':
                return False
        return False

    def clean_baseline_cooling_efficiency_kw_h(self):
        value = self.cleaned_data.get('baseline_cooling_efficiency_kw_h')
        if value is None:
            return value
        chiller_type = self.data.get('chiller_type', '')
        # Normalise in case the raw value hasn't been mapped yet
        if chiller_type == 'water-cooled':
            chiller_type = 'water_cooled'
        elif chiller_type == 'air-cooled':
            chiller_type = 'air_cooled'
        range_ = EFFICIENCY_RANGES.get(chiller_type)
        if range_:
            min_val, max_val = range_
            if value < min_val or value > max_val:
                raise forms.ValidationError(
                    _(f'Baseline cooling efficiency must be between {min_val} and {max_val} kW/RT for this chiller type.')
                )
        return value

    def clean_energy_efficiency_label(self):
        value = self.cleaned_data.get('energy_efficiency_label')
        if not value:
            return None
        if value.upper() not in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
            raise forms.ValidationError(_('Energy efficiency label must be A, B, C, D, E, F or G.'))
        return value.upper()

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


class CoolingSystemAirConditionerForm(forms.ModelForm):
    """
    Form for creating and updating Air Conditioner Cooling Systems.
    Handles field name mapping for window, split, VRV and packaged AC types.
    For AC types (window/split/vrf/packaged), cooling_capacity_per_unit_kw is
    populated from the frontend 'cooling_capacity_per_unit' + 'cooling_capacity_unit'
    fields, converting Tons or BTU/hr to kW server-side.
    """

    class Meta:
        model = CoolingSystemAirConditioner
        fields = [
            'ac_type',
            'packaged_subtype',
            'year_of_installation',
            'operation_hours_per_workday',
            'workdays_per_week',
            'workweeks_per_year',
            'refrigerant_type',
            'refrigerant_quantity_kg',
            'total_cooling_load_rt',
            'cooling_capacity_per_unit_kw',
            'baseline_efficiency_kw_per_rt',
            'baseline_refrigerant_emission_factor',
            'baseline_leakage_factor_percent',
            'total_energy_consumption_kwh_per_year',
            'number_of_units',
            'total_system_power_kw',
            'power_input_per_unit_kw',
            'cop',
            'iseer_rating',
            'eer_iseer_cop',
            'energy_efficiency_label',
            'number_of_stars',
        ]

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()

            field_mapping = {
                'type_of_air_condition': 'ac_type',
                'hours_per_day': 'operation_hours_per_workday',
                'days_per_week': 'workdays_per_week',
                'weeks_per_year': 'workweeks_per_year',
                'type_of_refrigerants': 'refrigerant_type',
                'refrigerant_quantity': 'refrigerant_quantity_kg',
                'total_cooling_load': 'total_cooling_load_rt',
                'baseline_cooling_efficiency': 'baseline_efficiency_kw_per_rt',
                'baseline_leakage_factor': 'baseline_leakage_factor_percent',
                'total_energy_consumption_annually': 'total_energy_consumption_kwh_per_year',
                'number_of_units': 'number_of_units',
                'total_system_power': 'total_system_power_kw',
                'power_input_per_unit': 'power_input_per_unit_kw',
                'iseer': 'iseer_rating',
                'eer_iseer_cop': 'eer_iseer_cop',
            }

            for frontend_name, model_name in field_mapping.items():
                if frontend_name in data:
                    data[model_name] = data.pop(frontend_name)

            # Convert cooling capacity to kW if provided with a unit
            raw_capacity = data.get('cooling_capacity_per_unit')
            capacity_unit = data.get('cooling_capacity_unit', 'kw').lower()
            if raw_capacity:
                try:
                    value = Decimal(str(raw_capacity))
                    factor = CAPACITY_CONVERSION.get(capacity_unit, Decimal('1'))
                    data['cooling_capacity_per_unit_kw'] = str((value * factor).quantize(Decimal('0.001')))
                except InvalidOperation:
                    pass  # validation will catch the bad value

        super().__init__(data=data, *args, **kwargs)

    def clean_eer_iseer_cop(self):
        value = self.cleaned_data.get('eer_iseer_cop')
        if value is not None and value <= 0:
            raise forms.ValidationError(_('EER / ISEER / COP must be greater than zero.'))
        return value

    def clean_baseline_efficiency_kw_per_rt(self):
        value = self.cleaned_data.get('baseline_efficiency_kw_per_rt')
        if value is None:
            return value
        ac_type = self.data.get('ac_type', '')
        range_ = AC_EFFICIENCY_RANGES.get(ac_type)
        if range_:
            min_val, max_val = range_
            if value < min_val or value > max_val:
                raise forms.ValidationError(
                    _(f'Baseline cooling efficiency must be between {min_val} and {max_val} kW/RT for this system type.')
                )
        return value

    def clean_energy_efficiency_label(self):
        value = self.cleaned_data.get('energy_efficiency_label')
        if not value:
            return None
        if value.upper() not in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
            raise forms.ValidationError(_('Energy efficiency label must be A, B, C, D, E, F or G.'))
        return value.upper()

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