import pandas as pd
import logging

from plotly.offline import plot
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseServerError

from django.shortcuts import get_object_or_404

from pages.models.assembly import StructuralProduct
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated, OperationalProduct, SimulatedOperationalProduct
from pages.models.epd import EPDImpact
from pages.views.building.building import get_assemblies
from pages.views.building.operational_products.operational_products import serialize_operational_products

logger = logging.getLogger(__name__)


def get_building_dashboard(user, building_id, dashboard_type: str, simulation: bool):
    if dashboard_type == "assembly":
        return building_dashboard_assembly(user, building_id, simulation)
    elif dashboard_type == "material":
        return building_dashboard_material(user, building_id, simulation)
    else:
        logger.info("Dashboard type not defined", user, building_id, dashboard_type)
        return HttpResponseServerError()


def building_dashboard_material(user, building_id, simulation):
    **"""
    UPDATED: Material view shows ONLY embodied carbon distributed by materials
    No operational carbon included in material view
    """**
    df = prep_building_dashboard_df(user, building_id, simulation)
    
    **# ADDED: Filter to only structural (embodied) carbon - NO operational carbon
    df_embodied_only = df[df["type"] == "structural"].copy()**
    
    return _building_dashboard_base(**df_embodied_only**, "material_category")


def building_dashboard_assembly(user, building_id, simulation):
    df = prep_building_dashboard_df(user, building_id, simulation)

    df["category_short"] = df["assembly_category"]
    df.loc[df["type"] == "structural", "category_short"] = df.loc[df["type"] == "structural", "assembly_category"].str.split("- ").str[1]
    df.loc[df["category_short"] == "Intermediate Floor Construction", "category_short"] = "Interm. Floor"
    df.loc[df["category_short"] == "Bottom Floor Construction", "category_short"] = "Bottom Floor"
    df.loc[df["category_short"] == "Roof Construction", "category_short"] = "Roof Const."
    
    # Aggregation for pie chart
    op_gwp_sum = df.loc[df["type"] == "operational", "gwp"].sum()
    op_penrt_sum = df.loc[df["type"] == "operational", "penrt"].sum()
    operational_row = {'category_short': 'Operational carbon', "gwp": op_gwp_sum, "penrt": op_penrt_sum, "type": "operational"}
    st_gwp_sum = df.loc[df["type"] == "structural", "gwp"].sum()
    st_penrt_sum = df.loc[df["type"] == "structural", "penrt"].sum()
    structural_row = {'category_short': 'Embodied carbon', "gwp": st_gwp_sum, "penrt": st_penrt_sum, "type": "structural"}
    df_list = [structural_row, operational_row]
    df_pie = pd.DataFrame(data=df_list)
    
    # Shorten df for bar chart
    df_filtered = df[df["type"] == "structural"]
    df_bar = df_filtered.groupby('category_short')['gwp'].sum().reset_index(name='gwp_abs')
    df_bar['gwp_per'] = df_bar['gwp_abs'] / df_bar['gwp_abs'].sum() * 100
    df_bar = df_bar.sort_values("gwp_per", ascending=False)

    return _building_dashboard_assembly(df_pie, df_bar, "category_short")


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

