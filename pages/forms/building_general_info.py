import datetime

from django import forms
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Layout, Fieldset, Row, Column, Submit

from cities_light.models import Country

from pages.models import Building, CategorySubcategory
from accounts.models import CustomCity, CustomRegion


class YearInput(forms.DateInput):
    input_type = "number"

    def __init__(self, attrs=None):
        years = range(1900, datetime.date.today().year + 1)
        attrs = attrs or {}
        attrs.update({"min": min(years), "max": max(years)})
        super().__init__(attrs)


class BuildingGeneralInformation(forms.ModelForm):
    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        widget=forms.Select(
            attrs={
                "id": "country-dropdown",
                "hx-get": "/select_lists/",  # HTMX request to the root URL
                "hx-trigger": "change",  # Trigger HTMX on change event
                "hx-target": "#region-dropdown",  # Update the City dropdown
                "class": "select form-select",
            }
        ),
        label="Country",
    )
    region = forms.ModelChoiceField(
        queryset=CustomRegion.objects.all(),
        widget=forms.Select(
            attrs={
                "id": "region-dropdown",
                "hx-get": "/select_lists/",  # HTMX request to the root URL
                "hx-trigger": "change",  # Trigger HTMX on change event
                "hx-target": "#city-dropdown",  # Update the City dropdown
                "class": "select form-select",
            }
        ),
        label="Region",
        required=False,
    )
    city = forms.ModelChoiceField(
        queryset=CustomCity.objects.none(),  # Start with an empty queryset
        widget=forms.Select(
            attrs={
                "id": "city-dropdown",
                "class": "select form-select",
            }
        ),
        label="City",
        help_text="Select a country first",
        required=False,
    )
    category = forms.ModelChoiceField(
        queryset=CategorySubcategory.objects.all(), label="Building Type"
    )
    construction_year = forms.IntegerField(widget=YearInput(), required=False)
    # forms.DateField(input_formats="%y-%m-%d", widget=forms.widgets.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = Building
        fields = [
            "name",
            "street",
            "zip",
            "number",
            "country",
            "region",
            "city",
            "category",
            "construction_year",
            "climate_zone",
            "reference_period",
            "total_floor_area",
        ]

        # labels = {
        #     "name": _("Writer"),
        # }
        # help_texts = {
        #     "city": _("Select a country first"),
        # }
        error_messages = {
            "name": {
                "max_length": _("This writer's name is too long."),
            },
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        super().__init__(*args, **kwargs)

        if instance:
            if instance.country:
                self.fields["region"].queryset = CustomRegion.objects.filter(
                    country=instance.country
                ).order_by("name")
                self.initial["country"] = instance.country
            else:
                self.fields["region"].queryset = CustomRegion.objects.none()

            if instance.region:
                self.fields["city"].queryset = CustomCity.objects.filter(
                    region=instance.region
                ).order_by("name")
                self.initial["region"] = instance.region
            else:
                self.fields["city"].queryset = CustomCity.objects.none()

            # Ensure the selected 'category' is prepopulated
            if instance.category:
                self.initial["category"] = instance.category

            # Ensure the selected 'city' is prepopulated
            if instance.city:
                self.initial["city"] = instance.city

        # Adjust 'city' queryset dynamically based on 'country' in the request data
        if "country" in self.data:
            try:
                country_id = int(self.data.get("country"))
                self.fields["region"].queryset = CustomRegion.objects.filter(
                    country_id=country_id
                ).order_by("name")
            except (ValueError, TypeError):
                self.fields["region"].queryset = CustomRegion.objects.none()
        if "region" in self.data:
            try:
                region_id = int(self.data.get("region"))
                self.fields["city"].queryset = CustomCity.objects.filter(
                    region_id=region_id
                ).order_by("name")
            except (ValueError, TypeError):
                self.fields["city"].queryset = CustomCity.objects.none()
        elif self.instance.pk:
            # If editing an existing instance, prepopulate the 'city' queryset
            self.fields["region"].queryset = CustomRegion.objects.filter(
                country=self.instance.country
            ).order_by("name")
            self.fields["city"].queryset = CustomCity.objects.filter(
                region=self.instance.region
            ).order_by("name")

        # Crispy Forms Layout
        self.helper = FormHelper()
        self.helper.layout = Layout(
            # Location Information Section
            Fieldset(
                "Location",
                # Name and Category in the first row
                Row(
                    Column("name", css_class="col-md-6"),
                    Column("country", css_class="col-md-3"),
                    Column("region", css_class="col-md-3"),
                ),
                # Country, ZIP and City in the second row
                Row(
                    Column("city", css_class="col-md-3"),
                    Column("zip", css_class="col-md-2"),
                    Column("street", css_class="col-md-5"),
                    Column("number", css_class="col-md-2"),
                ),
            ),
            HTML("<hr>"),  # Add a horizontal rule
            Fieldset(
                "Category",
                # Street and Number
                Row(
                    Column("category", css_class="col-md-4"),
                    Column("climate_zone", css_class="col-md-4"),
                    Column("reference_period", css_class="col-md-4"),
                ),
                # Street and Number in the last row with Postal code behind
                Row(
                    Column("total_floor_area", css_class="col-md-3"),
                    Column("construction_year", css_class="col-md-3"),
                ),
            ),
            Submit("submit", "Submit", css_class="btn btn-primary"),
        )
