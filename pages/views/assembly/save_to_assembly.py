from django.db.models import Prefetch

from pages.forms.assembly_form import AssemblyForm
from pages.models.assembly import Assembly, Product
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.models.epd import EPD, EPDImpact


def save_assembly(request, assembly: Assembly, building_instance: Building, simulation=None) -> None:
    # Save to BuildingAssembly or -Simulated, depending on Mode
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
    else:
        BuildingAssemblyModel = BuildingAssembly
    
    # Bind the form to the existing Assembly instance
    form = AssemblyForm(request.POST, instance=assembly, building_id=building_instance.pk, simulation=simulation)
    if form.is_valid():
        selected_epds, epd_map = parse_selected_epds(request)

        # DB OPERATIONS
        assembly = form.save() # Save the updated Assembly instance

        Product.objects.filter(assembly=assembly).delete()  # create a clean slate
        
        # Save to products
        for k, v in selected_epds.items():
            Product.objects.create(
                epd=epd_map[k],
                assembly=assembly,
                quantity=v.get("quantity"),
                input_unit=v.get("unit"),
            )
        
        BuildingAssemblyModel.objects.update_or_create(
            building=building_instance,
            assembly=assembly,
            defaults={
                "quantity": request.POST.get("quantity", 0),  # Get quantity from POST data
            }
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
    return selected_epds,epd_map