import os
from pathlib import Path

from django.shortcuts import render


def resources(request):
    lead_partner_logos = get_all_files("static/images/logos/lead_partners/")
    dev_partner_logos = get_all_files("static/images/logos/development_partners/")
    context = {
        "lead_partner_logos": lead_partner_logos,
        "dev_partner_logos": dev_partner_logos,
    }
    return render(request, "pages/resources.html", context)


def get_all_files(folder_path: Path):
    file_list = [
        Path(f).name
        for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
    ]
    file_list.sort()
    return file_list
