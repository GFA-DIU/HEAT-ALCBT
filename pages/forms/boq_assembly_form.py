from django import forms
from django.forms import widgets
from django.utils.translation import gettext as _

from pages.models.assembly import Assembly
from pages.models.building import BuildingAssembly, BuildingAssemblySimulated


class BOQAssemblyForm(forms.ModelForm):
    comment = forms.CharField(
        widget=widgets.Textarea(attrs={"rows": 2}), required=False
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
            "comment",
        ]

    def __init__(self, *args, **kwargs):
        building_id = kwargs.pop("building_id", None)
        simulation = kwargs.pop("simulation", False)
        if simulation:
            BuildingAssemblyModel = BuildingAssemblySimulated
        else:
            BuildingAssemblyModel = BuildingAssembly

        super().__init__(*args, **kwargs)
        if kwargs.get("instance"):
            pass
            # self.fields["reporting_life_cycle"].initial = (
            #     BuildingAssemblyModel.objects.get(
            #         assembly=self.instance, building__pk=building_id
            #     ).reporting_life_cycle
            # )
