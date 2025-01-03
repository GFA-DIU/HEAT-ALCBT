from django.db.models import Prefetch,  Q

from pages.forms.assembly_form import AssemblyForm
from pages.models.assembly import Assembly, Product
from pages.models.building import Building, BuildingAssembly
from pages.models.epd import EPD, EPDImpact


def save_assembly(request, assembly: Assembly, building_instance: Building):
    print("This is a form submission")
    print(request.POST)
    # Bind the form to the existing Assembly instance
    form = AssemblyForm(request.POST, instance=assembly, building_id=building_instance.pk)
    if form.is_valid():
        # Save the updated Assembly instance
        assembly = form.save()

        # Create clean slate
        Product.objects.filter(assembly=assembly).delete()

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
        # Save to products
        # TODO: Does this undermine the pre-fetching of the EPD data?
        products = []
        for k, v in selected_epds.items():
            products.append(
                Product.objects.create(
                    epd=epd_map[k],
                    assembly=assembly,
                    quantity=v.get("quantity"),
                    input_unit=v.get("unit"),
                )
            )
        
        # It doesn't duplicate if the assembly already is in structural_components
        BuildingAssembly.objects.update_or_create(
            building=building_instance,
            assembly=assembly,
            defaults={
                "quantity": request.POST.get("quantity", 0),  # Get quantity from POST data
            }
        )