def prep_structural_df(impact_list):
    df = pd.DataFrame.from_records(impact_list)
    df["impact_type"] = df["impact_type"].apply(lambda x: x.__str__())
    df["assembly_category"] = df["assembly_category"].apply(lambda x: x.__str__())
    df["material_category"] = df["material_category"].apply(lambda x: x.__str__())
    df = df[df["impact_type"].isin(["gwp a1a3", "penrt a1a3"])]
    df = df.pivot(
            index=["assembly_id", "epd_id", "assembly_category", "material_category"],
            columns="impact_type",
            values="impact_value",
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

def prep_operational_df(operational_impact_list, reference_period):
    df_op = pd.DataFrame.from_records(operational_impact_list)
    df_op["material_category"] = df_op["category"].apply(lambda x: x.__str__())
    df_op["type"] = "operational"
    df_op["assembly_category"] = "Operational Carbon"
    df_op["year"] = reference_period
    df_op["gwp_b6"] = df_op["gwp_b6"] * df_op["year"]
    df_op.rename(columns={"gwp_b6": "gwp", "penrt_b6": "penrt"}, inplace=True)
    return df_op


**def _map_material_categories(df):
    """
    NEW FUNCTION: Maps 336+ detailed material categories to 9 main categories
    Based on the exact mapping provided in the Excel file
    """
    
    # Define the exact mapping dictionary from the Excel file
    material_mapping = {
        'Cement': 'Ready-mix concrete and cement',
        'Lime': 'Masonry',
        'Gypsum': 'Finishing materials',
        'Clay': 'Masonry',
        'Sand and gravel': 'Masonry',
        'Natural stone': 'Masonry',
        'Pumice': 'Others',
        'Expanded clay': 'Masonry',
        'Expanded shale': 'Others',
        'Granulated foam glass': 'Insulation materials',
        'Perlite': 'Others',
        'Byproducts from power plant': 'Others',
        'Puzzolan': 'Others',
        'Dry filling material': 'Others',
        'Sand lime brick': 'Masonry',
        'Fired brick': 'Masonry',
        'Aerated concrete': 'Masonry',
        'Light concrete': 'Ready-mix concrete and cement',
        'Precast concrete elements and goods': 'Pre-cast concrete',
        'Stoneware': 'Masonry',
        'Tiles and cladding panels': 'Finishing materials',
        'Natural cut stone': 'Masonry',
        'Slate': 'Finishing materials',
        'Ceramic roof tile': 'Finishing materials',
        'Concrete roof tiles': 'Pre-cast concrete',
        'Fibre Cement': 'Ready-mix concrete and cement',
        'Gypsum plasterboard': 'Finishing materials',
        'Dry screed': 'Finishing materials',
        'Ceiling panel': 'Finishing materials',
        'Glass block': 'Masonry',
        'Air-dried brick (adobe)': 'Masonry',
        'Fire protection board': 'Others',
        'Substrate': 'Others',
        'Artificial stone': 'Masonry',
        'Ready mixed concrete': 'Ready-mix concrete and cement',
        'Mortar (masonry)': 'Ready-mix concrete and cement',
        'Screed dry mortar': 'Ready-mix concrete and cement',
        'Renders and plasters': 'Ready-mix concrete and cement',
        'Adhesive and adhesive mortar': 'Ready-mix concrete and cement',
        'Concrete additive': 'Ready-mix concrete and cement',
        'Split mastic asphalt': 'Others',
        'Mastic asphalt': 'Others',
        'Asphalt binder': 'Masonry',
        'Base courses': 'Others',
        'EoL plaster': 'Finishing materials',
        'EoL reinforcement': 'Ready-mix concrete and cement',
        'Inorganic pigments': 'Others',
        'Mineral wool': 'Insulation materials',
        'Glass wool': 'Insulation materials',
        'Rock wool': 'Insulation materials',
        'EPS white': 'Insulation materials',
        'EPS grey': 'Insulation materials',
        'EPS grey-white': 'Insulation materials',
        'XPS white': 'Insulation materials',
        'PU with aluminium': 'Aluminium and other metals',
        'PU with mineral fibre': 'Others',
        'PU slabstock foam': 'Insulation materials',
        'PIR rigid foam': 'Insulation materials',
        'Phenolic foam boards': 'Insulation materials',
        'Panels': 'Others',
        'Granulate': 'Others',
        'Wood wool panels': 'Wood/Timber',
        'Expanded cork': 'Others',
        'Wood fibre insulation boards': 'Wood/Timber',
        'Wood fibre and wood chips, loose': 'Wood/Timber',
        'Cellulose insulation (loose fill)': 'Insulation materials',
        'Cellulose insulation (panels)': 'Insulation materials',
        'Flax fibre mat': 'Insulation materials',
        'Hemp fibre mat': 'Insulation materials',
        'Conventional Cotton': 'Others',
        'Organic cotton': 'Others',
        'Urea-formaldehyde foam insulation (UFFI)': 'Insulation materials',
        'Melamine foam': 'Insulation materials',
        'Foam': 'Insulation materials',
        'Calcium silicate': 'Others',
        'Thermal insulation composite system': 'Insulation materials',
        'ETICS dowel': 'Others',
        'ETICS completely': 'Others',
        'EoL wood fibre insulation boards': 'Wood/Timber',
        'EoL glass wool': 'Insulation materials',
        'EoL rock wool': 'Insulation materials',
        'EoL ETICS dowel': 'Others',
        'EoL ETICS': 'Others',
        'EoL EPS': 'Insulation materials',
        'EoL wood wool': 'Wood/Timber',
        'Straw bale': 'Others',
        'Straw panels': 'Others',
        'Vacuum insulation panels': 'Insulation materials',
        'Hydrophobic panels': 'Others',
        'Isokorb thermal breaks': 'Others',
        'mineral': 'Others',
        'Organic': 'Others',
        'Foamed concrete insulation panels': 'Ready-mix concrete and cement',
        'Structural timber': 'Wood/Timber',
        'Solid structural timber (KVH)': 'Wood/Timber',
        'Duo and trio laminated  beams': 'Others',
        'Glue-laminated timber': 'Wood/Timber',
        'Glue-laminated timber board': 'Wood/Timber',
        '3- and 5-ply wood': 'Wood/Timber',
        'Plywood': 'Wood/Timber',
        'Veneer layer wood': 'Wood/Timber',
        'Oriented strand board': 'Wood/Timber',
        'Laminated Veneer Lumber (LVL)': 'Wood/Timber',
        'Particle boards': 'Wood/Timber',
        'Wood fibre boards': 'Wood/Timber',
        'Wood cement boards': 'Wood/Timber',
        'Wood plastic composties': 'Wood/Timber',
        'Wood-based elements': 'Wood/Timber',
        'Laminate flooring': 'Finishing materials',
        'Parquet': 'Finishing materials',
        'Cork': 'Wood/Timber',
        'Multilayer Modular Floor Coverings': 'Others',
        'EoL particle boards': 'Wood/Timber',
        'EoL OSB': 'Others',
        'EoL general': 'Others',
        'EoL wood fibre board': 'Wood/Timber',
        'EoL laminate': 'Wood/Timber',
        'EoL laminated boards': 'Wood/Timber',
        'Acetylated wood': 'Wood/Timber',
        'Thermally modified timber': 'Wood/Timber',
        'Steel reinforing bar': 'Rebar',
        'Steel reinforcement mesh': 'Rebar',
        'Structural steel profile': 'Steel',
        'Steel sheets': 'Steel',
        'Cast or forged steel and iron items': 'Steel',
        'Fixing material': 'Others',
        'Stainless steel sheets': 'Steel',
        'Stainless steel profiles': 'Steel',
        'Stainless steel tap water tubes': 'Steel',
        'Fastener': 'Others',
        'Aluminium sheets': 'Aluminium and other metals',
        'Aluminium profiles': 'Aluminium and other metals',
        'Cast aluminium': 'Aluminium and other metals',
        'Aluminium foil': 'Aluminium and other metals',
        'Copper sheets': 'Aluminium and other metals',
        'Copper pipes': 'Aluminium and other metals',
        'Copper profiles': 'Aluminium and other metals',
        'Cast or forged copper and brass items': 'Aluminium and other metals',
        'Zinc sheets': 'Aluminium and other metals',
        'Lead sheets': 'Aluminium and other metals',
        'Anodising of aluminium': 'Aluminium and other metals',
        '(Wet) varnishing of metals': 'Others',
        'Powder coating': 'Finishing materials',
        'Zinc coating of steel': 'Aluminium and other metals',
        'EoL aluminium': 'Aluminium and other metals',
        'EoL stainless steel': 'Steel',
        'EoL copper sheets': 'Aluminium and other metals',
        'EoL copper sheets (bronze alloy)': 'Aluminium and other metals',
        'EoL copper sheets (gold alloy)': 'Aluminium and other metals',
        'EoL copper tube': 'Aluminium and other metals',
        'EoL sandwich elements': 'Aluminium and other metals',
        'EoL steel sheets': 'Steel',
        'EoL steel works': 'Steel',
        'EoL zinc sheets': 'Aluminium and other metals',
        'Primer for paints and plasters': 'Finishing materials',
        'Bituminous paint': 'Finishing materials',
        'Dispersion': 'Finishing materials',
        'Silicate dispersion': 'Finishing materials',
        'Silicone resin': 'Finishing materials',
        'Wall and ceiling covering': 'Finishing materials',
        'Interior paint': 'Finishing materials',
        'Dispersion glue': 'Finishing materials',
        'Varnish systems for wooden windows': 'Finishing materials',
        'Varnish systems for wooden facade': 'Finishing materials',
        'Parquet varnish': 'Finishing materials',
        'Varnish systems for metals': 'Finishing materials',
        'EoL primer': 'Finishing materials',
        'Reactive resin on epoxy basis': 'Finishing materials',
        'Reaction resin on polyurethane basis': 'Finishing materials',
        'Reaction resin on methacrylate basis': 'Finishing materials',
        'Interior and exterior coatings': 'Finishing materials',
        'Tab water tubes': 'Others',
        'Sewer tube': 'Others',
        'Rainwater/Grey water tubes': 'Others',
        'PVC flooring': 'Finishing materials',
        'Rubber flooring': 'Finishing materials',
        'Thermoplastic / Polyolefine flooring': 'Finishing materials',
        'Linoleum flooring': 'Finishing materials',
        'Textile flooring': 'Finishing materials',
        'Bituminous sheet': 'Finishing materials',
        'PVC sheet': 'Finishing materials',
        'Elastomer sheet': 'Finishing materials',
        'EVA sheet (Ehylene Vinyl Acetate)': 'Finishing materials',
        'TPO roofing membranes': 'Finishing materials',
        'Solar plastic sheeting': 'Finishing materials',
        'Dowel for sheetings': 'Others',
        'ECB roofing membrane (Ethylene Copolymer Bitumen)': 'Others',
        'PIB sheeting (Polyisobutylene)': 'Others',
        'Rigid plastic profiles': 'Others',
        'Elastic plastic profiles': 'Others',
        'Resin-composite facade panels': 'Finishing materials',
        'Transparent panels': 'Finishing materials',
        'Dowel systems for panels': 'Finishing materials',
        'Secondary water-shedding membrane': 'Others',
        'Vapour barriers and brakes': 'Others',
        'Sealing foils': 'Others',
        'Fleeces': 'Others',
        'Building papers': 'Others',
        'Air cushion': 'Others',
        'Technical textiles': 'Others',
        'Rubber': 'Others',
        'Silicone': 'Others',
        'Polyurethane': 'Others',
        'Bitumen': 'Others',
        'PVC': 'Others',
        'Acrylate': 'Others',
        'Polysulphide': 'Others',
        'EoL dowel system for panels': 'Others',
        'EoL dowel system for membranes': 'Others',
        'EoL elastomer sheeting': 'Others',
        'EoL EVA sheeting': 'Others',
        'Wood': 'Wood/Timber',
        'Wood thermally separated': 'Wood/Timber',
        'Derived timber products': 'Wood/Timber',
        'Wood-aluminium': 'Wood/Timber',
        'Aluminium': 'Aluminium and other metals',
        'Aluminium thermally separated': 'Aluminium and other metals',
        'Steel': 'Steel',
        'Steel galvanised': 'Steel',
        'Polyurethane rigid foam': 'Insulation materials',
        'Transparent infill': 'Others',
        'Opaque fillings': 'Others',
        'Sealing profiles': 'Others',
        'Sprayable sealant': 'Others',
        'Waterproof foam sealant': 'Others',
        'Joint sealing tapes': 'Others',
        'Rubber seal': 'Others',
        'Sealing membranes': 'Others',
        'Stop beads for rendering applications': 'Others',
        'Steel window fittings': 'Steel',
        'Aluminium window fittings': 'Aluminium and other metals',
        'Bronze window fittings': 'Aluminium and other metals',
        'Brass window fittings': 'Aluminium and other metals',
        'Stainless steal window fittings': 'Steel',
        'Fastening materials': 'Others',
        'Window handles': 'Aluminium and other metals',
        'Zinc fittings': 'Aluminium and other metals',
        'Plastic fittings': 'Others',
        'EoL steel': 'Steel',
        'EoL bronze': 'Aluminium and other metals',
        'EoL brass': 'Aluminium and other metals',
        'EoL zinc': 'Aluminium and other metals',
        'EoL window': 'Aluminium and other metals',
        'Plastic': 'Others',
        'mechanical': 'Others',
        'electrical': 'Others',
        'Timber windows': 'Wood/Timber',
        'Timber-metal windows': 'Wood/Timber',
        'Metal windows': 'Aluminium and other metals',
        'Plastic windows': 'Others',
        'Other windows': 'Others',
        'Curtain walling - stick construction': 'Others',
        'Curtain walling - unitized walling': 'Others',
        'Other walling': 'Others',
        'Roof lights': 'Others',
        'Smoke and heat control systems': 'Others',
        'Other daylight systems': 'Others',
        'Solar protection devices': 'Others',
        'Finger protection devices': 'Others',
        'Fire resistance and smoke control devices': 'Others',
        'Heat generator': 'Others',
        'Heat distribution and dissipation': 'Others',
        'Storage': 'Others',
        'Ventilation system': 'Others',
        'Air conditioning/cooling machines': 'Others',
        'Accessory': 'Others',
        'Refrigerants': 'Others',
        'Sanitary ware': 'Others',
        'Mountings': 'Others',
        'Shower and bath tubs': 'Others',
        'Cable': 'Others',
        'Switches and sockets': 'Others',
        'Fuse and switch boxes': 'Others',
        'Lighting': 'Others',
        'Batteries': 'Others',
        'Elevator': 'Others',
        'Escalator': 'Others',
        'Use heat generator': 'Others',
        'Use ventilation and air conitioning': 'Others',
        'Use mountings': 'Others',
        'Use lighting': 'Others',
        'Use conveyor': 'Others',
        'Use heat generator (EnEV)': 'Others',
        'EoL heat generator': 'Others',
        'EoL ventilation and air conitioning': 'Others',
        'EoL sanitary': 'Others',
        'EoL electrical': 'Others',
        'EoL conveyor': 'Others',
        'Protection systems for cable and duct insulation': 'Others',
        'Digger/digging': 'Others',
        'Concreting': 'Others',
        'Concrete formwork': 'Others',
        'Welding': 'Others',
        'District heat': 'Others',
        'Drinking water': 'Others',
        'Fuel from vegetable oil': 'Others',
        'Truck': 'Others',
        'Train': 'Others',
        'Inland water transport': 'Others',
        'Ocean transport': 'Others',
        'Passenger car': 'Others',
        'Plane': 'Others',
        'Recycling of construction waste': 'Others',
        'Landfilling of construction waste': 'Others',
        'Standard landfilling': 'Others',
        'Waste incineration': 'Others',
        'Inner walls': 'Masonry',
        'Ceilings': 'Masonry',
        'Outer walls': 'Masonry',
        'Flooring': 'Masonry',
        'Reinforcement': 'Ready-mix concrete and cement',
        'Roof superstructures': 'Ready-mix concrete and cement',
        'Construction waste': 'Others',
        'Consumer waste': 'Others',
        'Metals': 'Aluminium and other metals',
        'Plastics': 'Others',
        'Building service engineering': 'Others'
    }
    
    def map_category(original_category):
        """
        Map original material category to one of the main categories
        """
        if pd.isna(original_category):
            return 'Others'
        
        original_str = str(original_category).strip()
        
        # Direct match
        if original_str in material_mapping:
            return material_mapping[original_str]
        
        # Case insensitive match
        original_lower = original_str.lower()
        for key, value in material_mapping.items():
            if key.lower() == original_lower:
                return value
        
        # Partial match - check if any keyword exists in the original category
        for key, value in material_mapping.items():
            if key.lower() in original_lower or original_lower in key.lower():
                return value
        
        # If no match found, return 'Others'
        return 'Others'
    
    # Apply the mapping
    df['mapped_material_category'] = df['material_category'].apply(map_category)
    
    return df**


def _building_dashboard_assembly(df_pie, df_bar, key_column: str):
    # Preset colors
    colors = ["rgb(244, 132, 67)", "rgb(150, 150, 150)"]

    # Create a 2x2 layout: top row for pie and bar, bottom row for indicators
    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "domain"}, {"type": "xy"}],
            [{"type": "domain"}, {"type": "domain"}],
        ],
        subplot_titles=[
            "<b>Whole life cycle carbon</b><br> ",
            "<b>Embodied carbon</b><br> ",
            "",
            "",
        ],
        # Give more vertical space to top row
        row_heights=[0.7, 0.25],
        vertical_spacing=0.3,
    )

    # Update all annotations (including subplot titles)
    for annotation in fig["layout"]["annotations"]:
        annotation["font"] = dict(size=20)  


    # Add custom labels for legend
    df_pie["Label"] = df_pie.apply(
        lambda x: f"{x[key_column]}: {x['gwp']:.1f} kg CO₂eq/m²", 
        axis=1
    )

    # Add pies
    fig.add_trace(
        go.Pie(
            labels=df_pie["Label"],
            values=df_pie["gwp"],  # using only positive values
            name="GWP",
            hole=0.4,
            marker=dict(colors=colors),
            legendgroup="GWP",
            showlegend=True,
        ),
        row=1,
        col=1,
    )

    # Stacking 2 bars on top of each other to have grey bars be behind orange bars
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=[100] * len(df_bar),
            orientation='h',
            marker=dict(
                color="rgba(200,200,200,0.3)",
                cornerradius=8,
            ),
            showlegend=False,
            hoverinfo='none',
            cliponaxis=False,
            # use the grey bars to carry the text
            text=[f"{cat} - {val:.1f}%" 
                for cat,val in zip(df_bar[key_column], df_bar["gwp_per"])],
            textposition='outside',
            textfont=dict(size=12, color='black'),
        ),
        row=1, col=2
    )
    
    # 2) Overlay the actual % bars in orange
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=df_bar["gwp_per"],
            customdata=df_bar["gwp_abs"],
            orientation='h',
            marker=dict(
                cornerradius=8,
                color=colors[0],
            ),
            showlegend=False,
            hovertemplate="%{customdata:,.1f} kg CO₂eq/m²<extra></extra>",
            hoverlabel=dict(
                font=dict(color="white")
            )
        ),
        row=1, col=2
    )
    
    # 4a) Flip the y-order so your biggest bars sit at the top
    fig.update_yaxes(autorange='reversed',
        showticklabels=False,       # no labels on the left
        side='right',               # ticks would go on the right
        row=1, col=2
        )

    # 4c) Clean up the x-axis (no grid, no numbers)
    fig.update_xaxes(
        range=[0, 100],
        automargin=True,
        showgrid=False,
        showticklabels=False,
        row=1, col=2
    )

    # Update pies formatting
    fig.update_traces(
        hoverinfo="label+value",
        hovertemplate="%{label}<extra></extra>",
        hoverlabel=dict(font_color="white", namelength=-1),
        textposition="auto",
        textfont=dict(
            size=14, 
            family="Arial, sans-serif",  
            color="white",
        ),
        texttemplate="<b>%{percent:.0%}</b>",
        selector=dict(type="pie"),
    )

    fig.update_traces(cliponaxis=False, selector=dict(type='bar'))
    
    fig.update_layout(
        height=500, 
        width=900,
        margin=dict(l=50, r=200, t=100, b=50),
        paper_bgcolor='rgba(0,0,0,0)',  
        plot_bgcolor='rgba(0,0,0,0)',
        bargap=0.05,
        bargroupgap=0.5,
        uniformtext=dict(mode='show', minsize=12),
        yaxis=dict(showticklabels=False),
        barmode='overlay',
        legend=dict(
            orientation="h",
            x=0.25,              
            xanchor="center",
            y=0.30,              
            yanchor="bottom",
            font=dict(size=14),  
        ),
    )

    # Calculate initial sums
    gwp_sum = df_pie["gwp"].sum()
    gwp_embodied_sum = df_pie.loc[df_pie["type"] == "structural", "gwp"].sum()

    # Add Indicators (make them larger)
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=gwp_sum,
            title={"text": "<b>Building carbon footprint</b>", "font": {"size": 20}},
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " kg CO₂eq/m²"},
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=gwp_embodied_sum,
            title={"text": "<b>Total embodied carbon</b>", "font": {"size": 20}},
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " kg CO₂eq/m²"},
        ),
        row=2,
        col=2,
    )

    pie_plot = plot(
        fig, output_type="div", config={"displaylogo": False, "displayModeBar": False}
    )
    return pie_plot



