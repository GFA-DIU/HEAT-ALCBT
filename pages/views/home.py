import logging

from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)

items = ["Apple", "Banana", "Cherry", "Date", "Elderberry"]

@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def item_list(request):
    global items
    context = {"items": items}
    
    logger.info("Access list view.")

    if request.method == "POST":
        new_item = request.POST.get("item")
        if new_item and len(items) < 5:
            logger.info("Add item: '%s' to list", new_item)
            items.append(new_item)
        return render(
            request, "pages/home/building_list/item.html", context
        )  # Partial update for POST

    elif request.method == "DELETE":
        item_to_delete = request.GET.get("item")
        if item_to_delete in items:
            logger.info("Delete item '%s' from list", item_to_delete)
            items.remove(item_to_delete)
        return render(
            request, "pages/home/building_list/item.html", context
        )  # Partial update for DELETE

    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/home/home.html", context)
