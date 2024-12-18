from django import forms
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit

from pages.models.epd import MaterialCategory


class EPDsFilterForm(forms.Form):
    search_query = forms.CharField(label="Search...", max_length=100, required=False)
    category = forms.ModelChoiceField(
        queryset=MaterialCategory.objects.filter(level=1).order_by("name_en"),
        widget=forms.Select(
            attrs={
                "hx-get": "/select_lists/",  # HTMX request to the root URL
                "hx-trigger": "change",  # Trigger HTMX on change event
                "hx-target": "#sub-category",  # Update the City dropdown
                "hx-vals": '{"id": this.value}',  # Dynamically include the dropdown value
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
                "hx-vals": '{"id": this.value}',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "subcategory" in self.data:
            try:
                subcategory_id = int(self.data.get("subcategory"))
                self.fields["childcategory"].queryset = MaterialCategory.objects.filter(
                    level=3, parent__pk=subcategory_id
                ).order_by("name_en")
            except (ValueError, TypeError):
                self.fields["childcategory"].queryset = MaterialCategory.objects.none()

        # Adjust 'city' queryset dynamically based on 'country' in the request data
        elif "category" in self.data:
            try:
                category_id = int(self.data.get("category"))
                self.fields["subcategory"].queryset = MaterialCategory.objects.filter(
                    level=2, parent__pk=category_id
                ).order_by("name_en")
            except (ValueError, TypeError):
                self.fields["subcategory"].queryset = MaterialCategory.objects.none()

        # Crispy Forms Layout
        self.helper = FormHelper()
        self.helper.layout = Layout(
            # Name and Category in the first row
            Row(
                Column("search_query", css_class="col-md-3"),
                Column("category", css_class="col-md-3"),
                Column("subcategory", css_class="col-md-3"),
                Column("childcategory", css_class="col-md-3"),
            ),
            Submit("submit", "Search", css_class="btn btn-primary"),
        )
