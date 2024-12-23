from django import forms
from django.forms import widgets
from django.db import models
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit

from cities_light.models import Country, City

from pages.models import Assembly, AssemblyMode


class AssemblyForm(forms.ModelForm):
    comment = forms.CharField(widget=widgets.Textarea(attrs={'rows': 3}))
    public = forms.BooleanField(
        required=False,
        widget=widgets.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    mode = forms.ChoiceField(
        choices=AssemblyMode.choices,
        widget=forms.Select(attrs={'disabled': 'disabled'})
    )
    
    class Meta:
        model = Assembly
        fields = [
            "name",
            "country",
            "dimension",
            "classification",
            "comment",
            "public",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['mode'].initial = self.instance.mode
        else:
            self.fields['mode'].initial = AssemblyMode.CUSTOM

    #     # Crispy Forms Layout
    #     self.helper = FormHelper()
    #     self.helper.layout = Layout(
    #         # Name and Category in the first row
    #         Row(
    #             Column('name', css_class='col-md-6'),
    #             Column('type', css_class='col-md-6'),
    #         ),
    #         # Country and City in the second row
    #         Row(
    #             Column('country', css_class='col-md-6'),
    #             Column('classification', css_class='col-md-6'),
    #         ),
    #         # Zip code in its own row
    #         Row(
    #             Column('comment', css_class='col-md-12'),
    #         ),
    #         Submit('submit', 'Save', css_class='btn btn-primary'),
    #     )
