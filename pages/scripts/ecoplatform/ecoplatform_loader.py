import os
import logging
import json

from dotenv import load_dotenv
import requests
import lcax

logger = logging.getLogger(__name__)

load_dotenv()

ECO_PLATFORM_TOKEN = os.getenv("ECO_PLATFORM_TOKEN")
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
    epd_list = []
    for i in data["data"]:
        if isinstance(i.get("geo"), str) and i.get("geo").strip().upper() in country_list:
            epd_list.append({
                "geo": i["geo"],
                "uuid": i["uuid"],
                "uri": i["uri"],
                "name": i["name"],
                "nodeid": i["nodeid"]
            })
        
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
