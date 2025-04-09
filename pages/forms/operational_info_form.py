from django import forms
from django.utils.translation import gettext as _
from django.core.validators import MinValueValidator, MaxValueValidator

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Layout, Fieldset, Row, Column, Submit, Field


from pages.models import Building


class OperationalInfoForm(forms.ModelForm):

    class Meta:
        model = Building
        fields = [
            "num_residents",
            "weeks_per_year",
            "hours_per_workday",
            "heating_temp",
            "heating_temp_unit",
            "workdays_per_week",
            "cooling_temp",
            "cooling_temp_unit",
            "heating_type",
            "heating_capacity",
            "heating_unit",
            "cooling_type",
            "cooling_capacity",
            "cooling_unit",
            "ventilation_type",
            "ventilation_capacity",
            "ventilation_unit",
            "lighting_type",
            "lighting_capacity",
            "lighting_unit",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["num_residents"].validators.extend([MinValueValidator(0)])
        self.fields["hours_per_workday"].validators.extend(
            [MinValueValidator(0), MaxValueValidator(24)]
        )
        self.fields["workdays_per_week"].validators.extend(
            [MinValueValidator(0), MaxValueValidator(7)]
        )
        self.fields["weeks_per_year"].validators.extend(
            [MinValueValidator(0), MaxValueValidator(52)]
        )
        self.fields["heating_temp"].validators.extend(
            [MinValueValidator(0), MaxValueValidator(120)]
        )
        self.fields["cooling_temp"].validators.extend(
            [MinValueValidator(0), MaxValueValidator(120)]
        )
        self.fields["heating_capacity"].validators.extend([MinValueValidator(0)])
        self.fields["cooling_capacity"].validators.extend([MinValueValidator(0)])
        self.fields["ventilation_capacity"].validators.extend([MinValueValidator(0)])
        self.fields["lighting_capacity"].validators.extend([MinValueValidator(0)])
        # Crispy Forms Layout
        self.helper = FormHelper()
        self.helper.layout = Layout(
            # Location Information Section
            Fieldset(
                "Location",
                # Name and Category in the first row
                Row(
                    Column("num_residents", css_class="col-md-6"),
                    Column(Field("weeks_per_year"), css_class="col-md-6"),
                ),
                # Country, ZIP and City in the second row
                Row(
                    Column(Field("hours_per_workday"), css_class="col-md-6"),
                    Column(Field("heating_temp"), css_class="col-md-4"),
                    Column(Field("heating_temp_unit"), css_class="col-md-2"),
                ),
                # Country, ZIP and City in the second row
                Row(
                    Column("workdays_per_week", css_class="col-md-6"),
                    Column(Field("cooling_temp"), css_class="col-md-4"),
                    Column(Field("cooling_temp_unit"), css_class="col-md-2"),
                ),
            ),
            HTML("<hr>"),  # Add a horizontal rule
            Fieldset(
                "Category",
                # Street and Number
                Row(
                    Column(Field("heating_type"), css_class="col-md-6"),
                    Column(Field("heating_capacity"), css_class="col-md-4"),
                    Column(Field("heating_unit"), css_class="col-md-2"),
                ),
                # Street and Number
                Row(
                    Column(Field("cooling_type"), css_class="col-md-6"),
                    Column(Field("cooling_capacity"), css_class="col-md-4"),
                    Column(Field("cooling_unit"), css_class="col-md-2"),
                ),
                # Street and Number
                Row(
                    Column(Field("ventilation_type"), css_class="col-md-6"),
                    Column(Field("ventilation_capacity"), css_class="col-md-4"),
                    Column(Field("ventilation_unit"), css_class="col-md-2"),
                ),
                # Street and Number
                Row(
                    Column(Field("lighting_type"), css_class="col-md-6"),
                    Column(Field("lighting_capacity"), css_class="col-md-4"),
                    Column(Field("lighting_unit"), css_class="col-md-2"),
                ),
            ),
            # Update building_simulation.py line 44 if this changes
            Submit("submit", "Submit", css_class="btn btn-primary"),
        )
