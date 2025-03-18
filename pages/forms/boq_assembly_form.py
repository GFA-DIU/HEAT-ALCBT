from django import forms
from django.forms import widgets
from django.utils.translation import gettext as _

from pages.models.assembly import (
    Assembly,
    AssemblyCategory,
    AssemblyTechnique,
    AssemblyCategoryTechnique,
)
from pages.models.building import BuildingAssembly, BuildingAssemblySimulated


class BOQAssemblyForm(forms.ModelForm):
    comment = forms.CharField(
        widget=widgets.Textarea(attrs={"rows": 2}), required=False
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
        label="Construction Technique",
        help_text="Select a category",
        required=False,
    )
    reporting_life_cycle = forms.IntegerField(
        label="Life Span",
        min_value=1,
        max_value=10000,
        help_text="Report in years",
        required=True,
        initial=50,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    class Meta:
        model = Assembly
        fields = [
            "name",
            "comment",
            "classification",
        ]

    def __init__(self, *args, **kwargs):
        building_id = kwargs.pop("building_id", None)
        simulation = kwargs.pop("simulation", None)
        if simulation:
            BuildingAssemblyModel = BuildingAssemblySimulated
        else:
            BuildingAssemblyModel = BuildingAssembly

        super().__init__(*args, **kwargs)
        if kwargs.get("instance"):
            self.fields["assembly_category"].initial = (
                self.instance.classification.category
            )
            self.fields["assembly_technique"].queryset = (
                AssemblyTechnique.objects.filter(
                    categories__pk=self.instance.classification.category.pk
                )
            )
            self.fields["assembly_technique"].initial = (
                self.instance.classification.technique
            )
            self.fields["reporting_life_cycle"].initial = (
                BuildingAssemblyModel.objects.get(
                    assembly=self.instance, building__pk=building_id
                ).reporting_life_cycle
            )

        # Dynamically update the queryset for assembly_technique to enable form validation
        if category_id := self.data.get("assembly_category"):
            category_id = int(category_id)
            # update queryset
            self.fields["assembly_technique"].queryset = (
                AssemblyTechnique.objects.filter(categories__id=category_id)
            )

        # parse into Assembly classification
        if category_id or self.fields["assembly_technique"].initial:
            category_id = (
                category_id
                if category_id
                else self.fields["assembly_technique"].initial.pk
            )
            technique_id = (
                self.data.get("assembly_technique")
                if self.data.get("assembly_technique")
                else None
            )
            self.initial["classification"] = AssemblyCategoryTechnique.objects.filter(
                category__id=category_id, technique__id=technique_id
            ).first()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("classification") and self.initial.get(
            "classification"
        ):
            cleaned_data["classification"] = self.initial["classification"]
        return cleaned_data
