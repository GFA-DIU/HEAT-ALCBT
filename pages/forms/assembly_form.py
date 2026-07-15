from django import forms
from django.forms import widgets
from django.utils.translation import gettext as _

from pages.models.assembly import (
    Assembly,
    AssemblyDimension,
    AssemblyMode,
    AssemblyCategory,
    AssemblyFamily,
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
    mode = forms.ChoiceField(
        required=False,
        choices=AssemblyMode.choices,
        widget=forms.Select(attrs={"disabled": "disabled"}),
        label="Mode*",
    )
    building_part = forms.ChoiceField(
        choices=[("", "Select a building part")] + list(AssemblyFamily.choices),
        widget=forms.Select(
            attrs={
                "hx-get": "/select_lists/",  # populate the component list for this part
                "hx-trigger": "change",
                "hx-target": "#assembly-category",  # narrow the Building Component dropdown
                "class": "select form-select",
            }
        ),
        label="Building Part",
        required=False,  # UI helper: the chosen component already implies its part
    )
    assembly_category = forms.ModelChoiceField(
        queryset=AssemblyCategory.objects.none(),  # populated once a Building Part is chosen
        widget=forms.Select(
            attrs={
                "id": "assembly-category",
                "hx-get": "/select_lists/",  # HTMX request to the root URL
                "hx-trigger": "change",  # Trigger HTMX on change event
                "hx-target": "#assembly-technique",  # Update the technique dropdown
                "class": "select form-select",
            }
        ),
        label="Building Component",
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
        label="Construction technique",
        help_text="Select a category",
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
            "dimension",
        ]

    def __init__(self, *args, **kwargs):
        building_id = kwargs.pop("building_id", None)
        simulation = kwargs.pop("simulation", False)
        if simulation:
            BuildingAssemblyModel = BuildingAssemblySimulated
        else:
            BuildingAssemblyModel = BuildingAssembly

        super().__init__(*args, **kwargs)
        # Show only the component name in the dropdown (not the "tag - name" __str__);
        # the tag is used purely to order the list ground-up.
        self.fields["assembly_category"].label_from_instance = lambda obj: obj.name
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
            self.fields["quantity"].initial = BuildingAssemblyModel.objects.get(
                assembly=self.instance, building__pk=building_id
            ).quantity
            # self.fields["reporting_life_cycle"].initial = (
            #     BuildingAssemblyModel.objects.get(
            #         assembly=self.instance, building__pk=building_id
            #     ).reporting_life_cycle
            # )
        else:
            self.fields["mode"].initial = AssemblyMode.CUSTOM
            self.fields["dimension"].initial = AssemblyDimension.AREA
            self.fields["country"].initial = Building.objects.get(
                id=building_id
            ).country

        # --- Building Part (family) cascade ---------------------------------
        # Scope the component dropdown to a family so the list isn't overwhelming.
        family = None
        if self.instance and self.instance.pk and self.instance.classification:
            family = self.instance.classification.category.family
        elif self.data.get("building_part"):
            family = self.data.get("building_part")
        if family:
            self.fields["building_part"].initial = family
            self.fields["assembly_category"].queryset = (
                AssemblyCategory.objects.filter(family=family).order_by("tag")
            )
        # On submit, accept whatever component was chosen even if the part field
        # wasn't sent, so validation never wrongly rejects a valid component.
        if self.is_bound and self.data.get("assembly_category"):
            self.fields["assembly_category"].queryset = (
                AssemblyCategory.objects.all().order_by("tag")
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
