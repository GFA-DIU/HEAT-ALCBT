import datetime

from django import forms
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit

from cities_light.models import Country, City

from pages.models import Building, CategorySubcategory


class YearInput(forms.DateInput):
    input_type = 'number'

    def __init__(self, attrs=None):
        years = range(1900, datetime.date.today().year + 1)
        attrs = attrs or {}
        attrs.update({'min': min(years), 'max': max(years)})
        super().__init__(attrs)


class BuildingGeneralInformation(forms.ModelForm):
    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        widget=forms.Select(attrs={
            'hx-get': '/select_lists/',               # HTMX request to the root URL
            'hx-trigger': 'change',      # Trigger HTMX on change event
            'hx-target': '#city-dropdown', # Update the City dropdown
            'class': 'select form-select',
        }),
        label="Country"
    )
    city = forms.ModelChoiceField(
        queryset=City.objects.none(),  # Start with an empty queryset
        widget=forms.Select(attrs={'id': 'city-dropdown', 'class': 'select form-select',}),
        label="City",
        help_text="Select a country first",
        required=False
    )
    category = forms.ModelChoiceField(queryset=CategorySubcategory.objects.all(), label="Building Type")
    construction_year = forms.DateField(widget=YearInput(), required=False)
    #forms.DateField(input_formats="%y-%m-%d", widget=forms.widgets.DateInput(attrs={'type': 'date'}))
    class Meta:
        model = Building
        fields = [
            "name",
            "street",
            "zip",
            "number",
            "city",
            "country",
            "category",
            "construction_year",
            "climate_zone",
            "total_floor_area",
            "cond_floor_area",
            "floors_above_ground",
            "floors_below_ground",
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
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        if instance:
            if instance.country:
                self.fields['city'].queryset = City.objects.filter(country=instance.country).order_by('name')
                self.initial['country'] = instance.country
            else: 
                self.fields['city'].queryset = City.objects.none()
            # Ensure the selected 'country' is prepopulated
            if instance.category:
                self.initial['category'] = instance.category

            # Ensure the selected 'city' is prepopulated
            if instance.city:
                self.initial['city'] = instance.city

        # Adjust 'city' queryset dynamically based on 'country' in the request data
        if "country" in self.data:
            try:
                country_id = int(self.data.get("country"))
                self.fields["city"].queryset = City.objects.filter(
                    country_id=country_id
                ).order_by("name")
            except (ValueError, TypeError):
                self.fields["city"].queryset = City.objects.none()
        elif self.instance.pk:
            # If editing an existing instance, prepopulate the 'city' queryset
            self.fields["city"].queryset = City.objects.filter(
                country=self.instance.country
            ).order_by("name")
        # Crispy Forms Layout
        self.helper = FormHelper()
        self.helper.layout = Layout(
            # Name and Category in the first row
            Row(
                Column('name', css_class='col-md-6'),
                Column('category', css_class='col-md-6'),
            ),
            # Country, ZIP and City in the second row
            Row(
                Column('country', css_class='col-md-6'),
                Column('construction_year', css_class='col-md-3'),
                Column('climate_zone', css_class='col-md-3'),
            ),
            # Street and Number
            Row(
                Column('city', css_class='col-md-3'),
                Column('zip', css_class='col-md-3'),
                Column('total_floor_area', css_class='col-md-3'),
                Column('cond_floor_area', css_class='col-md-3'),
            ),
            # Street and Number in the last row with Postal code behind
            Row(
                Column('street', css_class='col-md-4'),
                Column('number', css_class='col-md-2'),
                Column('floors_above_ground', css_class='col-md-3'),
                Column('floors_below_ground', css_class='col-md-3'),
            ),            
            Submit('submit', 'Submit', css_class='btn btn-primary'),
        )

    # def clean_city(self):
    #     city = self.cleaned_data.get('city')
    #     country = self.cleaned_data.get('country')
    #     if city and country and city.country != country:
    #         raise forms.ValidationError("The selected city is not valid for the chosen country.")
    #     return city

    # def clean_comment(self):
    #     name = self.cleaned_data.get('comment')

    #     # Trigger an error if the name is "admin"
    #     if name == "admin":
    #         raise ValidationError("The name 'admin' is not allowed.")

    #     return name

    # def clean(self):
    #     cleaned_data = super().clean()
    #     name = cleaned_data.get('name')
    #     comment = cleaned_data.get('comment')

    #     # Custom validation: check if 'name' and 'comment' are identical
    #     if name and comment and name == comment:
    #         raise ValidationError(
    #             "The name and comment cannot be the same.",
    #             code='invalid'
    #         )

    #     return cleaned_data
