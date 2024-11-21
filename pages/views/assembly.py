from django.shortcuts import render
from django.http import JsonResponse

from .forms import AssemblyForm

# Hardcoded list of materials
MATERIALS = [
    {"id": 1, "name": "Concrete"},
    {"id": 2, "name": "Steel"},
    {"id": 3, "name": "Wood"},
    {"id": 4, "name": "Brick"},
    {"id": 5, "name": "Glass"},
    {"id": 6, "name": "Aluminum"},
    {"id": 7, "name": "Copper"},
    {"id": 8, "name": "Plastic"},
    {"id": 9, "name": "Ceramic"},
    {"id": 10, "name": "Composite"},
    {"id": 11, "name": "Insulation"},
    {"id": 12, "name": "Asphalt"},
    {"id": 13, "name": "Stone"},
    {"id": 14, "name": "Clay"},
    {"id": 15, "name": "Gypsum"},
    {"id": 16, "name": "Fiberglass"},
    {"id": 17, "name": "Bamboo"},
    {"id": 18, "name": "Carbon Fiber"},
    {"id": 19, "name": "Titanium"},
    {"id": 20, "name": "Lead"}
]

def basic_assembly_info(request):
    # if this is a POST request we need to process the form data
    if request.method == "POST":
        # create a form instance and populate it with data from the request: 
        form = AssemblyForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            assembly_name = form.cleaned_data['assembly_name']
            country = form.cleaned_data['country']
            measurement_type = form.cleaned_data['measurement_type']
            public = form.cleaned_data['public']
            
            # Process selected materials
            selected_materials = []
            for key, value in request.POST.items():
                if key.startswith('material_') and key.endswith('_quantity'):
                    material_id = key.split('_')[1]
                    quantity = value
                    material_name = next((m['name'] for m in MATERIALS if str(m['id']) == material_id), 'Unknown')
                    selected_materials.append({'id': material_id, 'name': material_name, 'quantity': quantity})
            
            message = f"Changes for {assembly_name} saved successfully!"
            # redirect to a new URL: Currently reload empty Form
            return JsonResponse({'message': message}, status=200)
        else:
            # Respond with errors
            return JsonResponse({'errors': form.errors}, status=400)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = AssemblyForm() 

    return render(request, "pages/assembly/assembly_form.html", {"form": form, "materials": MATERIALS})