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
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.models.base import ALCBTCountryManager


class AssemblyForm(forms.ModelForm):
    country = forms.ModelChoiceField(
        queryset=ALCBTCountryManager.get_alcbt_countries(),
        label="Country",
        required=True,
    )
    comment = forms.CharField(
        widget=widgets.Textarea(attrs={"rows": 2}), required=False
    )

    public = forms.BooleanField(
        required=False,
        widget=widgets.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    is_template = forms.BooleanField(
        required=False,
        label="Save as template",
        widget=widgets.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    mode = forms.ChoiceField(
        required=False,
        choices=AssemblyMode.choices,
        widget=forms.Select(attrs={"disabled": "disabled"}),
        label="Mode*",
    )
    assembly_category = forms.ModelChoiceField(
        queryset=AssemblyCategory.objects.all().order_by("tag"),
        widget=forms.Select(
            attrs={
                "hx-get": "/select_lists/",
                "hx-trigger": "change",
                "hx-target": "#assembly-technique",
                "class": "select form-select",
            }
        ),
        label="Building Component",
        required=True,
    )
    assembly_technique = forms.ModelChoiceField(
        queryset=AssemblyTechnique.objects.none(),
        widget=forms.Select(
            attrs={
                "id": "assembly-technique",
                "class": "select form-select",
            }
        ),
        label="Construction technique",
        help_text="Select a category",
        required=False,
    )
    dimension = forms.ChoiceField(
        choices=AssemblyDimension.choices,
        widget=forms.Select(
            attrs={
                "id": "dimension-select",
                "hx-post": "",
                "hx-trigger": "change",
                "hx-target": "#epd-list",
                "hx-vals": '{"action": "filter"}',
                "class": "form-select flex-grow-0 w-auto",
            }
        ),
        label="Input Dimension",
    )
    quantity = forms.DecimalField(
        min_value=0,
        label="Quantity",
        required=True,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    )

    # reporting_life_cycle = forms.IntegerField(
    #     label="Life Span",
    #     min_value=1,
    #     max_value=10000,
    #     help_text="Report in years",
    #     required=True,
    #     initial=50,
    #     widget=forms.NumberInput(attrs={"class": "form-control", "type": "number"}),
    # )

    class Meta:
        model = Assembly
        fields = [
            "name",
            "country",
            "comment",
            "public",
            "is_template",
            "dimension",
        ]

    def __init__(self, *args, **kwargs):
        building_id = kwargs.pop("building_id", None)
        simulation = kwargs.pop("simulation", False)
        template_edit = kwargs.pop("template_edit", False)

        if simulation:
            BuildingAssemblyModel = BuildingAssemblySimulated
        else:
            BuildingAssemblyModel = BuildingAssembly

        super().__init__(*args, **kwargs)
        if kwargs.get("instance"):
            assembly_classification = self.instance.classification
            self.fields["mode"].initial = self.instance.mode
            self.fields["dimension"].initial = self.instance.dimension
            self.fields["assembly_category"].initial = assembly_classification.category
            self.fields["assembly_technique"].queryset = (
                AssemblyTechnique.objects.filter(
                    categories__pk=assembly_classification.category.pk
                )
            )
            self.fields["assembly_technique"].initial = (
                assembly_classification.technique
            )

            # Only try to get BuildingAssembly data if NOT editing a template
            if not template_edit:
                try:
                    building_assembly = BuildingAssemblyModel.objects.get(
                        assembly=self.instance, building__pk=building_id
                    )
                    self.fields["quantity"].initial = building_assembly.quantity
                    # self.fields["reporting_life_cycle"].initial = building_assembly.reporting_life_cycle
                except BuildingAssemblyModel.DoesNotExist:
                    self.fields["quantity"].initial = 1
                    # self.fields["reporting_life_cycle"].initial = 50
            else:
                # For template editing, use default or template-specific values
                self.fields["quantity"].initial = 1  # Default quantity for templates
                # self.fields["reporting_life_cycle"].initial = 50
        else:
            self.fields["mode"].initial = AssemblyMode.CUSTOM
            self.fields["dimension"].initial = AssemblyDimension.AREA

            # Only try to get building country if NOT editing a template
            if not template_edit and building_id:
                try:
                    self.fields["country"].initial = Building.objects.get(
                        id=building_id
                    ).country
                except Building.DoesNotExist:
                    pass

        if category_id := self.data.get("assembly_category"):
            category_id = int(category_id)
            self.fields["assembly_technique"].queryset = (
                AssemblyTechnique.objects.filter(categories__id=category_id)
            )

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