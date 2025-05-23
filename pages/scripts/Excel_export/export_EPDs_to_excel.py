from io import BytesIO

import pandas as pd

from pages.models.epd import EPD, EPDImpact, MaterialCategory

def to_excel(epds: list[EPD]) -> None:
    epd_list = []
    for e in epds:
        epd_list.append(parse_EPD(e))
    
    return pd.DataFrame.from_records(epd_list)

def to_excel_bytes(epds: list[EPD]):
    df = to_excel(epds)
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='EPDs', index=False)

    excel_bytes = buffer.getvalue()
    return excel_bytes

def parse_EPD(epd: EPD):
    return {
        "level_0_index": epd.category.parent.parent.level if get_parent(get_parent(epd.category)) else "",
        "level_0_text": epd.category.parent.parent.name_en if get_parent(get_parent(epd.category)) else "",
        "level_1_index": epd.category.parent.level if get_parent(epd.category) else "",
        "level_1_text": epd.category.parent.name_en if get_parent(epd.category) else "",
        "level_2_index": epd.category.level,
        "level_2_text": epd.category.name_en,
        "source": epd.source,
        "type": epd.type,
        "comment": epd.comment,
        "country": epd.country.name,
        "uuid": epd.UUID,
        "name": epd.name,
        "names": ", ".join([n["value"] for n in epd.names]),
        "declared_unit": epd.declared_unit,
        "declared amount": epd.declared_amount,
        "weight": get_conversion(epd.conversions, "-"),
        "volumne density": get_conversion(epd.conversions, "kg/m^3"),
        "area density": get_conversion(epd.conversions, "kg/m^2"),
        "linear density": get_conversion(epd.conversions, "kg/m"),
        "gwp_a1a3": get_impact(epd.epdimpact_set.all(), "gwp", "a1a3")
    }


def get_conversion(conversions: list[dict], unit):
    for c in conversions:
        if c.get("unit") == unit:
            return c.get("value")


def get_impact(impacts: list[EPDImpact], impact_catgory, life_cycle_stage):
    for i in impacts:
        if i.impact.impact_category == impact_catgory and i.impact.life_cycle_stage == life_cycle_stage:
            return i.value


def get_parent(category: MaterialCategory):
    if category and category.parent:
        return category.parent
