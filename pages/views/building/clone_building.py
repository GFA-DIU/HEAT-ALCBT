"""Deep-copy a Building into a new one.

Used to (a) seed example buildings and (b) power the user-facing "Start from this
example" flow: the source (an example) is cloned into a brand-new, independent
building owned by the target user. Nothing in the source is modified.

Copies: the Building record (new id + uuid), its structural components
(BuildingAssembly -> a fresh Assembly -> its StructuralProducts), operational
products, and the operational systems + energy summary. Simulated components are
intentionally not copied.
"""

import uuid
import logging

from django.db import transaction

from pages.models.building import Building, BuildingAssembly, OperationalProduct
from pages.models.assembly import Assembly, StructuralProduct
from pages.models.building_operation.operational_information import BuildingOperation
from pages.models.building_operation.energy_summary import EnergySummary
from pages.models.building_operation.air_conditioning import CoolingSystemAirConditioner
from pages.models.building_operation.chilling import CoolingSystemChiller
from pages.models.building_operation.hot_water import HotWaterSystem
from pages.models.building_operation.general_systems import LiftEscalatorSystem
from pages.models.building_operation.lighting import LightingSystem
from pages.models.building_operation.ventilation import VentilationSystem

logger = logging.getLogger(__name__)

# building-FK leaf tables copied verbatim (new PK, repointed to the new building)
_LEAF_CHILD_MODELS = [
    OperationalProduct,
    BuildingOperation,
    EnergySummary,
    CoolingSystemAirConditioner,
    CoolingSystemChiller,
    HotWaterSystem,
    LiftEscalatorSystem,
    LightingSystem,
    VentilationSystem,
]


@transaction.atomic
def clone_building(source, user, new_name, *, as_example=False, variant=None, public=None):
    """Return a new Building deep-copied from ``source``.

    as_example/variant/public control the copy's flags. For a user "start from
    example" clone, leave them default (a private, editable, non-example building).
    """
    new = Building.objects.get(pk=source.pk)
    new.pk = uuid.uuid4()          # BaseModel PK is a UUID
    new.uuid = uuid.uuid4()        # separate public building UUID
    new._state.adding = True
    new.created_by = user
    new.name = new_name
    new.is_example = as_example
    new.example_variant = variant if as_example else None
    new.public = as_example if public is None else public
    new.draft = False
    new.organisation = None        # never carry the source's org into a clone
    new.save()

    # Structural components: clone each Assembly + its StructuralProducts, then link.
    for ba in BuildingAssembly.objects.filter(building=source).select_related("assembly"):
        original_assembly_id = ba.assembly.pk
        asm = Assembly.objects.get(pk=original_assembly_id)
        asm.pk = None
        asm._state.adding = True
        asm.created_by = user
        asm.save()
        for sp in StructuralProduct.objects.filter(assembly_id=original_assembly_id):
            StructuralProduct.objects.create(
                description=sp.description,
                epd=sp.epd,
                input_unit=sp.input_unit,
                assembly=asm,
                quantity=sp.quantity,
                classification=sp.classification,
            )
        BuildingAssembly.objects.create(
            assembly=asm,
            building=new,
            quantity=ba.quantity,
            reporting_life_cycle=ba.reporting_life_cycle,
        )

    # Operational products + systems + energy summary: verbatim copy repointed to new.
    for model in _LEAF_CHILD_MODELS:
        for obj in model.objects.filter(building=source):
            obj.pk = None
            obj._state.adding = True
            obj.building = new
            obj.save()

    return new
