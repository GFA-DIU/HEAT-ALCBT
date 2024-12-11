import logging

from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.models.assembly import Assembly, AssemblyImpact
from pages.forms.assembly_form import AssemblyForm

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def component_edit(request, assembly_id=None):
    """
    View to either edit an existing component or create a new one.
    """
    context = {"assembly_id": assembly_id}

    if assembly_id:
        # If a component ID is provided, try to fetch the existing component
        component = get_object_or_404(Assembly, id=assembly_id)
        context["assembly_id"] = component.id
        print(context)
        print(request)
        if request.method == "POST":
            print("Here am I")
            form = AssemblyForm(request.POST, instance=component)
            if form.is_valid():
                print("Form is valid: ", request.POST)
                form.save()
                # return HttpResponseRedirect(reverse("component"))  # Redirect after successful update
        else:
            form = AssemblyForm(
                instance=component
            )  # Prepopulate the form with the component data
    else:
        if request.method == "POST":
            form = AssemblyForm(request.POST)
            if form.is_valid():
                form.save()
                # return HttpResponseRedirect(reverse("component"))  # Redirect after successful creation
        else:
            form = AssemblyForm()  # Blank form for new component creation


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
