from django import forms

class AssemblyForm(forms.Form):
    assembly_name = forms.CharField(
        label="Assembly Name",
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Type your assembly name..'
        })
    )
    country = forms.ChoiceField(
        label="Select Country",
        choices=[
            ('Germany', 'Germany'),
            ('India', 'India'),
            ('Indonesia', 'Indonesia'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    measurement_type = forms.ChoiceField(
        label="Select Measurement Type to report in",
        choices=[
            ('area', 'Area - m²'),
            ('volume', 'Volume - %'),
            ('mass', 'Mass - t'),
            ('length', 'Length - m'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    public = forms.BooleanField(
        label="Public",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )