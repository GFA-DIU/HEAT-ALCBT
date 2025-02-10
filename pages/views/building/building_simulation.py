import logging

from django.db import transaction
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from pages.models.assembly import AssemblyMode, Assembly, Product
from pages.models.building import BuildingAssembly, BuildingAssemblySimulated
from pages.views.building.building import handle_building_load
from pages.views.building.building import handle_assembly_delete


logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def building_simulation(request, building_id):
    logger.info(
        "Building Simulation - Request method: %s, user: %s",
        request.method,
        request.user,
    )

    if request.method == "DELETE":
        return handle_assembly_delete(request, building_id, simulation=True)

    elif request.method == "POST" and request.POST.get("action") == "reset":
        return handle_simulation_reset(building_id)

    # Full reload
    else:
        context, form, detailedForm = handle_building_load(
            request, building_id, simulation=True
        )

        if not context["structural_components"]:
            return handle_simulation_reset(building_id)

        # disable the form fields and button
        for field in form.fields:
            form.fields[field].disabled = True
        for field in detailedForm.fields:
            detailedForm.fields[field].disabled = True
        if hasattr(form.helper.layout[3], "flat_attrs"):
            form.helper.layout[3].flat_attrs = "disabled"
        if hasattr(detailedForm.helper.layout[3], "flat_attrs"):
            detailedForm.helper.layout[3].flat_attrs = "disabled"

        context["form_general_info"] = form
        context["form_detailed_info"] = detailedForm

    context["simulation"] = True
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building_simulation.html", context)


@transaction.atomic
def handle_simulation_reset(building_id):
    ##### create clean slate
    # Fetch the simulated assemblies for the given building
    simulated_buildingassemblies = BuildingAssemblySimulated.objects.filter(
        building__id=building_id
    )

    # Find and delete associated assemblies with AssemblyMode.CUSTOM
    sim_custom_assemblies = Assembly.objects.filter(
        id__in=simulated_buildingassemblies.values_list("assembly_id", flat=True),
        mode=AssemblyMode.CUSTOM,
    )

    try:
        sim_custom_assemblies.delete()

        # Clear existing simulated assemblies
        simulated_buildingassemblies.delete()

        ###### Create from Building Assembly
        normal_assemblies = BuildingAssembly.objects.filter(building__id=building_id)

        if not normal_assemblies:
            # simulation is not possible if there is no normal set-up
            return redirect("building", building_id=building_id)

        for a in normal_assemblies:
            # For custom assemblies, clone the original
            if a.assembly.mode == AssemblyMode.CUSTOM:
                # https://docs.djangoproject.com/en/5.1/topics/db/queries/#copying-model-instances
                original_assembly_id = a.assembly.pk
                a.assembly.pk = None
                a.assembly._state.adding = True
                a.assembly.save()

                # Clone associated Products
                for product in Product.objects.filter(
                    assembly__id=original_assembly_id
                ):
                    Product.objects.create(
                        description=product.description,
                        epd=product.epd,
                        input_unit=product.input_unit,
                        assembly=a.assembly,  # Use the new cloned assembly
                        quantity=product.quantity,
                    )

            BuildingAssemblySimulated.objects.create(
                assembly=a.assembly, building=a.building, quantity=a.quantity
            )
    except Exception:
        logger.exception(
            "Resetting the simulation failed for building %s failed", building_id
        )

    # Do a full page reload
    return redirect("building_simulation", building_id=building_id)
