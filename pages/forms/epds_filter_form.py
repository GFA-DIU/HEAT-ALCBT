from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Div
from crispy_forms.bootstrap import Accordion, AccordionGroup
from cities_light.models import Country


from pages.models.epd import MaterialCategory, EPDType


class EPDsFilterForm(forms.Form):
    search_query = forms.CharField(label="Text search", max_length=100, required=False)
    category = forms.ModelChoiceField(
        queryset=MaterialCategory.objects.filter(level=1).order_by("name_en"),
        widget=forms.Select(
            attrs={
                "hx-get": "/select_lists/",  # HTMX request to the root URL
                "hx-trigger": "change",  # Trigger HTMX on change event
                "hx-target": "#sub-category",  # Update the City dropdown
                "class": "select form-select",
            }
        ),
        label="Category",
        required=False,
    )
    subcategory = forms.ModelChoiceField(
        queryset=MaterialCategory.objects.none(),  # Start with an empty queryset
        widget=forms.Select(
            attrs={
                "id": "sub-category",
                "hx-get": "/select_lists/",  # HTMX request to the root URL
                "hx-trigger": "change",  # Trigger HTMX on change event
                "hx-target": "#child-category",  # Update the City dropdown
                "class": "select form-select",
            }
        ),
        label="Subcategory",
        help_text="Select a category first",
        required=False,
    )
    childcategory = forms.ModelChoiceField(
        queryset=MaterialCategory.objects.none(),  # Start with an empty queryset
        widget=forms.Select(
            attrs={
                "id": "child-category",
                "class": "select form-select",
            }
        ),
        label="Child category",
        help_text="Select a subcategory first",
        required=False,
    )
    country = forms.ModelChoiceField(
        queryset=Country.objects.all().order_by("name"),
        label="Country",
        required=False,
    )
    type = forms.ChoiceField(
        choices=[('', '---------')] + [(choice.value, choice.value) for choice in EPDType],
        label="EPD type",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "search_query" in self.data:
            self.initial["search_query"] = self.data.get("search_query")

        if "childcategory" in self.data:
            self.initial["childcategory"] = self.data.get("childcategory")

        if "subcategory" in self.data:
            self.initial["subcategory"] = self.data.get("subcategory")
            try:
                subcategory_id = int(self.data.get("subcategory"))
                self.fields["childcategory"].queryset = MaterialCategory.objects.filter(
                    level=3, parent__pk=subcategory_id
                ).order_by("name_en")
            except (ValueError, TypeError):
                self.fields["childcategory"].queryset = MaterialCategory.objects.none()

        # Adjust 'city' queryset dynamically based on 'country' in the request data
        if "category" in self.data:
            self.initial["category"] = self.data.get("category")
            try:
                category_id = int(self.data.get("category"))
                self.fields["subcategory"].queryset = MaterialCategory.objects.filter(
                    level=2, parent__pk=category_id
                ).order_by("name_en")
            except (ValueError, TypeError):
                self.fields["subcategory"].queryset = MaterialCategory.objects.none()

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("search_query", css_class="col-md-9"),
                Column("country", css_class="col-md-3"),
            ),
            Accordion(
                AccordionGroup(
                    mark_safe('<strong>Advanced Search</strong>'),
                    Row(
                        Column("category", css_class="col-md-4"),
                        Column("subcategory", css_class="col-md-4"),
                        Column("childcategory", css_class="col-md-4"),
                    ),
                    Row(
                        Column("type", css_class="col-md-3"),
                    ),
                    active=False
                ),
            ),
            Div(
                Submit("submit", "Search", css_class="btn btn-primary"),
                css_class="mt-3"
            ),
                
        )
