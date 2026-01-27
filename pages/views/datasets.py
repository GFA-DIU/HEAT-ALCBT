
from django.shortcuts import render


def datasets(request):
    # Logic to handle the request and prepare context
    context = {}
    return render(request, "pages/home/datasets.html", context)