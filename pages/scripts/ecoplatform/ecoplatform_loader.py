import os
import logging
import json
from datetime import date

import environ
import requests
import lcax

logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env()  # Reads variables from a .env file

ECO_PLATFORM_TOKEN = env("ECO_PLATFORM_TOKEN")
# NOTE: ECO Platform migrated to the "New ECO Portal" — the old host
# `data.eco-platform.org` now only redirects to the portal home page, so the
# API base is `portal.eco-platform.org/resource/` (per the official API guide:
# https://github.com/ECO-Platform/ECO_Platform_API_Guide).
# validUntil is kept to the current year so we only pull EPDs still valid today
# (was hardcoded to 2025, which silently excludes currently-valid datasets once
# the year rolls over). No `view=extended` here on purpose: this is the LIST call
# and we only read metadata (uuid/uri/geo/name); the full per-EPD download in
# get_full_epd() adds view=extended. (Previously mistyped as `iew=extended`.)
ECO_PLATFORM_URL = (
    "https://portal.eco-platform.org/resource/processes"
    "?search=true&distributed=true&virtual=true&metaDataOnly=false"
    f"&validUntil={date.today().year}&format=json"
)

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


def get_all_uuids_ecoplatform() -> dict[str, dict]:
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
        
        # Filter EPD for target countries
        if isinstance(geo, str) and geo.strip().upper() in country_list:
            if not uuid:
                logger.error("The EPD with URI: '%s' did not contain a UUID.\nSkipping", uri)
                continue
            
            if not name:
                logger.error("The EPD with UUID: '%s' did not contain a name.\nSkipping", uuid)
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
