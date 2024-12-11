import logging

from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.models.assembly import Assembly
from pages.models.epd import EPD
from pages.forms.assembly_form import AssemblyForm


logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def component_edit(request, assembly_id=None):
    """
    View to either edit an existing component or create a new one.
    """
    # Initialize the session variable if it doesn't exist
    if "selected_epds" not in request.session:
        request.session["selected_epds"] = []

    # Load selected EPDs from session
    selected_epd_ids = request.session["selected_epds"]
    selected_epds = EPD.objects.filter(id__in=selected_epd_ids)

    context = {
        "assembly_id": assembly_id,
        "selected_epds": selected_epds,
    }
    
    if assembly_id:
        component = get_object_or_404(Assembly, id=assembly_id)
        context["assembly_id"] = component.id

        if request.method == "POST":
            if request.POST.get("action") == "form_submission":
                print("This is a form submission")
                form = AssemblyForm(request.POST, instance=component)
                if form.is_valid():
                    form.save()
                    # Clear the session variable after successful submission
                    request.session["selected_epds"] = []
                    form = AssemblyForm(instance=component)
                    epd_list = EPD.objects.all()
                    context["epd_list"] = epd_list
                    context["form"] = form
                    print("This is context", context)
                    return render(request, "pages/building/test_component.html", context)

            elif request.POST.get("epd_selected"):
                epd_id = request.POST.get("epd_selected")
                if epd_id not in selected_epd_ids:
                    selected_epd_ids.append(epd_id)
                    request.session["selected_epds"] = selected_epd_ids
            context["selected_epds"] = EPD.objects.filter(id__in=selected_epd_ids)
            return render(request, "pages/building/component_add/selected_epd_list.html", context)

        elif request.method == "DELETE":
            # epd_id = request.body.decode("utf-8")  # Get epd_id from the request body
            epd_id = request.GET.get("epd_remove")
            print("This is delete: ", epd_id)
            print(selected_epd_ids)
            if epd_id in selected_epd_ids:
                selected_epd_ids.remove(epd_id)
                request.session["selected_epds"] = selected_epd_ids
            context["selected_epds"] = EPD.objects.filter(id__in=selected_epd_ids)
            return render(request, "pages/building/component_add/selected_epd_list.html", context)

        else:
            form = AssemblyForm(instance=component)
            epd_list = EPD.objects.all()
            context["epd_list"] = epd_list
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
            epd_list = EPD.objects.all()
            context["epd_list"] = epd_list

    context["form"] = form
    return render(request, "pages/building/test_component.html", context)


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
