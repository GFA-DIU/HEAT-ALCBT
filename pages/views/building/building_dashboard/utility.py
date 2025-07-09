import logging

from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
import pandas as pd

from pages.models.assembly import StructuralProduct
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated, OperationalProduct, SimulatedOperationalProduct
from pages.models.epd import EPDImpact
from pages.views.building.building import get_assemblies
from pages.views.building.operational_products.operational_products import serialize_operational_products

logger = logging.getLogger(__name__)


def prep_building_dashboard_df(user, building_id, simulation):
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
        relation_name = "buildingassemblysimulated_set"
        BuildingProductModel = SimulatedOperationalProduct
        op_relation_name = "simulated_operational_products"
    else:
        BuildingAssemblyModel = BuildingAssembly
        relation_name = "buildingassembly_set"
        BuildingProductModel = OperationalProduct
        op_relation_name = "operational_products"


    building = get_object_or_404(
        Building.objects
            .filter(created_by=user)
            .prefetch_related(
                # 1) grab each BuildingAssemblyModel …
                Prefetch(
                    relation_name,
                    queryset=BuildingAssemblyModel.objects
                        .filter(building__created_by=user)
                        .select_related("assembly")     # pull in the Assembly
                        .prefetch_related(
                            # 2) … and on *each* BuildingAssemblyModel, pull its assembly's products …
                            Prefetch(
                                "assembly__structuralproduct_set",
                                queryset=StructuralProduct.objects
                                    .select_related("epd", "classification")
                                    .prefetch_related(
                                        # 3) fetch EPD impacts…
                                        Prefetch(
                                            "epd__epdimpact_set",
                                            queryset=EPDImpact.objects.select_related("impact"),
                                            to_attr="all_impacts",
                                        ),
                                        # 4) and EPD/category, classification/category
                                        "epd__category",
                                        "classification__category",
                                    ),
                                to_attr="prefetched_products",
                            ),
                        ),
                    to_attr="prefetched_components",
                ),
                # 5) plus any operational products
                Prefetch(
                    op_relation_name,
                    queryset=BuildingProductModel.objects
                        .filter(building__created_by=user)
                        .select_related("epd")     # pull in the Assembly
                        .prefetch_related(
                            Prefetch(
                                "epd__epdimpact_set",
                                queryset=EPDImpact.objects.select_related("impact"),
                                to_attr="all_impacts",
                            ),
                            # 4) and EPD/category, classification/category
                            "epd__category",
                        ),
                    to_attr="prefetched_operational_products",
                ),
            ),
        pk=building_id,
    )

    # Build structural and operational components and impacts in one step
    structural_components, impact_list = get_assemblies(building.prefetched_components)
    operational_impact_list = serialize_operational_products(building.prefetched_operational_products)
    reference_period = building.reference_period

    if not structural_components and not operational_impact_list:
        return HttpResponse()
    elif not structural_components:
        df = prep_operational_df(operational_impact_list, reference_period)
    elif not operational_impact_list:
        df = prep_structural_df(impact_list)
    elif operational_impact_list and structural_components:
        
        df = prep_structural_df(impact_list)
    
        # operational df
        df_op = prep_operational_df(operational_impact_list, reference_period)

        df = pd.concat([df, df_op], axis=0)[["assembly_category", "material_category", "gwp", "penrt", "type"]]
    return df


def prep_operational_df(operational_impact_list, reference_period):
    df_op = pd.DataFrame.from_records(operational_impact_list)
    df_op["material_category"] = df_op["category"].apply(lambda x: x.__str__())
    df_op["type"] = "operational"
    df_op["assembly_category"] = "Operational Carbon"
    df_op["year"] = reference_period
    df_op["gwp_b6"] = df_op["gwp_b6"] * df_op["year"]
    df_op.rename(columns={"gwp_b6": "gwp", "penrt_b6": "penrt"}, inplace=True)
    return df_op


def prep_structural_df(impact_list):
    df = pd.DataFrame.from_records(impact_list)
    df["impact_type"] = df["impact_type"].apply(lambda x: x.__str__())
    df["assembly_category"] = df["assembly_category"].apply(lambda x: x.__str__())
    df["material_category"] = df["material_category"].apply(lambda x: x.__str__())
    df = df[df["impact_type"].isin(["gwp a1a3", "penrt a1a3"])]
    df = df.pivot_table(
            index=["assembly_id", "epd_id", "assembly_category", "material_category"],
            columns="impact_type",
            values="impact_value",
            aggfunc="sum",         # sum duplicates
        ).reset_index()

        
        # Decision to only display positive values for embodied carbon and embodied energy, yet indicator below still shows sum.
        # Thus creating a new column
    df["gwp a1a3 pos"] = df["gwp a1a3"]
    df.loc[df["gwp a1a3 pos"] <= 0, "gwp a1a3 pos"] = 0
    df["penrt a1a3 pos"] = df["penrt a1a3"]
    df.loc[df["penrt a1a3 pos"] <= 0, "penrt a1a3 pos"] = 0
    df["type"] = "structural"
    df.rename(columns={"gwp a1a3 pos": "gwp", "penrt a1a3 pos": "penrt"}, inplace=True)
    return df


def _generate_discrete_colors(
    start_color=(242, 103, 22), end_color=(255, 247, 237), n=5
):
    """
    Generate a list of n discrete colors evenly spaced between start_color and end_color.

    Parameters
    ----------
    start_color : tuple
        A tuple of (R, G, B) for the start color. Each channel should be 0-255.
    end_color : tuple
        A tuple of (R, G, B) for the end color. Each channel should be 0-255.
    n : int
        Number of discrete colors to generate.

    Returns
    -------
    list of str
        A list of n RGB color strings in the format 'rgb(R,G,B)'.
    """
    colors = []
    for i in range(n):
        # Determine fraction along the gradient
        fraction = i / (n - 1) if n > 1 else 0

        # Interpolate each channel
        r = int(start_color[0] + fraction * (end_color[0] - start_color[0]))
        g = int(start_color[1] + fraction * (end_color[1] - start_color[1]))
        b = int(start_color[2] + fraction * (end_color[2] - start_color[2]))

        colors.append(f"rgb({r},{g},{b})")
    return colors

