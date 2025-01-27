from django import forms
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Layout, Fieldset, Row, Column, Submit

from pages.models import Building


class BuildingDetailedInformation(forms.ModelForm):
    class Meta:
        model = Building
        fields = [
            "longitude",
            "latitude",
            "cond_floor_area",
            "floors_above_ground",
            "floors_below_ground",
        ]

        error_messages = {
            "name": {
                "max_length": _("This writer's name is too long."),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Crispy Forms Layout
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Location",
                # Street and Number
                Row(
                    Column("longitude", css_class="col-md-4"),
                    Column("latitude", css_class="col-md-4"),
                ),
            ),
            HTML("<hr>"),  # Add a horizontal rule
            Fieldset(
                "Category",
                # Street and Number in the last row with Postal code behind
                Row(
                    Column("cond_floor_area", css_class="col-md-3"),
                    Column("floors_above_ground", css_class="col-md-3"),
                    Column("floors_below_ground", css_class="col-md-3"),
                ),
            ),
            Submit("submit", "Submit", css_class="btn btn-primary"),
        )
