from django import forms
from django.forms import widgets
from django.utils.translation import gettext as _

from pages.models.assembly import (
    Assembly,
    AssemblyDimension,
    AssemblyMode,
    AssemblyCategory,
    AssemblyTechnique,
    AssemblyCategoryTechnique,
)


class AssemblyForm(forms.ModelForm):
    comment = forms.CharField(widget=widgets.Textarea(attrs={"rows": 3}))
    public = forms.BooleanField(
        required=False,
        widget=widgets.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    mode = forms.ChoiceField(
        required=True,
        choices=AssemblyMode.choices,
        widget=forms.Select(attrs={"disabled": "disabled"}),
    )
    assembly_category = forms.ModelChoiceField(
        queryset=AssemblyCategory.objects.all().order_by("tag"),
        widget=forms.Select(
            attrs={
                "hx-get": "/select_lists/",  # HTMX request to the root URL
                "hx-trigger": "change",  # Trigger HTMX on change event
                "hx-target": "#assembly-technique",  # Update the City dropdown
                "class": "select form-select",
            }
        ),
        label="Category",
        required=True,
    )
    assembly_technique = forms.ModelChoiceField(
        queryset=AssemblyTechnique.objects.none(),  # Start with an empty queryset
        widget=forms.Select(
            attrs={
                "id": "assembly-technique",
                "class": "select form-select",
            }
        ),
        label="Technique",
        help_text="Select a category first",
        required=False,
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
        label="Input Dimension"
    )
    quantity = forms.FloatField(
        min_value=0,
        label="Quantity",
        required=True
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
            self.fields["mode"].initial = self.instance.mode
            self.fields["dimension"].initial = self.instance.dimension
            self.fields["assembly_category"].initial = self.instance.classification.category
            self.fields["assembly_technique"].queryset = AssemblyTechnique.objects.filter(categories__pk=self.instance.classification.category.pk)
            self.fields["assembly_technique"].initial = self.instance.classification.technique
        else:
            self.fields["mode"].initial = AssemblyMode.CUSTOM
            self.fields["dimension"].initial = AssemblyDimension.AREA
        
        # Dynamically update the queryset for assembly_technique to enable form validation
        if category_id := self.data.get("assembly_category"):
            category_id = int(category_id)
            # update queryset
            self.fields["assembly_technique"].queryset = AssemblyTechnique.objects.filter(categories__id=category_id)
        
        # parse into Assembly classification
        if category_id or self.fields["assembly_technique"].initial:
            category_id = category_id if category_id else self.fields["assembly_technique"].initial.pk
            technique_id = self.data.get("assembly_technique") if self.data.get("assembly_technique") else None
            self.initial["classification"] = AssemblyCategoryTechnique.objects.filter(
                    category__id=category_id, technique__id=technique_id
                ).first()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("classification") and self.initial.get("classification"):
            cleaned_data["classification"] = self.initial["classification"]
        return cleaned_data

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
