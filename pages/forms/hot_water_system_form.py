from django import forms
from django.utils.translation import gettext as _

from pages.models.building_operation import HotWaterSystem, HotWaterSystemType, FuelType
from decimal import Decimal, InvalidOperation


class HotWaterSystemForm(forms.ModelForm):
    """
    Form for validating Hot Water System data.
    Handles validation for creating and updating HWS records.
    """

    class Meta:
        model = HotWaterSystem
        fields = [
            'type_of_hot_water_system',
            'fuel_type',
            'number_of_equipment',
            'operating_hours_per_day',
            'operating_days_per_week',
            'operating_weeks_per_year',
            'baseline_efficiency',
            'heat_recovery_system',
            'equipment_efficiency_level',
            'power_input',
            'total_energy_consumption_kwh_per_year',
            'total_fuel_consumption',
            'fuel_consumption_unit',
        ]

    def __init__(self, data=None, *args, **kwargs):
        super().__init__(data=data, *args, **kwargs)

    def clean_heat_recovery_system(self):
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

    def clean_power_input(self):
        value = self.cleaned_data.get('power_input')
        if value is None or value == '':
            return None
        try:
            value = Decimal(str(value))
            if value < 0:
                raise forms.ValidationError(_('Power input cannot be negative.'))
            return value
        except Exception:
            raise forms.ValidationError(_('Please enter a valid number.'))

    def clean_total_energy_consumption_kwh_per_year(self):
        value = self.cleaned_data.get('total_energy_consumption_kwh_per_year')
        if value is None or value == '':
            return None
        try:
            value = Decimal(str(value))
            if value < 0:
                raise forms.ValidationError(_('Total energy consumption cannot be negative.'))
            return value
        except (InvalidOperation, ValueError, TypeError):
            raise forms.ValidationError(_('Please enter a valid number.'))

    def clean_total_fuel_consumption(self):
        value = self.cleaned_data.get('total_fuel_consumption')
        if value is None or value == '':
            return None
        try:

            val = Decimal(str(value))
            if val < 0:
                raise forms.ValidationError(_('Total fuel consumption cannot be negative.'))
            return val
        except forms.ValidationError:
            raise
        except Exception:
            raise forms.ValidationError(_('Please enter a valid number.'))

    def clean_fuel_consumption_unit(self):
        value = self.cleaned_data.get('fuel_consumption_unit')
        if value is None or value == '':
            return None
        return str(value).strip()