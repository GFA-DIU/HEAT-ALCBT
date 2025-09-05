import logging

from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponseServerError

from pages.forms.assembly_form import AssemblyForm
from pages.forms.boq_assembly_form import BOQAssemblyForm
from pages.models.assembly import Assembly, AssemblyCategoryTechnique, StructuralProduct
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.models.epd import EPD, EPDImpact

logger = logging.getLogger(__name__)


@transaction.atomic
def save_assembly(
    request,
    assembly: Assembly,
    building_instance: Building,
    simulation=False,
    is_boq=False,
) -> None:
    # Save to BuildingAssembly or -Simulated, depending on Mode
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
    else:
        BuildingAssemblyModel = BuildingAssembly
    assembly_form = BOQAssemblyForm if is_boq else AssemblyForm
    # Bind the form to the existing Assembly instance
    form = assembly_form(
        request.POST,
        instance=assembly,
        building_id=building_instance.pk,
        simulation=simulation,
    )

    try:
        if form.is_valid():
            selected_epds = parse_selected_epds(request)

            # DB OPERATIONS
            assembly = form.save()  # Save the updated Assembly instance
            assembly.is_boq = is_boq
            assembly.created_by = request.user
            assembly.save()

            StructuralProduct.objects.filter(
                assembly=assembly
            ).delete()  # create a clean slate

            # Save to products
            for _, v in selected_epds.items():
                classification = AssemblyCategoryTechnique.objects.get(
                    category_id=v.get("category"),
                    technique_id=v.get("technique") or None,
                )
                StructuralProduct.objects.create(
                    epd_id=v.get("epd_id"),
                    assembly=assembly,
                    quantity=v.get("quantity"),
                    input_unit=v.get("unit"),
                    description=v.get("description"),
                    classification=classification,
                )

            BuildingAssemblyModel.objects.update_or_create(
                building=building_instance,
                assembly=assembly,
                defaults={
                    "quantity": request.POST.get(
                        "quantity", 1
                    ),  # Get quantity from POST data
                    "reporting_life_cycle": request.POST.get(
                        "reporting_life_cycle", 50
                    ),  # Get reporting_life_cycle from POST data, default to 50
                },
            )
        else:
            logger.error(
                "Submit failed for user %s because form is invalid, with these errors: %s",
                request.user,
                form.errors,
            )
            raise HttpResponseServerError()
    except Exception:
        logger.exception(
            "Saving assemby %s for building %s failed",
            assembly.pk,
            building_instance.pk,
        )
        raise HttpResponseServerError()


def parse_selected_epds(request) -> tuple[dict, dict[str, EPD]]:
    """Get user input and db info for selected EPDs."""
    # Identify selected EPDs
    selected_epds = {}
    # If struct. component classification comes from assembly. If BOQ classification comes from epd
    for key, value in request.POST.items():
        if key.startswith("material_") and "_quantity" in key:
            key_array = key.split("_")
            epd_id = key_array[1]
            timestamp = key_array[-1]
            selected_epds[epd_id + timestamp] = {
                "epd_id": epd_id,
                "quantity": float(value),
                "unit": request.POST[f"material_{epd_id}_unit_{timestamp}"],
                "description": request.POST[
                    f"material_{epd_id}_description_{timestamp}"
                ],
                "category": request.POST.get(f"material_{epd_id}_category_{timestamp}")
                or request.POST.get("assembly_category"),
                "technique": request.POST.get("assembly_technique", None),
            }

    return selected_epds
