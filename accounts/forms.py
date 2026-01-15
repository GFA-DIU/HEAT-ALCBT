from cities_light.models import Country
from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from accounts.models import CustomCity
from pages.models.base import ALCBTCountryManager

from .models import CustomRegion, CustomUser, UserProfile


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
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full validator',
                'placeholder': 'Username',
                'maxlength': '150',
                'required': True,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full validator',
                'placeholder': 'Email',
                'required': True,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the email field shows the decrypted value
        if self.instance and self.instance.pk:
            # Access the email property which should return the decrypted value
            self.initial['email'] = str(self.instance.email) 
class UserProfileUpdateForm(forms.ModelForm):
    country = forms.ModelChoiceField(
        queryset=ALCBTCountryManager.get_all_countries(),
        widget=forms.Select(attrs={
            'class': 'select select-with-icon w-full validator',
            'hx-get': '/select_lists/',               # HTMX request to the root URL
            'hx-trigger': 'change',      # Trigger HTMX on change event
            'hx-target': '#region-dropdown', # Update the Region dropdown
            'required': 'true',
        }),
        label="Country",
        required=False
    )
    region = forms.ModelChoiceField(
        queryset=CustomRegion.objects.all(),
        widget=forms.Select(attrs={
            "id": "region-dropdown",
            "hx-get": "/select_lists/",  # HTMX request to the root URL
            "hx-trigger": "change",  # Trigger HTMX on change event
            "hx-target": "#city-dropdown",  # Update the City dropdown
            "class": "select select-with-icon w-full validator",
            "required": True,
        }),
        label="Region",
        required=False,
    )
    city = forms.ModelChoiceField(
        queryset=CustomCity.objects.none(),  # Start with an empty queryset
        widget=forms.Select(attrs={
            'id': 'city-dropdown',
            'class': 'select select-with-icon w-full validator',
            'required': True,
        }),
        label="City",
        required=False
    )

    # Text fields for Global country (not saved to model, just for UI)
    region_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full validator',
        })
    )
    city_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full validator',
        })
    )
    
    class Meta:
        model = UserProfile
        fields = ['country', 'region', 'city', "consent_flag"]
        widgets = {
            'consent_flag': forms.CheckboxInput(attrs={
                'class': 'checkbox checkbox-xs rounded-[var(--radius-4)]',
            }),
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