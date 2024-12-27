from django import forms
from django.forms import widgets
from django.utils.translation import gettext as _

from pages.models.assembly import Assembly, AssemblyDimension, AssemblyMode, AssemblyCategory, AssemblyTechnique


class AssemblyForm(forms.ModelForm):
    comment = forms.CharField(widget=widgets.Textarea(attrs={'rows': 3}))
    public = forms.BooleanField(
        required=False,
        widget=widgets.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    mode = forms.ChoiceField(
        required=False,
        choices=AssemblyMode.choices,
        widget=forms.Select(attrs={"disabled": "disabled"}),
    )
    dimension = forms.ChoiceField(
        choices=AssemblyDimension.choices,
        widget=forms.Select(
            attrs={
                "id": "dimension-select",
                "hx-post": "",  # HTMX request to the current url path
                "hx-trigger": "change",  # Trigger HTMX on change event
                "hx-target": "#epd-list",  # Update the City dropdown
                "hx-vals": '{"action": "filter"}',  # Dynamically include the dropdown value
                "class": "select form-select",
            }
        ),
    )

    class Meta:
        model = Assembly
        fields = [
            "name",
            "country",
            "classification",
            "comment",
            "public",
            "dimension",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['mode'].initial = self.instance.mode
            self.fields['dimension'].initial = self.instance.dimension
        else:
            self.fields['mode'].initial = AssemblyMode.CUSTOM
            self.fields["dimension"].initial = AssemblyDimension.AREA

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
