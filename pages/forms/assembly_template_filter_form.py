from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Div
from crispy_forms.bootstrap import Accordion, AccordionGroup
from cities_light.models import Country

from pages.models.assembly import AssemblyCategory, AssemblyTechnique, AssemblyDimension
from pages.models.base import ALCBTCountryManager


class AssemblyTemplateFilterForm(forms.Form):
    search_query = forms.CharField(
        label="Text search", 
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search templates by name...'})
    )
    
    template_type = forms.ChoiceField(
        choices=[
            ('', 'All templates'),
            ('user', 'My templates only'),
            ('generic', 'Generic templates only'),
        ],
        label="Template Type",
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    dimension = forms.ChoiceField(
        choices=[('', 'All dimensions')] + AssemblyDimension.choices,
        label="Dimension Type",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    country = forms.ModelChoiceField(
        queryset=ALCBTCountryManager.get_alcbt_countries(),
        label="Country",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    category = forms.ModelChoiceField(
        queryset=AssemblyCategory.objects.all().order_by("tag"),
        widget=forms.Select(
            attrs={
                "hx-get": "/select_lists/",
                "hx-trigger": "change",
                "hx-target": "#template-technique",
                "class": "select form-select",
            }
        ),
        label="Building Component",
        required=False,
    )
    
    technique = forms.ModelChoiceField(
        queryset=AssemblyTechnique.objects.none(),
        widget=forms.Select(
            attrs={
                "id": "template-technique",
                "class": "select form-select",
            }
        ),
        label="Construction Technique",
        help_text="Select a component category first",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Handle dynamic technique filtering based on category
        if "category" in self.data:
            self.initial["category"] = self.data.get("category")
            try:
                category_id = int(self.data.get("category"))
                self.fields["technique"].queryset = AssemblyTechnique.objects.filter(
                    categories__pk=category_id
                ).order_by("name")
            except (ValueError, TypeError):
                self.fields["technique"].queryset = AssemblyTechnique.objects.none()

        # Preserve other field values
        for field_name in ['search_query', 'template_type', 'technique', 'dimension', 'country']:
            if field_name in self.data:
                self.initial[field_name] = self.data.get(field_name)

        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = Layout(
            Row(
                Column("search_query", css_class="col-md-6"),
                Column("country", css_class="col-md-3"),
                Column("template_type", css_class="col-md-3"),
            ),
            Accordion(
                AccordionGroup(
                    mark_safe('<strong>Advanced filters</strong>'),
                    Row(
                        Column("category", css_class="col-md-4"),
                        Column("technique", css_class="col-md-4"),
                        Column("dimension", css_class="col-md-4"),
                    ),
                    active=False
                ),
            ),
            Div(
                Submit("filter", "Search", css_class="btn btn-primary"),
                css_class="mt-3"
            ),
        )