**def _building_dashboard_material_bar(df_bar, df_full, key_column: str):
    """
    NEW FUNCTION: Material dashboard showing ONLY bar chart for embodied carbon by materials
    Similar to assembly view but only showing bar chart, no pie chart
    """
    
    # Create a 2x1 layout: top row for bar chart, bottom row for indicators
    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "xy", "colspan": 2}, None],
            [{"type": "domain"}, {"type": "domain"}],
        ],
        subplot_titles=[
            "<b>Embodied carbon by material</b><br> ",
            "",
            "",
            "",
        ],
        # Give more vertical space to top row
        row_heights=[0.7, 0.25],
        vertical_spacing=0.3,
    )

    # Update all annotations (including subplot titles)
    for annotation in fig["layout"]["annotations"]:
        annotation["font"] = dict(size=20)  

    # Stacking 2 bars on top of each other to have grey bars be behind orange bars
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=[100] * len(df_bar),
            orientation='h',
            marker=dict(
                color="rgba(200,200,200,0.3)",
                cornerradius=8,
            ),
            showlegend=False,
            hoverinfo='none',
            cliponaxis=False,
            # use the grey bars to carry the text
            text=[f"{cat} - {val:.1f}%" 
                for cat,val in zip(df_bar[key_column], df_bar["gwp_per"])],
            textposition='outside',
            textfont=dict(size=12, color='black'),
        ),
        row=1, col=1
    )
    
    # 2) Overlay the actual % bars in orange
    fig.add_trace(
        go.Bar(
            y=df_bar[key_column],
            x=df_bar["gwp_per"],
            customdata=df_bar["gwp_abs"],
            orientation='h',
            marker=dict(
                cornerradius=8,
                color="rgb(244, 132, 67)",  # Orange color for embodied carbon
            ),
            showlegend=False,
            hovertemplate="%{customdata:,.1f} kg CO₂eq/m²<extra></extra>",
            hoverlabel=dict(
                font=dict(color="white")
            )
        ),
        row=1, col=1
    )
    
    # 4a) Flip the y-order so your biggest bars sit at the top
    fig.update_yaxes(autorange='reversed',
        showticklabels=False,       # no labels on the left
        side='right',               # ticks would go on the right
        row=1, col=1
        )

    # 4c) Clean up the x-axis (no grid, no numbers)
    fig.update_xaxes(
        range=[0, 100],
        automargin=True,
        showgrid=False,
        showticklabels=False,
        row=1, col=1
    )

    fig.update_traces(cliponaxis=False, selector=dict(type='bar'))
    
    fig.update_layout(
        height=500, 
        width=900,
        margin=dict(l=50, r=200, t=100, b=50),
        paper_bgcolor='rgba(0,0,0,0)',  
        plot_bgcolor='rgba(0,0,0,0)',
        bargap=0.05,
        bargroupgap=0.5,
        uniformtext=dict(mode='show', minsize=12),
        yaxis=dict(showticklabels=False),
        barmode='overlay',
    )

    # Calculate sums for indicators
    gwp_sum = df_full["gwp"].sum()
    penrt_sum = df_full["penrt"].sum()

    # Add Indicators (make them larger)
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=gwp_sum,
            title={"text": "<b>Total Embodied Carbon</b>", "font": {"size": 20}},
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " kg CO₂eq/m²"},
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=penrt_sum,
            title={"text": "<b>Total Embodied Energy</b>", "font": {"size": 20}},
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " MJ/m²"},
        ),
        row=2,
        col=2,
    )

    pie_plot = plot(
        fig, output_type="div", config={"displaylogo": False, "displayModeBar": False}
    )
    return pie_plot**


