"""
API views for handling building certification and BoQ file uploads/serving.
Files are stored on disk and access is restricted to admin users.
"""

import logging
import mimetypes
import os

from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

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
    mime = uploaded_file.content_type or ""
    if mime and mime not in ALLOWED_MIME_TYPES:
        return f"MIME type '{mime}' is not allowed."
    return None


def _get_building(building_uuid_str):
    """Fetch building by UUID string. Returns (building, error_response)."""
    import uuid as uuid_lib
    try:
        uuid_obj = uuid_lib.UUID(str(building_uuid_str).strip())
        building = Building.objects.get(uuid=uuid_obj)
    except (ValueError, AttributeError, Building.DoesNotExist):
        return None, Response({"success": False, "error": "Building not found"}, status=status.HTTP_404_NOT_FOUND)
    return building, None


class BuildingFilesView(APIView):
    """
    GET  /api/buildings/files/?building_uuid=<uuid>[&type=certification|boq&file_id=<id>]
         - With type param: serves the actual file (FileResponse)
         - Without type param: returns current file state as JSON

    POST /api/buildings/files/
         Uploads certification and/or BoQ files.
         Expects multipart/form-data with:
           - building_uuid: str
           - has_certification: "yes" | "no"
           - certification_file: single file (optional)
           - has_boq: "yes" | "no"
           - boq_files: one or more files (optional)
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        building_uuid_str = request.GET.get("building_uuid", "")
        file_type = request.GET.get("type", "")

        if not building_uuid_str:
            return Response({"success": False, "error": "building_uuid is required"}, status=status.HTTP_400_BAD_REQUEST)

        building, err = _get_building(building_uuid_str)
        if err:
            return err

        # If type is specified, serve the actual file
        if file_type == "certification":
            if not building.certification_file:
                return Response({"error": "File not found."}, status=status.HTTP_404_NOT_FOUND)
            try:
                file_path = building.certification_file.path
                if not os.path.isfile(file_path):
                    return Response({"error": "File not found on disk."}, status=status.HTTP_404_NOT_FOUND)
                mime_type, _ = mimetypes.guess_type(file_path)
                return FileResponse(open(file_path, "rb"), content_type=mime_type or "application/octet-stream")
            except SuspiciousFileOperation:
                return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        elif file_type == "boq":
            file_id = request.GET.get("file_id")
            if not file_id:
                return Response({"error": "file_id required."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                boq_file = BuildingBoQFile.objects.get(id=int(file_id), building=building)
                file_path = boq_file.file.path
                if not os.path.isfile(file_path):
                    return Response({"error": "File not found on disk."}, status=status.HTTP_404_NOT_FOUND)
                mime_type, _ = mimetypes.guess_type(file_path)
                return FileResponse(open(file_path, "rb"), content_type=mime_type or "application/octet-stream")
            except (ValueError, BuildingBoQFile.DoesNotExist, SuspiciousFileOperation):
                return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        # No type param — return current file state as JSON
        cert_info = None
        if building.certification_file:
            cert_info = {
                "name": os.path.basename(building.certification_file.name),
                "url": f"/api/buildings/files/?building_uuid={building.uuid}&type=certification",
            }

        boq_info = [
            {
                "id": bf.id,
                "name": bf.original_filename or os.path.basename(bf.file.name),
                "url": f"/api/buildings/files/?building_uuid={building.uuid}&type=boq&file_id={bf.id}",
            }
            for bf in building.boq_files.all()
        ]

        return Response({
            "success": True,
            "has_certification": building.has_certification,
            "has_boq": building.has_boq,
            "certification_file": cert_info,
            "boq_files": boq_info,
        })

    def post(self, request):
        building_uuid_str = request.data.get("building_uuid", "")
        if not building_uuid_str:
            return Response({"success": False, "error": "building_uuid is required"}, status=status.HTTP_400_BAD_REQUEST)

        building, err = _get_building(building_uuid_str)
        if err:
            return err

        has_certification = request.data.get("has_certification", "no") in ("yes", "true", "1")
        has_boq = request.data.get("has_boq", "no") in ("yes", "true", "1")

        building.has_certification = has_certification
        building.has_boq = has_boq

        # --- Certification file ---
        if has_certification:
            cert_file = request.FILES.get("certification_file")
            if cert_file:
                err_msg = _validate_file(cert_file)
                if err_msg:
                    return Response({"success": False, "error": f"Certification file: {err_msg}"}, status=status.HTTP_400_BAD_REQUEST)
                # Delete previous certification file if present
                if building.certification_file:
                    try:
                        old_path = building.certification_file.path
                        if os.path.isfile(old_path):
                            os.remove(old_path)
                    except Exception:
                        pass
                building.certification_file = cert_file
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

        # --- BoQ files ---
        if has_boq:
            new_boq_files = request.FILES.getlist("boq_files")
            if new_boq_files:
                for f in new_boq_files:
                    err_msg = _validate_file(f)
                    if err_msg:
                        return Response({"success": False, "error": f"BoQ file '{f.name}': {err_msg}"}, status=status.HTTP_400_BAD_REQUEST)
                # Delete previous BoQ files
                for old_file in building.boq_files.all():
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
                    )
        else:
            # has_boq=no — remove all existing BoQ files
            for old_file in building.boq_files.all():
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
                "url": f"/api/buildings/files/?building_uuid={building.uuid}&type=certification",
            }

        boq_info = [
            {
                "id": bf.id,
                "name": bf.original_filename or os.path.basename(bf.file.name),
                "url": f"/api/buildings/files/?building_uuid={building.uuid}&type=boq&file_id={bf.id}",
            }
            for bf in building.boq_files.all()
        ]

        logger.info(f"Files uploaded for building {building.id}: cert={has_certification}, boq={has_boq}")

        return Response({
            "success": True,
            "has_certification": building.has_certification,
            "has_boq": building.has_boq,
            "certification_file": cert_info,
            "boq_files": boq_info,
        })

    def delete(self, request):
        """
        DELETE /api/buildings/files/?building_uuid=<uuid>&type=certification|boq&file_id=<id>
        Deletes a specific file from the building.
        """
        building_uuid_str = request.GET.get("building_uuid", "")
        file_type = request.GET.get("type", "")

        if not building_uuid_str:
            return Response({"success": False, "error": "building_uuid is required"}, status=status.HTTP_400_BAD_REQUEST)

        building, err = _get_building(building_uuid_str)
        if err:
            return err

        if file_type == "certification":
            if not building.certification_file:
                return Response({"success": False, "error": "No certification file found."}, status=status.HTTP_404_NOT_FOUND)
            try:
                old_path = building.certification_file.path
                if os.path.isfile(old_path):
                    os.remove(old_path)
            except Exception:
                pass
            building.certification_file = None
            building.has_certification = False
            building.save()
            return Response({"success": True})

        elif file_type == "boq":
            file_id = request.GET.get("file_id")
            if not file_id:
                return Response({"success": False, "error": "file_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                boq_file = BuildingBoQFile.objects.get(id=int(file_id), building=building)
                try:
                    if os.path.isfile(boq_file.file.path):
                        os.remove(boq_file.file.path)
                except Exception:
                    pass
                boq_file.delete()
                # If no more BoQ files, clear the flag
                if not building.boq_files.exists():
                    building.has_boq = False
                    building.save()
                return Response({"success": True})
            except (ValueError, BuildingBoQFile.DoesNotExist):
                return Response({"success": False, "error": "File not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"success": False, "error": "type must be 'certification' or 'boq'."}, status=status.HTTP_400_BAD_REQUEST)
