from rest_framework.permissions import BasePermission

from accounts.models import UserProfile


ADMIN_ROLES = {UserProfile.Role.ADMIN, UserProfile.Role.SUPERADMIN}


class IsAdminUser(BasePermission):
    """Only allows access to users with admin or superadmin role (is_staff=True)."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_staff):
            return False
        try:
            return request.user.userprofile.role in ADMIN_ROLES
        except Exception:
            return False
