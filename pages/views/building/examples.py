"""Example / reference buildings — user-facing UI.

Read-only, system-owned reference buildings (``Building.is_example=True``) that a
user can preview and then clone into their own editable building.

Three endpoints:
  * ``examples_list``       — the "Example buildings" area: cards grouped by
                              building type + country (Typical + Low-carbon).
  * ``example_preview``     — a read-only preview of one example (no edit controls)
                              with a prominent "Start from this example" button.
  * ``start_from_example``  — POST: deep-copies the example into the current user's
                              account (private, editable) and redirects into it.

Examples are deliberately NOT reachable through the normal editable building view
(which is scoped to ``created_by=request.user``); these views load them by pk with
``is_example=True`` and never mutate them.
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from pages.models.assembly import StructuralProduct
from pages.models.building import Building, BuildingAssembly
from pages.models.epd import EPDImpact
from pages.views.building.building import get_assemblies
from pages.views.building.building_stats import calculate_total_embodied_carbon
from pages.views.building.clone_building import clone_building

logger = logging.getLogger(__name__)


# Order variants Typical then Low-carbon for consistent card layout.
_VARIANT_ORDER = {Building.EXAMPLE_TYPICAL: 0, Building.EXAMPLE_LOW_CARBON: 1}


def _example_qs():
    """All example buildings, richest-relation prefetch for structure + stats."""
    return (
        Building.objects.filter(is_example=True)
        .select_related("category", "category__category", "country")
        .prefetch_related(
            Prefetch(
                "buildingassembly_set",
                queryset=BuildingAssembly.objects.select_related("assembly")
                .order_by("-assembly__created_at")
                .prefetch_related(
                    Prefetch(
                        "assembly__structuralproduct_set",
                        queryset=StructuralProduct.objects.select_related(
                            "epd", "classification"
                        ).prefetch_related(
                            Prefetch(
                                "epd__epdimpact_set",
                                queryset=EPDImpact.objects.select_related("impact"),
                                to_attr="all_impacts",
                            ),
                            "epd__category",
                            "classification__category",
                        ),
                        to_attr="prefetched_products",
                    ),
                ),
                to_attr="prefetched_components",
            ),
        )
    )


@login_required
@require_http_methods(["GET"])
def examples_list(request):
    """The Example buildings area: cards grouped by (building type, country)."""
    examples = list(_example_qs())
    for b in examples:
        # Only embodied carbon is shown on the cards; compute just that, reusing the
        # already-prefetched components so we don't re-query per building.
        b.embodied_carbon = calculate_total_embodied_carbon(
            b, prefetched_assemblies=b.prefetched_components
        )

    # Group by (type name, country name) -> {typical, low_carbon}
    groups = {}
    for b in examples:
        type_name = b.category.category.name if b.category and b.category.category else "-"
        country_name = b.country.name if b.country else "-"
        key = (type_name, country_name)
        groups.setdefault(
            key,
            {
                "type_name": type_name,
                "country_name": country_name,
                "country_code2": b.country.code2 if b.country else "",
                "variants": [],
            },
        )["variants"].append(b)

    grouped = sorted(groups.values(), key=lambda g: (g["type_name"], g["country_name"]))
    for g in grouped:
        g["variants"].sort(key=lambda b: _VARIANT_ORDER.get(b.example_variant, 99))

    logger.info("User %s viewed the examples area (%d examples).", request.user, len(examples))
    return render(request, "pages/examples/examples.html", {"grouped_examples": grouped})


@login_required
@require_http_methods(["GET"])
def example_preview(request, building_id):
    """Read-only preview of a single example building."""
    building = get_object_or_404(_example_qs(), pk=building_id)

    structural_components, _ = get_assemblies(building.prefetched_components)
    embodied_carbon = calculate_total_embodied_carbon(
        building, prefetched_assemblies=building.prefetched_components
    )

    # Display-only cleanup for the preview table: classification without its numeric
    # code ("120 - Finishes" -> "Finishes") and units in standard notation.
    _unit_display = {"m^2": "m²", "m^3": "m³", "m": "m", "kg": "kg", "ton": "t", "pcs": "pcs"}
    for c in structural_components:
        cls = c.get("assembly_classification")
        c["classification_display"] = getattr(cls, "name", None) or (str(cls) if cls else "-")
        c["unit_display"] = _unit_display.get(c.get("unit"), c.get("unit") or "")

    context = {
        "building": building,
        "structural_components": structural_components,
        "embodied_carbon": embodied_carbon,
        "type_name": building.category.category.name
        if building.category and building.category.category
        else "-",
        "country_name": building.country.name if building.country else "-",
    }
    return render(request, "pages/examples/example_preview.html", context)


@login_required
@require_http_methods(["POST"])
def start_from_example(request, building_id):
    """Deep-copy an example into the user's account and redirect into the copy."""
    source = get_object_or_404(Building.objects.filter(is_example=True), pk=building_id)

    type_name = (
        source.category.category.name
        if source.category and source.category.category
        else "Building"
    )
    country_name = source.country.name if source.country else ""
    variant_label = dict(Building.EXAMPLE_VARIANT_CHOICES).get(source.example_variant, "")
    new_name = f"My {type_name}"
    if variant_label and country_name:
        new_name = f"My {type_name} (from {variant_label} {country_name} example)"

    new_building = clone_building(source, request.user, new_name=new_name)

    logger.info(
        "User %s started from example %s -> new building %s",
        request.user, source.pk, new_building.pk,
    )
    messages.info(
        request,
        "This is your own editable copy. The example stays unchanged.",
    )
    return redirect("building", building_id=new_building.id)
