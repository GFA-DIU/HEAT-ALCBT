from django import forms
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit

from cities_light.models import Country, City

from pages.models import Building, CategorySubcategory


class BuildingGeneralInformation(forms.ModelForm):
    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        widget=forms.Select(attrs={
            'hx-get': '/building/_new',               # HTMX request to the root URL
            'hx-trigger': 'change',      # Trigger HTMX on change event
            'hx-target': '#city-dropdown', # Update the City dropdown
            'hx-vals': '{"id": this.value}', # Dynamically include the dropdown value
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
    class Meta:
        model = Building
        fields = [
            "name",
            "street",
            "zip",
            "number",
            "city",
            "country",
            "category"]

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
            self.fields["country"] = forms.ModelChoiceField(
                queryset=Country.objects.all(),
                widget=forms.Select(
                    attrs={
                        "hx-get": "/building/"
                        + str(instance.pk),  # HTMX request to the root URL
                        "hx-trigger": "change",  # Trigger HTMX on change event
                        "hx-target": "#city-dropdown",  # Update the City dropdown
                        "class": "select form-select",
                    }
                ),
                label="Country",
            )
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

        if 'city' in self.data:
            self.instance.city = get_object_or_404(City, id=int(self.data['city']))
        # Crispy Forms Layout
        self.helper = FormHelper()
        self.helper.layout = Layout(
            # Name and Category in the first row
            Row(
                Column('name', css_class='col-md-6'),
                Column('category', css_class='col-md-6'),
            ),
            # Country and City in the second row
            Row(
                Column('country', css_class='col-md-6'),
                Column('city', css_class='col-md-6'),
            ),
            # Zip code in its own row
            Row(
                Column('zip', css_class='col-md-12'),
            ),
            # Street and Number in the last row
            Row(
                Column('street', css_class='col-md-9'),
                Column('number', css_class='col-md-3'),
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
