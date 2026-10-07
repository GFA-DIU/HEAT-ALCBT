from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from pages.models.building import Building
from pages.models.building_operation.air_conditioning import CoolingSystemAirConditioner
from pages.models.building_operation.chilling import CoolingSystemChiller
from pages.models.building_operation.energy_summary import EnergySummary
from pages.models.building_operation.general_systems import LiftEscalatorSystem
from pages.models.building_operation.hot_water import HotWaterSystem
from pages.models.building_operation.lighting import LightingSystem
from pages.models.building_operation.ventilation import VentilationSystem

_SYSTEM_MODELS = (
    CoolingSystemAirConditioner,
    CoolingSystemChiller,
    VentilationSystem,
    LightingSystem,
    LiftEscalatorSystem,
    HotWaterSystem,
)


# Buildings currently being deleted. A system's post_delete fires while its
# parent is still on its way out, and must not write anything back.
_deleting_buildings = set()


def _refresh_summary(building, create=True):
    """Recompute a building's EnergySummary.

    `create=False` is used from delete handlers. Deleting one system should
    refresh an existing summary, but must never *create* one, because during a
    building cascade there is nothing left to summarise.

    Why the plain existence check was not enough: Django puts EnergySummary in
    `Collector.fast_deletes`, so it is bulk-deleted BEFORE the per-model deletes
    that fire signals. By the time LiftEscalatorSystem.post_delete runs, the
    summary row is already gone but the Building row is not - the old guard
    passed, get_or_create resurrected the summary, and deleting the building
    then violated the foreign key. This broke building deletion in the app and
    five test modules.
    """
    if building is None or building.pk in _deleting_buildings:
        return
    if not Building.objects.filter(pk=building.pk).exists():
        return

    if create:
        summary, _ = EnergySummary.objects.get_or_create(building=building)
    else:
        summary = EnergySummary.objects.filter(building=building).first()
        if summary is None:
            return

    summary.recalculate()
    summary.save()


@receiver(pre_delete, sender=Building, weak=False)
def _building_deleting(sender, instance, **kwargs):
    _deleting_buildings.add(instance.pk)


@receiver(post_delete, sender=Building, weak=False)
def _building_deleted(sender, instance, **kwargs):
    _deleting_buildings.discard(instance.pk)


def _register(model):
    @receiver(post_save, sender=model, weak=False)
    def on_save(sender, instance, **kwargs):
        _refresh_summary(instance.building)

    @receiver(post_delete, sender=model, weak=False)
    def on_delete(sender, instance, **kwargs):
        _refresh_summary(instance.building, create=False)


for _model in _SYSTEM_MODELS:
    _register(_model)
