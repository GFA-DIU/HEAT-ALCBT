import json

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .forms import AssemblyForm

# Hardcoded list of materials

MATERIALS = [
    {"id": 1, "name": "Concrete", "country": "USA", "impacts": "High", "city": "New York", "category": "Building", "source": "QNG-database", "type": "Raw"},
    {"id": 2, "name": "Steel", "country": "Germany", "impacts": "Medium", "city": "Berlin", "category": "Infrastructure", "source": "ABC-database", "type": "Processed"},
    {"id": 3, "name": "Wood", "country": "Canada", "impacts": "Low", "city": "Vancouver", "category": "Building", "source": "XYZ-database", "type": "Natural"},
    {"id": 4, "name": "Brick", "country": "UK", "impacts": "Medium", "city": "London", "category": "Residential", "source": "LMN-database", "type": "Manufactured"},
    {"id": 5, "name": "Glass", "country": "France", "impacts": "High", "city": "Paris", "category": "Commercial", "source": "OPQ-database", "type": "Processed"},
    {"id": 6, "name": "Aluminum", "country": "Australia", "impacts": "High", "city": "Sydney", "category": "Industrial", "source": "RST-database", "type": "Raw"},
    {"id": 7, "name": "Copper", "country": "Chile", "impacts": "Medium", "city": "Santiago", "category": "Electrical", "source": "UVW-database", "type": "Raw"},
    {"id": 8, "name": "Plastic", "country": "China", "impacts": "High", "city": "Beijing", "category": "Packaging", "source": "XYZ-database", "type": "Synthetic"},
    {"id": 9, "name": "Ceramic", "country": "Italy", "impacts": "Low", "city": "Rome", "category": "Decorative", "source": "ABC-database", "type": "Natural"},
    {"id": 10, "name": "Composite", "country": "Japan", "impacts": "Medium", "city": "Tokyo", "category": "Aerospace", "source": "LMN-database", "type": "Synthetic"},
]

@require_http_methods(["GET", "POST", "DELETE"])
def basic_assembly_info(request):
    print("basic_assembly POST")
    print(request.POST)
    materials_selected = []
    # if this is a POST request we need to process the form data
    if request.method == "POST" and request.POST.get("action") == "submitted":
        print("I'm here")
        print(request.POST)
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
            
            message = f"Changes for {assembly_name} saved successfully! {country}, {measurement_type}, {public}, {selected_materials}"
            # redirect to a new URL: Currently reload empty Form
            return JsonResponse({'message': message}, status=200)
        else:
            # Respond with errors
            return JsonResponse({'errors': form.errors}, status=400)
    elif request.method == "POST":
        # create a form instance and populate it with data from the request: 
        
        added_material = request.POST.get("material")
        added_material = [m for m in MATERIALS if m.get("id") == int(added_material)]
        materials_selected.extend(added_material)
        return render(request, "pages/assembly/material_list/material_list_delete.html", {"materials": MATERIALS, "materials_selected": materials_selected})
    
    # if a GET (or any other method) we'll create a blank form
    else:
        form = AssemblyForm() 

    return render(request, "pages/assembly/assembly.html", {"form": form, "materials": MATERIALS, "materials_selected": materials_selected})