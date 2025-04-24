from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomRegion, CustomUser, UserProfile

from cities_light.models import Country

from accounts.models import CustomCity


class CustomUserCreationForm(UserCreationForm):

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "email",
            "username",
        )


class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "username",
        )


class CustomUserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [
            'email',
            'username',
        ] 

class UserProfileUpdateForm(forms.ModelForm):
    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        widget=forms.Select(attrs={
            'hx-get': '/select_lists/',               # HTMX request to the root URL
            'hx-trigger': 'change',      # Trigger HTMX on change event
            'hx-target': '#region-dropdown', # Update the Region dropdown
            'class': 'select form-select',
        }),
        label="Country"
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
        widget=forms.Select(attrs={'id': 'city-dropdown', 'class': 'select form-select',}),
        label="City",
        help_text="Select a country first",
        required=False
    )
    
    class Meta:
        model = UserProfile
        fields = ['country', 'region', 'city', "consent_flag"]
        
        
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