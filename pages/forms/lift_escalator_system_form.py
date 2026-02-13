"""
Form for validating and saving Lift & Escalator System data.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from pages.models.building_operation import LiftEscalatorSystem


class LiftEscalatorSystemForm(forms.ModelForm):

    class Meta:
        model = LiftEscalatorSystem
        fields = [
            'number_of_lifts',
            'lift_regenerative_features',
            'vvvf_sleep_mode',
            'annual_energy_consumption_kwh',
        ]

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            if 'annual_energy_consumption' in data:
                data['annual_energy_consumption_kwh'] = data.pop('annual_energy_consumption')
        super().__init__(data=data, *args, **kwargs)

    def clean_lift_regenerative_features(self):
        value = self.data.get('lift_regenerative_features', '')
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() == 'yes':
                return True
            elif value.lower() == 'no':
                return False
        return False

    def clean_vvvf_sleep_mode(self):
        value = self.data.get('vvvf_sleep_mode', '')
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() == 'yes':
                return True
            elif value.lower() == 'no':
                return False
        return False

    def clean_annual_energy_consumption_kwh(self):
        value = self.cleaned_data.get('annual_energy_consumption_kwh')
        if value is None or value == '':
            return None
        try:
            value = int(value)
            if value < 0:
                raise forms.ValidationError(_('Annual energy consumption cannot be negative.'))
            return value
        except (ValueError, TypeError):
            raise forms.ValidationError(_('Please enter a valid number.'))