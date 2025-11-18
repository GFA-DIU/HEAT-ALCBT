import os
from pathlib import Path

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


# List of files to be sorted
files = [
    "1_ACE logo.jpg",
    "2_EESL Logo Branding C2C (1)-01.png",
    "3_GGGI Logo New Green.png"
]

# Priority mapping: GGGI first, then ACE, then EESL
priority = {"GGGI": 0, "ACE": 1, "EESL": 2}

@login_required
def resources(request):
    lead_partner_logos = get_all_files("static/images/logos/lead_partners/")
    lead_partner_logos = sort_files(lead_partner_logos, priority)
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


def sort_files(files, priority):
    """
    Sorts a list of filenames based on the order defined in the priority mapping.
    Any filenames not matching the keys will be placed at the end.
    """
    return sorted(
        files,
        key=lambda filename: next(
            (priority[key] for key in priority if key in filename), 
            float('inf')
        )
    )
