import logging

from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponseServerError

from pages.forms.assembly_form import AssemblyForm
from pages.models.assembly import Assembly, Product
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.models.epd import EPD, EPDImpact

logger = logging.getLogger(__name__)


@transaction.atomic
def save_assembly(
    request,
    assembly: Assembly,
    building_instance: Building,
    simulation=None,
    assembly_form=AssemblyForm,
) -> None:
    # Save to BuildingAssembly or -Simulated, depending on Mode
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
    else:
        BuildingAssemblyModel = BuildingAssembly

    # Bind the form to the existing Assembly instance
    form = assembly_form(
        request.POST,
        instance=assembly,
        building_id=building_instance.pk,
        simulation=simulation,
    )

    try:
        if form.is_valid():
            selected_epds, epd_map = parse_selected_epds(request)

            # DB OPERATIONS
            assembly = form.save()  # Save the updated Assembly instance
            assembly.created_by = request.user
            assembly.save()

            Product.objects.filter(assembly=assembly).delete()  # create a clean slate

            # Save to products
            for k, v in selected_epds.items():
                Product.objects.create(
                    epd=epd_map[k],
                    assembly=assembly,
                    quantity=v.get("quantity"),
                    input_unit=v.get("unit"),
                    description=v.get("description"),
                )

            BuildingAssemblyModel.objects.update_or_create(
                building=building_instance,
                assembly=assembly,
                defaults={
                    "quantity": request.POST.get(
                        "quantity"
                    ),  # Get quantity from POST data
                    "reporting_life_cycle": request.POST.get(
                        "reporting_life_cycle"
                    ),  # Get reporting_life_cycle from POST data
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


def parse_selected_epds(request) -> tuple[dict, dict[str, EPD]]:
    """Get user input and db info for selected EPDs."""
    # Identify selected EPDs
    selected_epds = {}
    for key, value in request.POST.items():
        if key.startswith("material_") and "_quantity" in key:
            epd_id = key.split("_")[1]
            selected_epds[epd_id] = {
                "quantity": float(value),
                "unit": request.POST[f"material_{epd_id}_unit"],
                "description": request.POST[f"material_{epd_id}_description"],
            }

    # Pre-fetch EPDImpact and Impact objects
    epds = EPD.objects.filter(pk__in=selected_epds.keys()).prefetch_related(
        Prefetch(
            "epdimpact_set",
            queryset=EPDImpact.objects.select_related("impact"),
            to_attr="prefetched_impacts",
        )
    )
    epd_map = {str(epd.id): epd for epd in epds}
    return selected_epds, epd_map
