from django import forms
from django.utils.translation import gettext as _
from django.core.validators import MinValueValidator, MaxValueValidator

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Layout, Fieldset, Row, Column, Submit, Field


from pages.models.building import Building, HeatingType, CoolingType, VentilationType, LightingType
from pages.models.epd import Unit


class OperationalInfoForm(forms.ModelForm):

    num_residents = forms.IntegerField(
        label="# residents",
        help_text="Apprximation",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    hours_per_workday = forms.IntegerField(
        label="Operation hours per workday",
        help_text="hours per workday",
        min_value=0,
        max_value=24,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    workdays_per_week = forms.IntegerField(
        label="Operation days per week",
        help_text="days per week",
        min_value=0,
        max_value=7,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    weeks_per_year = forms.IntegerField(
        label="Operation weeks per year",
        help_text="weeks per year",
        min_value=0,
        max_value=52,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    heating_temp = forms.DecimalField(
        label="Typical Heating Temperature",
        min_value=0,
        max_value=120,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    heating_temp_unit = forms.ChoiceField(
        label="Heating Temperature Unit",
        choices=[c for c in Unit.choices if c[0] in (Unit.CELSIUS, Unit.FAHRENHEIT)],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    cooling_temp = forms.DecimalField(
        label="Typical Cooling Temperature",
        min_value=0,
        max_value=120,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    cooling_temp_unit = forms.ChoiceField(
        label="Cooling Temperature Unit",
        choices=[c for c in Unit.choices if c[0] in (Unit.CELSIUS, Unit.FAHRENHEIT)],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    heating_type = forms.ChoiceField(
        label="Heating Type",
        choices=[('', '---------')] + HeatingType.choices,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    heating_capacity = forms.DecimalField(
        label="Heating Capacity",
        min_value=0,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    heating_unit = forms.ChoiceField(
        label="Heating Unit",
        choices=[c for c in Unit.choices if c[0] in (Unit.KW,)],
        required=False,
        initial="",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    cooling_type = forms.ChoiceField(
        label="Coolingting Type",
        choices=[('', '---------')]+CoolingType.choices,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    cooling_capacity = forms.DecimalField(
        label="Cooling Capacity",
        min_value=0,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    cooling_unit = forms.ChoiceField(
        label="Cooling Unit",
        choices=[c for c in Unit.choices if c[0] in (Unit.KW, Unit.TR)],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    ventilation_type = forms.ChoiceField(
        label="Ventilation Type",
        choices=[('', '---------')]+VentilationType.choices,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    ventilation_capacity = forms.DecimalField(
        label="Ventilation Capacity",
        min_value=0,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    ventilation_unit = forms.ChoiceField(
        label="Ventilation Unit",
        choices=[c for c in Unit.choices if c[0] in (Unit.M3_H, Unit.CFM)],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    lighting_type = forms.ChoiceField(
        label="Lighting Type",
        choices=[('', '---------')]+LightingType.choices,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    lighting_capacity = forms.DecimalField(
        label="Lighting Capacity",
        min_value=0,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    lighting_unit = forms.ChoiceField(
        label="Lighting Unit",
        choices=[c for c in Unit.choices if c[0] in (Unit.KW,)],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Building
        fields = []