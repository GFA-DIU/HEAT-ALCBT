"""Shared utilities for the API module."""
import csv
import io

from django.core.paginator import Paginator


def paginate_queryset(queryset, request, per_page=10):
    """
    Paginate a queryset using Django's Paginator.
    Query params: page (default 1), page_size (default per_page, max 100).
    Returns (page_object, meta_dict).
    """
    try:
        page_size = min(100, max(1, int(request.query_params.get("page_size", per_page))))
    except (ValueError, TypeError):
        page_size = per_page

    try:
        page_number = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        page_number = 1

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page_number)

    meta = {
        "total": paginator.count,
        "page": page_obj.number,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
    }
    return page_obj, meta


def parse_csv(file_obj):
    """
    Parse an uploaded CSV file. Returns list of rows as lists of strings.
    Skips empty rows.
    """
    decoded = file_obj.read().decode("utf-8-sig")
    reader = csv.reader(io.StringIO(decoded))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    return rows


def render_csv_response(rows, filename):
    """
    Build a StreamingHttpResponse for CSV export.
    rows: iterable of lists.
    """
    from django.http import HttpResponse
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    for row in rows:
        writer.writerow(row)
    return response