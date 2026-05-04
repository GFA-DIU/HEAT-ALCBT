from django.db.models.signals import post_delete, post_save
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


def _refresh_summary(building):
    # Guard: if the building is being cascade-deleted, its PK may no longer
    # exist in the DB. Attempting get_or_create in that case causes a FK
    # violation. Skip the refresh — the EnergySummary will be removed by
    # CASCADE anyway.
    if not Building.objects.filter(pk=building.pk).exists():
        return
    summary, _ = EnergySummary.objects.get_or_create(building=building)
    summary.recalculate()
    summary.save()


def _register(model):
    @receiver(post_save, sender=model, weak=False)
    def on_save(sender, instance, **kwargs):
        _refresh_summary(instance.building)

    @receiver(post_delete, sender=model, weak=False)
    def on_delete(sender, instance, **kwargs):
        _refresh_summary(instance.building)


for _model in _SYSTEM_MODELS:
    _register(_model)
