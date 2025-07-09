import logging

from django.http import HttpResponseServerError

from pages.views.building.building_dashboard.assembly_dashboard import building_dashboard_assembly
from pages.views.building.building_dashboard.material_dashboard import building_dashboard_material

logger = logging.getLogger(__name__)


def get_building_dashboard(user, building_id, dashboard_type: str, simulation: bool):
    logger.info("Dashboard type is: %s", dashboard_type)
    if dashboard_type == "assembly":
        return building_dashboard_assembly(user, building_id, simulation)
    elif dashboard_type == "material":
        return building_dashboard_material(user, building_id, simulation)
    else:
        logger.info("Dashboard type not defined", user, building_id, dashboard_type)
        return HttpResponseServerError()


