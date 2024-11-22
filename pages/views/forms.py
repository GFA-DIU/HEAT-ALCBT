from django import forms

# Replace this with a database query later
def get_country_choices():
    return [
        ('us', 'United States'),
        ('de', 'Germany'),
        ('fr', 'France'),
    ]
    
def get_measurement_type_choices():
    return [
        ('area', 'Area - m²'),
        ('volume', 'Volume - %'),
        ('mass', 'Mass - t'),
        ('length', 'Length - m'),
    ]

class AssemblyForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamically populate the choices with a placeholder
        self.fields['country'].choices = [('', 'Select a country')] + get_country_choices()
        self.fields['country'].widget.attrs.update({'class': 'form-select'})
        
        self.fields['measurement_type'].choices = [('', 'Select a measurement type')] + get_measurement_type_choices()
        self.fields['measurement_type'].widget.attrs.update({'class': 'form-select'})
    
    assembly_name = forms.CharField(
        label="Assembly Name",
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Type your assembly name..'
        })
    )
    country = forms.ChoiceField(
        initial="Select your country..",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    ) 
    measurement_type = forms.ChoiceField(
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    public = forms.BooleanField(
        label="Public",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    