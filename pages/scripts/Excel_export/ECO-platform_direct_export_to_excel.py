import json

import pandas as pd

from pages.scripts.oekobaudat.oekobaudat_loader import (
    get_all_epds,
    get_full_epd,
    parse_epd,
)
from pages.scripts.ecoplatform.ecoplatform_loader import get_all_uuids_ecoplatform
from pages.scripts.ecoplatform.ecoplatform_loader import get_full_epd as eco_get_full_epd


with open("pages/fixtures/material_category_data.json","r") as f:
    data = json.load(f)


mapping_table = pd.DataFrame.from_records([d["fields"] for d in data])
mapping_dict = dict(zip(mapping_table["category_id"], mapping_table["name_en"]))
mapping_dict["0"] = "Unkown"


def load_oekobaudat():
    def get_classification(d: dict):
        classification_list = d["processInformation"]["dataSetInformation"]["classificationInformation"]["classification"][0]["class"]
        container = {}
        for count, i in enumerate(classification_list):
            # classification list is ordered
            assert i.get("level") == count
            container.update({f"level_{count}_index": i.get('classId'), f"level_{count}_text": i.get('value')})
            
        return container


    def get_densities(d: dict):
        container = {}
        for conv in d["conversions"]:
            if conv["name"] == "massenbezug":
                conv["name"] = "mass reference"
            if conv["name"] == "thickness":
                conv["name"] = "layer thickness"
            if conv["name"] == "conversion_factor (to kg)":
                conv["name"] = "conversion factor to 1 kg"
            if conv["name"] == "conversion factor":
                continue
            container.update({conv["name"]: conv["value"]})

        return container


    def get_conv_factor(d: dict):
        conv = {"conversion_factor (to kg)": i["value"] for i in d.get("conversions") if "kg" in i["unit"]}
        return conv
    
    uuids = get_all_epds()
    
    epd_list = []
    for uuid in uuids:
        data = get_full_epd(uuid)
        epd = parse_epd(data)
        epd.update(get_classification(data))
        epd.update(get_densities(epd))
        epd.update(get_conv_factor(epd))
        epd_list.append(epd)
        
    df = pd.DataFrame.from_records(epd_list)
    

    level_cols = ["level_0", "level_1", "level_2"]

    for col in level_cols:
        df[f"{col}_text"] = df[f"{col}_index"].apply(lambda x: mapping_dict.get(x))
        df[f"{col}_index"] = df[f"{col}_index"].apply(lambda x: x.split(".")[-1] if isinstance(x, str) else None)


    col_order = [
        "level_0_index",
        "level_0_text",
        "level_1_index",
        "level_1_text",
        "level_2_index",
        "level_2_text",
        "country",
        "Source",
        "uuid",
        "name",
        "declared_unit",
        "declared_amount",
        'layer thickness',
        'grammage',
        'gross density',
        'conversion factor to 1 kg',
        'linear density',
        'weight per piece',
        'mass reference',
        'conversion factor [mass/declared unit]',
        # 'declared unit',
        'weight per unit',
        'bulk density',
        'productiveness',
        # 'conversion factor', # undeclared unit, unclear conversion target
        "penrt_a1a3",
        "penrt_c3",
        "penrt_c4",
        "penrt_d",
        "gwp_a1a3",
        "gwp_c3",
        "gwp_c4",
        "gwp_d"
    ]
    df.rename(columns={"linear  density": "linear density"})
    df = df[col_order]
    
    return df


def load_ecoplatform():
    def get_classification(d: dict):
        try:
            classification_list = d["processInformation"]["dataSetInformation"]["classificationInformation"]["classification"][0]["class"]
            container = {}
            for count, i in enumerate(classification_list):
                # classification list is ordered
                assert i.get("level") == count
                assert len(i.get("classId")) < 7  # otherwise there is an error
                container.update({f"level_{count}_index": i.get('classId'), f"level_{count}_text": i.get('value')})
            if container != {}:
                return container
            else:
                return {
                    "level_0_index": 0,
                    "level_0_text": "Unkown"
                } 
    
        except:
            try:
                classification_info = d["processInformation"]["dataSetInformation"].get(
                    "classificationInformation"
                )
                if classification_info:
                    return {
                        "level_0_index": "5",
                        "level_0_text": "Coverings",
                        "level_1_index": "5.1",
                        "level_1_text": "Primer",
                        "level_2_index": "5.1.01",
                        "level_2_text": "Primer for paints and plasters",
                    } 
                else:
                    return {
                        "level_0_index": 0,
                        "level_0_text": "Unkown"
                    }       
            except:
                return {
                    "level_0_index": 0,
                    "level_0_text": "Unkown"
                } 

    def get_densities(d: dict):
        container = {}
        for conv in d["conversions"]:
            if conv["name"] == "grammage (kg/m^2)":
                conv["name"] = "grammage"
            if conv["name"] == "layer thickness (m)":
                conv["name"] = "layer thickness"
            if conv["name"] == "conversion_factor (to kg)":
                conv["name"] = "conversion factor to 1 kg"
            container.update({conv["name"]: conv["value"]})

        return container


    def get_conv_factor(d: dict):
        conv = {"conversion_factor (to kg)": i["value"] for i in d.get("conversions") if "kg" in i["unit"]}
        return conv
    
    epd_info = get_all_uuids_ecoplatform()
    epd_info = [(e["uri"], e["geo"]) for e in epd_info]
    
    
    epd_list = []
    uri_issue_list = []
    for uri, geo in epd_info:
        # Fetch related country
        country = geo
        # Retrieve and process EPD data
        data = get_full_epd(uri)
        epd = parse_epd(data)
        epd.update(get_classification(data))
        epd.update(get_densities(epd))
        epd.update(get_conv_factor(epd))
        epd["country"] = geo.upper()
        epd_list.append(epd)
    
    df = pd.DataFrame.from_records(epd_list)
    
    level_cols = ["level_0", "level_1", "level_2"]

    for col in level_cols:
        df[f"{col}_text"] = df[f"{col}_index"].apply(lambda x: mapping_dict.get(x) if mapping_dict.get(x) else "Unkown")
        df[f"{col}_index"] = df[f"{col}_index"].apply(lambda x: x.split(".")[-1] if isinstance(x, str) else None)
        
    
    col_order = [
        "level_0_index",
        "level_0_text",
        "level_1_index",
        "level_1_text",
        "level_2_index",
        "level_2_text",
        "country",
        "Source",
        "uuid",
        "name",
        "declared_unit",
        "declared_amount",
        'layer thickness',
        'grammage',
        'gross density',
        'conversion factor to 1 kg',
        # 'weight per piece',
        # 'mass reference',
        # 'conversion factor [mass/declared unit]',
        # 'declared unit',
        # 'weight per unit',
        'bulk density',
        # 'productiveness',
        # 'conversion factor', # undeclared unit, unclear conversion target
        # 'linear  density'
        "penrt_a1a3",
        "penrt_c3",
        "penrt_c4",
        "penrt_d",
        "gwp_a1a3",
        "gwp_c3",
        "gwp_c4",
        "gwp_d"
    ]

    df.rename(columns={"source": "Source", "conversion_factor (to kg)": "conversion factor to 1 kg"}, inplace=True)
    df = df[col_order]
    
    return df


if __name__ == "__main__":
    df_oeko = load_oekobaudat()
    df_eco = load_ecoplatform()
    
    df = pd.concat([df_oeko, df_eco], axis=0, ignore_index=True)
    
    df.to_excel("epd_data_for_dirk_20241219.xlsx", index=None)