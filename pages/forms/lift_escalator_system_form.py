"""
Form for validating and saving Lift & Escalator System data.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from pages.models.building_operation import LiftEscalatorSystem


class LiftEscalatorSystemForm(forms.ModelForm):
    """
    Form for creating and updating Lift & Escalator Systems.
    Handles conversion of yes/no strings to boolean values.
    """

    class Meta:
        model = LiftEscalatorSystem
        fields = [
            'number_of_lifts',
            'lift_regenerative_features',
            'vvvf_sleep_mode',
            'annual_energy_consumption_kwh',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Handle the field name mapping from frontend
        if isinstance(args[0] if args else None, dict):
            data = args[0].copy() if args else {}
            # Map frontend field name to model field name
            if 'annual_energy_consumption' in data:
                data['annual_energy_consumption_kwh'] = data.pop('annual_energy_consumption')
            args = (data,) + args[1:]

        self.args = args
        self.kwargs = kwargs

    def clean_lift_regenerative_features(self):
        """Convert 'yes'/'no' string values to boolean."""
        value = self.data.get('lift_regenerative_features', '')

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

    def clean_vvvf_sleep_mode(self):
        """Convert 'yes'/'no' string values to boolean."""
        value = self.data.get('vvvf_sleep_mode', '')

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

    def clean_annual_energy_consumption_kwh(self):
        """Validate annual energy consumption."""
        # Check both possible field names
        value = self.data.get('annual_energy_consumption_kwh') or self.data.get('annual_energy_consumption')

        if value is None or value == '':
            return None

        try:
            value = int(value)
            if value < 0:
                raise forms.ValidationError(_('Annual energy consumption cannot be negative.'))
            return value
        except (ValueError, TypeError):
            raise forms.ValidationError(_('Please enter a valid number.'))