import logging

import pandas as pd

from pages.models.epd import EPD, EPDLabel, Label, MaterialCategory
from pages.scripts.csv_import.utils import get_category, get_country



logger = logging.getLogger(__name__)


def add_GCCA_labels():
    file_path = "pages/data/GCCA_label_mapping.csv"
    df = pd.read_csv(file_path, sep=";")
    
    failure_list = []
    for id, row in df.iterrows():
        logger.info("Row %s is being processed", id)
        
        try:
            label = Label.objects.get(
                name= "GCCA Global Reference Threshold Low Carbon and Near Zero Emissions Concrete"
            )
            
            category = MaterialCategory.objects.get(
                name_en=row["level_2_text"], level=3
            )
                       
            epd = EPD.objects.get(
                category=category,
                source=row["source"],
                type= row["type"],
                comment= row["comment"] if not pd.isna(row["comment"]) else None,
                country= get_country(row["country"]),
                name= row["name"],
                declared_unit= row["declared_unit"],
            )

            EPDLabel.objects.update_or_create(
                epd=epd,
                label=label,
                score=row["label_score"]
            )
        except Exception as e:
            logger.exception("Error in row %s", id)
            failure_list.append(id)
            raise Exception(f"Error in row {id}: {e}\n  Row: {row}")

    logger.info("Executed with %s errors out of %s entries", len(failure_list), len(df))
