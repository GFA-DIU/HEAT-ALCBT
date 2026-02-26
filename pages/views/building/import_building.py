
from django.shortcuts import render


def view_import_dialog(request):
    return render(request, "pages/home/import-dialog/import-dialog.html")

def view_initial_import_dialog(request):
    return render(request, "pages/home/import-dialog/initial-dialog.html")

def view_import_building_step(request, step_id):
    print(f"Received request for import building step: {step_id}")
    return render(request, f"pages/home/import-dialog/{step_id}.html")