def _building_dashboard_base(df, key_column: str):
    
    # Generate colors & correct ordering
    df_sorted, color_list = _get_color_ordering(df, "carbon")

    # Create a 2x2 layout: top row for pies, bottom row for indicators
    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "domain"}, {"type": "domain"}],
            [{"type": "domain"}, {"type": "domain"}],
        ],
        subplot_titles=[
            **"<b>Embodied Carbon</b><br>by material<br> ",  # UPDATED: Changed from "LCA Carbon"**
            **"<b>Embodied Energy</b><br>by material<br> ",  # UPDATED: Changed from "LCA Energy"**
            "",
            "",
        ],
        # Give more vertical space to top row
        row_heights=[0.6, 0.3],
        vertical_spacing=0.05,
    )

    # Update all annotations (including subplot titles)
    for annotation in fig["layout"]["annotations"]:
        annotation["font"] = dict(size=20)  



    # Add pies
    fig.add_trace(
        go.Pie(
            labels=df_sorted[key_column],
            values=df_sorted["gwp"],  
            name="GWP",
            direction ='clockwise',
            hole=0.4,
            marker=dict(colors=color_list),
            legendgroup="GWP",
            showlegend=True,
            sort=False,
        ),
        row=1,
        col=1,
    )

    # Generate colors & correct ordering
    df_sorted, color_list = _get_color_ordering(df, "energy")

    fig.add_trace(
        go.Pie(
            labels=df_sorted[key_column],
            values=df_sorted["penrt"],
            sort=False,
            direction ='clockwise',
            name="PENRT",
            hole=0.4,
            marker=dict(colors=color_list),
            legendgroup="PENRT",
            showlegend=True,
        ),
        row=1,
        col=2,
    )

    # Update pies formatting
    fig.update_traces(
        hoverinfo="label+value",
        hovertemplate="%{label}<br><b>Value: %{value:.2f}</b><extra></extra>",
        hoverlabel=dict(font_color="white", namelength=-1),
        textposition="inside",
        textfont=dict(
            size=14,  # Default font size
            family="Arial, sans-serif",  # Use a modern sans-serif font
            color="white",  # Default high contrast text color
        ),
        texttemplate="<b>%{label}</b><br>%{percent:.0%}",
        
        # connector=dict(line=dict(color="black", width=1, dash="solid")),
    )

    # Store existing annotations (subplot titles)
    existing_annotations = list(fig.layout.annotations)

    # Calculate centers for pie hole annotations
    first_pie_domain = fig.data[0].domain
    second_pie_domain = fig.data[1].domain

    gwp_annotation = dict(
        text="GWP",
        x=(first_pie_domain.x[0] + first_pie_domain.x[1]) / 2,
        y=(first_pie_domain.y[0] + first_pie_domain.y[1]) / 2,
        font_size=20,
        showarrow=False,
        xanchor="center",
        yanchor="middle",
    )

    penrt_annotation = dict(
        text="PENRT",
        x=(second_pie_domain.x[0] + second_pie_domain.x[1]) / 2,
        y=(second_pie_domain.y[0] + second_pie_domain.y[1]) / 2,
        font_size=20,
        showarrow=False,
        xanchor="center",
        yanchor="middle",
    )

    # Combine original titles + new annotations
    new_annotations = existing_annotations + [gwp_annotation, penrt_annotation]
    fig.update_layout(annotations=new_annotations, uniformtext_minsize=12, uniformtext_mode='hide')

    # Calculate initial sums
    gwp_sum = df["gwp"].sum()
    penrt_sum = df["penrt"].sum()

    # Add Indicators (make them larger)
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=gwp_sum,
            title={"text": **"<b>Total Embodied Carbon</b>"**, "font": {"size": 20}},  **# UPDATED: Changed from "Total GWP"**
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " kg CO₂eq/m²"},
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=penrt_sum,
            title={"text": **"<b>Total Embodied Energy</b>"**, "font": {"size": 20}},  **# UPDATED: Changed from "Total PENRT"**
            number={"font": {"size": 20, "weight": "bold"}, 'valueformat': ',.0f', 'suffix': " MJ/m²"},
        ),
        row=2,
        col=2,
    )

    # Increase figure size and reduce margins
    fig.update_layout(
        height=500, width=900, margin=dict(l=25, r=25, t=125, b=25), showlegend=True
    )

    pie_plot = plot(
        fig, output_type="div", config={"displaylogo": False, "displayModeBar": False}
    )
    return pie_plot


def _get_color_ordering(df, unit):
    **# UPDATED: Simplified since material view only contains structural materials now**
    **df_sorted = df.sort_values(["gwp"], ascending=[False]).reset_index(drop=True)**
    
    **# REMOVED: Separation of structural vs operational since only structural exists**
    **if unit == "carbon":  
        color_list = _generate_discrete_colors(
            start_color=(244, 132, 67), end_color=(250, 199, 165), n=df_sorted.shape[0]
        )
    elif unit == "energy":
        color_list = _generate_discrete_colors(
            start_color=(36, 191, 91), end_color=(154, 225, 177), n=df_sorted.shape[0]
        )**
        
    **return df_sorted, color_list**


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
