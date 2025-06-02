import os
import logging
import json

import environ
import requests
import lcax

logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env()  # Reads variables from a .env file

ECO_PLATFORM_TOKEN = env("ECO_PLATFORM_TOKEN")
ECO_PLATFORM_URL =  "https://data.eco-platform.org/resource/processes?search=true&distributed=true&virtual=true&metaDataOnly=false&validUntil=2025&format=json&iew=extended"

# ALCBT countries, ISO 3166-1 alpha-2
country_list = [
    "ID",  # Indonesia
    "IN",  # India
    "KH",  # Cambodia
    "TH",  # Thailand
    "VN",  # Vietnam
]


def get_epds(limit) -> dict:
    """Get multiple EPDs from ECO-Platform"""

    headers = {
        "Authorization": f"Bearer {ECO_PLATFORM_TOKEN}"
    }

    response = requests.get(f"{ECO_PLATFORM_URL}&pageSize={limit}", headers=headers)
    response.raise_for_status()
    data = response.json()

    logger.info(
        "Retrieved %s EPDs out of %s from ECO-Platform",
        data.get("pageSize"),
        data.get("totalCount"),
    )

    return data


def get_all_uuids_ecoplatform() -> list[dict]:
    """Get UUIDs and info from Eco-platform."""
    # get total number of EPDs
    data = get_epds(1)
    num_epds = data.get("totalCount")

    # Load all epds
    data = get_epds(num_epds)
    
    # Get UUID
    required = ("uuid", "uri", "nodeid", "geo", "name")
    epd_list = {}
    for i in data["data"]:
        try:
            uuid, uri, nodeid, geo, name = (i[k] for k in required)
        except KeyError as exc:
            logger.error("Missing required key %s in EPD entry: %s.\nSkipping", exc, i)
            continue
        
        if not uuid:
            logger.error("The EPD with URI: '%s' did not contain a UUID.\nSkipping", uri)
            continue
        
        if not name:
            logger.error("The EPD with UUID: '%s' did not contain a name.\nSkipping", uuid)
            continue
        
        if not isinstance(geo, str) or geo.strip().upper() not in country_list:
            logger.error("Invalid georeference %s for the EPD with UUID: '%s'.\nSkipping", geo, uuid)
            continue
        
        epd_list[uuid] = {
            "geo": geo,
            "uuid": uuid,
            "uri": uri,
            "name": name,
            "nodeid": nodeid
        }

    return epd_list


def get_full_epd(uri: str) -> dict:
    """Get the full dataset for a single EPD"""

        
    headers = {
        "Authorization": f"Bearer {ECO_PLATFORM_TOKEN}"
    }

    assert "?" in uri  # check that parameter can be given    
        
    
    response = requests.get(f"{uri}&lang=en&format=json&view=extended", headers=headers)
    response.raise_for_status()
    data = response.json()
    data["source"] = uri

    return data
