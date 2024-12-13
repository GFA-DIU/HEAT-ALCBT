import logging
import json

import lcax
import requests

logger = logging.getLogger(__name__)

OKOBAU_URL = "https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/c391de0f-2cfd-47ea-8883-c661d294e2ba"


def get_epds(limit) -> dict:
    """Get several EPDs from Ökobau"""

    response = requests.get(
        f"{OKOBAU_URL}/processes?format=json&view=extended&pageSize={limit}"
    )
    response.raise_for_status()
    data = response.json()

    logger.info(
        "Retrieved %s EPDs out of %s from Ökobau",
        data.get("pageSize"),
        data.get("totalCount"),
    )

    return data


def get_all_epds() -> dict:
    """Get UUIDs from all Oekobaudat EPDs."""
    # get total number of EPDs
    data = get_epds(1)
    num_epds = data.get("totalCount")

    # Load all epds
    data = get_epds(num_epds)

    # Get UUID
    uuids = []
    for epd in data.get("data"):
        uuids.append(epd.get("uuid"))

    return uuids


def get_full_epd(uid: str) -> dict:
    """Get the full dataset for a single EPD

    Notes:
     - If no version number is specified, the most recent dataset (with the highest version number) is always
    returned. (ECO-Platform documentation on soda4LCA)
    """

    base_url = f"{OKOBAU_URL}/processes/{uid}"
    response = requests.get(f"{base_url}?format=json&view=extended")
    response.raise_for_status()
    data = response.json()
    data["source"] = base_url

    return data


def get_names(d: dict):
    name_list = d["processInformation"]["dataSetInformation"]["name"]["baseName"]
    name_de = ""
    name_en = ""
    for i in name_list:
        if i["lang"] == "de":
            name_de = i["value"]
        else:
            name_en = i["value"]
    
    
    return name_de, name_en, name_list


def get_classification(d: dict):
    classification_list = d["processInformation"]["dataSetInformation"]["classificationInformation"]["classification"][0]["class"]
    container = {}
    for count, i in enumerate(classification_list):
        # classification list is ordered
        assert i.get("level") == count
        container = {"classification": i.get("classId")}

    return container


def parse_epd(epd: dict):
    parsed_epd = {}

    # parsing from JSON
    name_de, name_en, names = get_names(epd)
    name = name_en if name_en else name_de
    parsed_epd.update({"name": name, "names": names, "source": epd["source"]})
    parsed_epd.update(get_classification(epd))
    parsed_epd.update(get_declared_quantity(epd))

    # parsing from LCAx
    parsed_epd.update(parse_Lcax_format(epd))

    logger.info(
        "Successfuly parsed EPD %s",
    )

    return parsed_epd


def parse_Lcax_format(epd: dict) -> dict:
    epd_string = json.dumps(epd)
    epd = lcax.convert_ilcd(epd_string, as_type=lcax.EPD)
    conversions = [json.loads(conv.meta_data) for conv in epd.conversions]
    info = {
        "declared_unit": epd.declared_unit.value,
        "conversions": conversions,
        "uuid": epd.id,
        "comment": epd.comment,
        "version": epd.version,
    }
    impacts = get_impacts(epd)
    info.update(impacts)
    return info


def get_impacts(epd: lcax.EPD):
    indicator_list = {
        "penrt": ["a1a3", "c3", "c4", "d"],
        "gwp": ["a1a3", "c3", "c4", "d"],
    }

    container = {}
    for k, v in epd.impacts.items():
        if lifecycle := indicator_list.get(k):
            for i in lifecycle:
                container.update({f"{k}_{i}": v.get(i)})

    return container


def get_declared_quantity(epd: dict) -> float:
    return {"declared_amount": epd["exchanges"]["exchange"][0]["resultingflowAmount"]}
