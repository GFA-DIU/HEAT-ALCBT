import logging
from collections import defaultdict
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional

from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.forms import ValidationError

from pages.models.assembly import Assembly, Product, AssemblyImpact
from pages.models.epd import EPD, EPDImpact
from pages.forms.assembly_form import AssemblyForm


logger = logging.getLogger(__name__)


@dataclass
class SelectedEPD:
    id: str
    available_units: list[str]
    sel_unit: Optional[str]
    sel_quantity: float
    name: str
    category: Optional[str]
    country: Optional[str]
    source: Optional[str]
    
    @classmethod
    def parse_product(cls, product):
        """
        Parses a Product instance into a SelectedEPD dataclass.
        """
        available_units = [i["unit"] for i in product.epd.conversions]
        available_units.append(product.epd.declared_unit)
        
        return cls(
            id=str(product.epd.id),
            sel_unit=product.input_unit,
            available_units = available_units,
            sel_quantity=float(product.quantity),
            name=product.epd.name,
            category=product.epd.category.name_en if product.epd.category else None,
            country=product.epd.country.name if product.epd.country else None,
            source=product.epd.source
        )

    @classmethod
    def parse_epd(cls, epd):
        """
        Parses an EPD instance into a SelectedEPD dataclass.
        """
        available_units = [i["unit"] for i in epd.conversions]
        available_units.append(epd.declared_unit)
        
        return cls(
            id=str(epd.id),
            sel_unit="",
            sel_quantity="",
            name=epd.name,
            category=epd.category.name_en if epd.category else None,
            country=epd.country.name if epd.country else None,
            source=epd.source
        )


@require_http_methods(["GET", "POST", "DELETE"])
def component_edit(request, assembly_id=None):
    """
    View to either edit an existing component or create a new one with pagination for EPDs.
    """
    # Initialize the session variable if it doesn't exist
    if "selected_epds" not in request.session:
        request.session["selected_epds"] = []


    component = get_object_or_404(Assembly, id=assembly_id)
    products = Product.objects.filter(assembly=component).select_related('epd')
    selected_epds = [SelectedEPD.parse_product(p) for p in products]

    # # Load selected EPDs from session
    # selected_epd_ids = request.session["selected_epds"]
    # selected_epds = EPD.objects.filter(id__in=selected_epd_ids)

    context = {
        "assembly_id": assembly_id,
        "selected_epds": selected_epds,
    }

    # Pagination setup for EPD list
    epd_list = EPD.objects.all().order_by('id')  # Replace with any filtering logic if needed
    paginator = Paginator(epd_list, 10)  # Show 10 items per page
    page_number = request.GET.get('page', 1)  # Get the current page number from the query parameters
    page_obj = paginator.get_page(page_number)

    # Add the paginated list to the context
    context["epd_list"] = page_obj

    if assembly_id:
        component = get_object_or_404(Assembly, id=assembly_id)
        context["assembly_id"] = component.id


        if request.method == "POST" and request.POST.get("action") == "form_submission":
            context = save_assembly(request, context, component)
            return HttpResponseRedirect(reverse('component_edit', kwargs={'assembly_id': assembly_id}))

        elif request.method == "GET" and request.GET.get("page"):
            # Handle partial rendering for HTMX
            return render(request, "pages/building/component_add/epd_list.html", context)

        elif request.method =="GET" and request.GET.get("add_component") == "step_1":
            # TODO: Only makes sense for new component
            return render(request, "pages/building/component_add/modal_step_1.html")

        else:
            form = AssemblyForm(instance=component)
    else:
        # Handle creation of a new assembly
        if request.method == "POST":
            form = AssemblyForm(request.POST)
            if form.is_valid():
                form.save()
                # Clear the session variable after successful submission
                request.session["selected_epds"] = []
                return HttpResponseRedirect(reverse("component"))
        else:
            form = AssemblyForm()

    # Add form to context
    context["form"] = form

    # Render full template for non-HTMX requests
    return render(request, "pages/building/component_add/modal_step_2.html", context)


def save_assembly(request, context, component):
    print("This is a form submission")
    print(request.POST)

    # Bind the form to the existing Assembly instance
    form = AssemblyForm(request.POST, instance=component)
    if form.is_valid():
        # Save the updated Assembly instance
        assembly = form.save()
        
        # Create clean slate
        Product.objects.filter(assembly=assembly).delete()
        AssemblyImpact.objects.filter(assembly=assembly).delete()

        # Clear the session variable after successful submission
        request.session["selected_epds"] = []

        epd_impacts = []

        # Collect EPD IDs and dynamic field data
        epd_ids = set()
        dynamic_fields = []
        for key, value in request.POST.items():
            print("Key: ", key)
            print("Value: ", value)
            if key.startswith("material_") and "_quantity" in key:
                epd_id = key.split("_")[1]
                epd_ids.add(epd_id)
                dynamic_fields.append({
                    "epd_id": epd_id,
                    "quantity": Decimal(value),
                    "unit": request.POST[f"material_{epd_id}_unit"],
                })

        print("Dynamic fields: ", dynamic_fields)
        # Pre-fetch EPDImpact and Impact objects
        epds = EPD.objects.filter(pk__in=epd_ids).prefetch_related(
            Prefetch(
                "epdimpact_set",
                queryset=EPDImpact.objects.select_related("impact"),
                to_attr="prefetched_impacts",
            )
        )
        epd_map = {str(epd.id): epd for epd in epds}

        # Process each dynamic field
        impacts_data = defaultdict(Decimal)  # For summing impacts by cate1 mgory & stage
        for field in dynamic_fields:
            # Fetch the EPD and its impacts
            epd = epd_map[field["epd_id"]]
            conversion_f = 1
            if epd.declared_unit != field.get("unit"):
                conversion_f = [f["value"] for f in epd.conversions if f["unit"]==field.get("unit")]
                conversion_f = float(conversion_f[0])
            print("conversion f: ", conversion_f)
                
            for impact in epd.prefetched_impacts:
                # Group impacts by category and stage
                impacts_data[impact.impact] += Decimal(impact.value) * field.get("quantity") * Decimal(conversion_f)

                epd_impacts.append({
                    "impact": impact.impact,
                    "value": Decimal(impact.value) * field.get("quantity") * Decimal(conversion_f),
                })

            # Save the Product
            product = Product.objects.update_or_create(
                epd=epd,
                assembly=component,
                quantity=field.get("quantity"),
                input_unit=field.get("unit"),
            )


        print("epd_impacts: ", epd_impacts)
        print("impacts_data: ", impacts_data)
        # Create AssemblyImpact records
        for impact, total_value in impacts_data.items():
            AssemblyImpact.objects.update_or_create(
                assembly=assembly,
                impact=impact,
                value=total_value,
            )

        # Update context with the form and EPD list
        epd_list = EPD.objects.all()
        context["epd_list"] = epd_list
        context["form"] = form
        context["epd_impacts"] = epd_impacts  # Add the impacts to the context for further use
        print("This is context", context)
        return context




def component_new(request):
    print("Component new", request)
    context = {}
    # If no component ID, assume creation of a new component
    if request.method == "POST":
        form = AssemblyForm(request.POST)
        if form.is_valid():
            form.save()
            # return HttpResponseRedirect(reverse("component"))  # Redirect after successful creation
    else:
        form = AssemblyForm()  # Blank form for new component creation

    context["form"] = form
    return render(request, "pages/building/test_component.html", context)
