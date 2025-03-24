from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, UserProfile

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
            'hx-target': '#city-dropdown', # Update the City dropdown
            'class': 'select form-select',
        }),
        label="Country"
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
        fields = ['country', 'city', "consent_flag"]
        
        
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        if instance:
            if instance.country:
                self.fields['city'].queryset = CustomCity.objects.filter(country=instance.country).order_by('name')
                self.initial['country'] = instance.country
            else: 
                self.fields['city'].queryset = CustomCity.objects.none()

            # Ensure the selected 'city' is prepopulated
            if instance.city:
                self.initial['city'] = instance.city

        # Adjust 'city' queryset dynamically based on 'country' in the request data
        if "country" in self.data:
            try:
                country_id = int(self.data.get("country"))
                self.fields["city"].queryset = CustomCity.objects.filter(
                    country_id=country_id
                ).order_by("name")
            except (ValueError, TypeError):
                self.fields["city"].queryset = CustomCity.objects.none()
        elif self.instance.pk:
            # If editing an existing instance, prepopulate the 'city' queryset
            self.fields["city"].queryset = CustomCity.objects.filter(
                country=self.instance.country
            ).order_by("name")