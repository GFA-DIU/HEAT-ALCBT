"""
Views for handling building certification and BoQ file uploads.
Files are stored on disk and access is restricted to building owner + admin.
"""

import logging
import mimetypes
import os
import uuid as uuid_lib

from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_http_methods

from pages.models.building import Building, BuildingBoQFile

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def _validate_file(uploaded_file):
    """Return an error string if the file is invalid, else None."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"File type '{ext}' is not allowed. Use images or PDFs."
    if uploaded_file.size > MAX_FILE_SIZE_BYTES:
        return "File exceeds the 20 MB size limit."
    # Check MIME type reported by browser (not fully trusted, but adds a layer)
    mime = uploaded_file.content_type or ""
    if mime and mime not in ALLOWED_MIME_TYPES:
        return f"MIME type '{mime}' is not allowed."
    return None


def _get_building_for_owner(building_uuid_str, user):
    """Fetch building checking ownership. Returns (building, error_response)."""
    try:
        uuid_obj = uuid_lib.UUID(building_uuid_str)
        building = Building.objects.get(uuid=uuid_obj)
    except (ValueError, Building.DoesNotExist):
        return None, JsonResponse({"success": False, "error": "Building not found"}, status=404)

    if not (user.is_staff or building.created_by == user):
        return None, JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    return building, None


@login_required
@require_http_methods(["POST"])
def upload_building_files(request):
    """
    Upload certification file and/or BoQ files for a building.

    Expects multipart/form-data with:
      - building_uuid: str
      - has_certification: "yes" | "no"
      - certification_file: single file (optional, required when has_certification=yes)
      - has_boq: "yes" | "no"
      - boq_files: one or more files (optional, required when has_boq=yes)
    """
    building_uuid_str = request.POST.get("building_uuid", "")
    if not building_uuid_str:
        return JsonResponse({"success": False, "error": "Building UUID is required"}, status=400)

    building, err = _get_building_for_owner(building_uuid_str, request.user)
    if err:
        return err

    has_certification = request.POST.get("has_certification", "no") in ("yes", "true", "1")
    has_design_drawings = request.POST.get("has_design_drawings", "no") in ("yes", "true", "1")
    has_boq = request.POST.get("has_boq", "no") in ("yes", "true", "1")

    building.has_certification = has_certification
    building.has_design_drawings = has_design_drawings
    building.has_boq = has_boq

    # --- Certification file ---
    if has_certification:
        cert_file = request.FILES.get("certification_file")
        if cert_file:
            err_msg = _validate_file(cert_file)
            if err_msg:
                return JsonResponse({"success": False, "error": f"Certification file: {err_msg}"}, status=400)
            # Delete previous certification file if present
            if building.certification_file:
                try:
                    old_path = building.certification_file.path
                    if os.path.isfile(old_path):
                        os.remove(old_path)
                except Exception:
                    pass
            building.certification_file = cert_file
        # If no new file submitted but has_certification=yes, keep existing file
    else:
        # has_certification=no — clear any existing file
        if building.certification_file:
            try:
                old_path = building.certification_file.path
                if os.path.isfile(old_path):
                    os.remove(old_path)
            except Exception:
                pass
            building.certification_file = None

    building.save()

    # --- Design drawing files ---
    if has_design_drawings:
        new_drawing_files = request.FILES.getlist("design_drawing_files")
        if new_drawing_files:
            for f in new_drawing_files:
                err_msg = _validate_file(f)
                if err_msg:
                    return JsonResponse({"success": False, "error": f"Design drawing '{f.name}': {err_msg}"}, status=400)
            # Delete previous drawing files
            for old_file in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_DRAWING):
                try:
                    if os.path.isfile(old_file.file.path):
                        os.remove(old_file.file.path)
                except Exception:
                    pass
                old_file.delete()
            for f in new_drawing_files:
                BuildingBoQFile.objects.create(
                    building=building,
                    file=f,
                    original_filename=f.name,
                    file_type=BuildingBoQFile.FILE_TYPE_DRAWING,
                )
    else:
        # has_design_drawings=no — remove all existing drawing files
        for old_file in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_DRAWING):
            try:
                if os.path.isfile(old_file.file.path):
                    os.remove(old_file.file.path)
            except Exception:
                pass
            old_file.delete()

    # --- BoQ files ---
    if has_boq:
        new_boq_files = request.FILES.getlist("boq_files")
        if new_boq_files:
            # Validate all files first
            for f in new_boq_files:
                err_msg = _validate_file(f)
                if err_msg:
                    return JsonResponse({"success": False, "error": f"BoQ file '{f.name}': {err_msg}"}, status=400)
            # Delete previous BoQ files
            for old_file in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_BOQ):
                try:
                    if os.path.isfile(old_file.file.path):
                        os.remove(old_file.file.path)
                except Exception:
                    pass
                old_file.delete()
            # Save new ones
            for f in new_boq_files:
                BuildingBoQFile.objects.create(
                    building=building,
                    file=f,
                    original_filename=f.name,
                    file_type=BuildingBoQFile.FILE_TYPE_BOQ,
                )
        # If no new files submitted but has_boq=yes, keep existing files
    else:
        # has_boq=no — remove all existing BoQ files
        for old_file in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_BOQ):
            try:
                if os.path.isfile(old_file.file.path):
                    os.remove(old_file.file.path)
            except Exception:
                pass
            old_file.delete()

    # Build response with current state
    cert_info = None
    if building.certification_file:
        cert_info = {
            "name": os.path.basename(building.certification_file.name),
            "url": f"/building/files/serve/?building_uuid={building.uuid}&type=certification",
        }

    drawing_info = [
        {
            "id": bf.id,
            "name": bf.original_filename or os.path.basename(bf.file.name),
            "url": f"/building/files/serve/?building_uuid={building.uuid}&type=boq&file_id={bf.id}",
        }
        for bf in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_DRAWING)
    ]

    boq_info = [
        {
            "id": bf.id,
            "name": bf.original_filename or os.path.basename(bf.file.name),
            "url": f"/building/files/serve/?building_uuid={building.uuid}&type=boq&file_id={bf.id}",
        }
        for bf in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_BOQ)
    ]

    logger.info(f"Files uploaded for building {building.id}: cert={has_certification}, drawings={has_design_drawings}, boq={has_boq}")

    return JsonResponse({
        "success": True,
        "has_certification": building.has_certification,
        "has_design_drawings": building.has_design_drawings,
        "has_boq": building.has_boq,
        "certification_file": cert_info,
        "design_drawing_files": drawing_info,
        "boq_files": boq_info,
    })


@login_required
@require_http_methods(["GET"])
def serve_building_file(request):
    """
    Securely serve a building file.
    Only accessible by building owner or admin staff.

    Query params:
      - building_uuid: str
      - type: "certification" | "boq"
      - file_id: int (required when type=boq)
    """
    building_uuid_str = request.GET.get("building_uuid", "")
    file_type = request.GET.get("type", "")

    if not building_uuid_str or not file_type:
        return HttpResponseForbidden("Invalid request.")

    building, err = _get_building_for_owner(building_uuid_str, request.user)
    if err:
        return HttpResponseForbidden("Access denied.")

    if file_type == "certification":
        if not building.certification_file:
            return HttpResponseForbidden("File not found.")
        try:
            file_path = building.certification_file.path
            if not os.path.isfile(file_path):
                return HttpResponseForbidden("File not found on disk.")
            mime_type, _ = mimetypes.guess_type(file_path)
            return FileResponse(open(file_path, "rb"), content_type=mime_type or "application/octet-stream")
        except SuspiciousFileOperation:
            return HttpResponseForbidden("Access denied.")

    elif file_type == "boq":
        file_id = request.GET.get("file_id")
        if not file_id:
            return HttpResponseForbidden("file_id required.")
        try:
            boq_file = BuildingBoQFile.objects.get(id=int(file_id), building=building)
            file_path = boq_file.file.path
            if not os.path.isfile(file_path):
                return HttpResponseForbidden("File not found on disk.")
            mime_type, _ = mimetypes.guess_type(file_path)
            return FileResponse(open(file_path, "rb"), content_type=mime_type or "application/octet-stream")
        except (ValueError, BuildingBoQFile.DoesNotExist, SuspiciousFileOperation):
            return HttpResponseForbidden("Access denied.")

    return HttpResponseForbidden("Invalid file type.")


@login_required
@require_http_methods(["GET"])
def get_building_files(request):
    """
    Return current file upload state for a building (for edit mode).
    Only accessible by building owner or admin staff.
    """
    building_uuid_str = request.GET.get("building_uuid", "")
    if not building_uuid_str:
        return JsonResponse({"success": False, "error": "Building UUID required"}, status=400)

    building, err = _get_building_for_owner(building_uuid_str, request.user)
    if err:
        return err

    cert_info = None
    if building.certification_file:
        cert_info = {
            "name": os.path.basename(building.certification_file.name),
            "url": f"/building/files/serve/?building_uuid={building.uuid}&type=certification",
        }

    drawing_info = [
        {
            "id": bf.id,
            "name": bf.original_filename or os.path.basename(bf.file.name),
            "url": f"/building/files/serve/?building_uuid={building.uuid}&type=boq&file_id={bf.id}",
        }
        for bf in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_DRAWING)
    ]

    boq_info = [
        {
            "id": bf.id,
            "name": bf.original_filename or os.path.basename(bf.file.name),
            "url": f"/building/files/serve/?building_uuid={building.uuid}&type=boq&file_id={bf.id}",
        }
        for bf in building.boq_files.filter(file_type=BuildingBoQFile.FILE_TYPE_BOQ)
    ]

    return JsonResponse({
        "success": True,
        "has_certification": building.has_certification,
        "has_design_drawings": building.has_design_drawings,
        "has_boq": building.has_boq,
        "certification_file": cert_info,
        "design_drawing_files": drawing_info,
        "boq_files": boq_info,
    })