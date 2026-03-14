import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdminUser
from api.serializers.users import (
    UserListSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserImportRowSerializer,
)
from api.utils import paginate_queryset, parse_csv, render_csv_response
from accounts.models import UserProfile
from pages.models.organisation import OrganisationMembership

logger = logging.getLogger(__name__)

User = get_user_model()


def _user_queryset(request):
    """Base queryset scoped to what the calling user may see."""
    qs = User.objects.select_related("userprofile").prefetch_related(
        "organisation_memberships__organisation",
        "organisation_memberships__countries",
    ).order_by("first_name", "last_name", "email")

    if not request.user.is_superuser:
        # Admins only see users within their own organisations
        qs = qs.filter(
            organisation_memberships__organisation__memberships__user=request.user
        ).distinct()

    return qs


class UserListCreateView(APIView):
    """
    GET  /api/users/  — list users (paginated, searchable, filterable)
    POST /api/users/  — create (add) a new user
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = _user_queryset(request)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(username__icontains=search)
            ).distinct()

        role = request.query_params.get("role", "").strip()
        if role:
            qs = qs.filter(userprofile__role=role)

        org_id = request.query_params.get("organisation", "").strip()
        if org_id:
            qs = qs.filter(organisation_memberships__organisation_id=org_id).distinct()

        page_obj, meta = paginate_queryset(qs, request)
        return Response({"results": UserListSerializer(page_obj, many=True).data, "pagination": meta})

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        logger.info("Admin %s created user %s", request.user, user)
        return Response(UserListSerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    """
    GET   /api/users/<pk>/  — user detail
    PATCH /api/users/<pk>/  — edit user
    """
    permission_classes = [IsAdminUser]

    def _get_user(self, pk, request):
        qs = _user_queryset(request)
        try:
            return qs.get(pk=pk)
        except User.DoesNotExist:
            return None

    def get(self, request, pk):
        user = self._get_user(pk, request)
        if user is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserListSerializer(user).data)

    def patch(self, request, pk):
        user = self._get_user(pk, request)
        if user is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserUpdateSerializer(
            instance=user, data=request.data, partial=True,
            context={"request": request, "user_instance": user},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        updated_user = serializer.save()
        logger.info("Admin %s updated user %s", request.user, updated_user)
        return Response(UserListSerializer(updated_user).data)


class UserExportView(APIView):
    """
    GET /api/users/export/
    Exports users as CSV.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = _user_queryset(request)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            ).distinct()

        rows = [["first_name", "last_name", "email", "role", "organisation", "organisation_role", "last_login", "email_verified"]]
        for user in qs:
            try:
                role = user.userprofile.role
            except Exception:
                role = UserProfile.Role.VIEWER

            try:
                from allauth.account.models import EmailAddress
                verified = EmailAddress.objects.filter(user=user, verified=True).exists()
            except Exception:
                verified = user.is_active

            memberships = user.organisation_memberships.select_related("organisation")
            if memberships.exists():
                for m in memberships:
                    rows.append([
                        user.first_name, user.last_name, user.email, role,
                        m.organisation.name, m.role,
                        user.last_login.isoformat() if user.last_login else "",
                        "yes" if verified else "no",
                    ])
            else:
                rows.append([
                    user.first_name, user.last_name, user.email, role,
                    "", "",
                    user.last_login.isoformat() if user.last_login else "",
                    "yes" if verified else "no",
                ])

        return render_csv_response(rows, "users_export.csv")


class UserImportView(APIView):
    """
    POST /api/users/import/
    CSV columns: first_name, last_name, email, role, organisation_name, organisation_role
    Header row is skipped if it matches column names.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rows = parse_csv(file)
        except Exception as e:
            return Response({"detail": f"Could not parse CSV: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        if not rows:
            return Response({"detail": "CSV file is empty."}, status=status.HTTP_400_BAD_REQUEST)

        # Skip header row if present
        EXPECTED_HEADERS = {"first_name", "last_name", "email", "role"}
        if rows and EXPECTED_HEADERS.issubset({c.lower().strip() for c in rows[0]}):
            rows = rows[1:]

        created_count = 0
        errors = []

        for i, row in enumerate(rows, start=2):
            if len(row) < 3:
                errors.append({"row": i, "errors": "Not enough columns (need at least first_name, last_name, email)."})
                continue

            data = {
                "first_name": row[0].strip() if len(row) > 0 else "",
                "last_name": row[1].strip() if len(row) > 1 else "",
                "email": row[2].strip() if len(row) > 2 else "",
                "role": row[3].strip() if len(row) > 3 else UserProfile.Role.VIEWER,
                "organisation_name": row[4].strip() if len(row) > 4 else "",
                "organisation_role": row[5].strip() if len(row) > 5 else OrganisationMembership.MemberRole.VIEWER,
            }

            row_serializer = UserImportRowSerializer(data=data)
            if not row_serializer.is_valid():
                errors.append({"row": i, "email": data.get("email"), "errors": row_serializer.errors})
                continue

            # Map organisation name → id
            org_id = None
            org_name = row_serializer.validated_data.get("organisation_name", "").strip()
            if org_name:
                from pages.models.organisation import Organisation
                org = Organisation.objects.filter(name__iexact=org_name).first()
                if org:
                    org_id = org.id

            create_data = {
                "first_name": row_serializer.validated_data["first_name"],
                "last_name": row_serializer.validated_data.get("last_name", ""),
                "email": row_serializer.validated_data["email"],
                "role": row_serializer.validated_data["role"],
                "organisation_id": org_id,
                "organisation_role": row_serializer.validated_data.get("organisation_role"),
            }

            create_serializer = UserCreateSerializer(data=create_data, context={"request": request})
            if not create_serializer.is_valid():
                errors.append({"row": i, "email": data.get("email"), "errors": create_serializer.errors})
                continue

            try:
                create_serializer.save()
                created_count += 1
            except Exception as e:
                errors.append({"row": i, "email": data.get("email"), "errors": str(e)})

        result = {"created": created_count}
        if errors:
            result["errors"] = errors
        return Response(result, status=status.HTTP_201_CREATED if created_count > 0 else status.HTTP_400_BAD_REQUEST)