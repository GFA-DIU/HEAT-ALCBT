from pages.models import EPD, EPDImpact

from pages.scripts.Excel_export.export_EPDs_to_excel import to_excel


from django.db.models import Prefetch

epds = (
    EPD.objects
        .all()
    #    .filter(category__parent__name_en="Mortar and Concrete")
       # follow all your FK/OneToOne links in one big JOIN
       .select_related(
           "country",
           "city",
           "category",
           "category__parent",
           "category__parent__parent",
       )
       # grab all the reverse/M2M data in one shot each
       .prefetch_related(
           # impacts are through the EPDImpact intermediary; prefetch both sides
           Prefetch(
               "epdimpact_set",
               queryset=EPDImpact.objects.select_related("impact"),
               to_attr="all_impacts",
           ),
           # if you ever do `epd.impacts.all()`, you can also prefetch that:
           "impacts",
       )
)

df = to_excel(epds)

df.to_excel("Complete_EPD_db_export_20250522.xlsx")
# df.to_excel("Concrete_db_export_20250522.xlsx")