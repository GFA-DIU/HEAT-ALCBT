import os
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# The logos themselves are read from the folder, so adding a file is enough to
# show it. Only the lead partners have a fixed order; development partners fall
# back to alphabetical. Each key is matched as a substring of the filename, so a
# renamed file keeps its place as long as the partner's initials survive.
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
    return render(request, "pages/home/resources.html", context)


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
