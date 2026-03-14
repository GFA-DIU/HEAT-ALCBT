from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from api.permissions import IsAdminUser
from api.serializers.auth import (
    LoginSerializer,
    UserSerializer,
    UserProfileSerializer,
    ProfileUpdateSerializer,
    ProfileUserProfileUpdateSerializer,
)

User = get_user_model()


class AdminLoginView(APIView):
    """POST /api/auth/login/ — authenticate admin user, return JWT tokens + user data."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            errors = serializer.errors
            # Surface not_admin as 403
            non_field = errors.get("non_field_errors", [])
            if any("Access restricted" in str(e) for e in non_field):
                return Response(
                    {"detail": "Access restricted to admin users only."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )


class AdminLogoutView(APIView):
    """POST /api/auth/logout/ — blacklist refresh token."""

    permission_classes = [IsAdminUser]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


class AdminTokenRefreshView(TokenRefreshView):
    """POST /api/auth/token/refresh/ — refresh access token."""

    permission_classes = [AllowAny]


class AdminForgotPasswordView(APIView):
    """POST /api/auth/forgot-password/ — send password reset email for admin users."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip()
        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if the email belongs to a staff user
        user = User.objects.filter(email=email, is_staff=True).first()
        if user is None:
            # Check if user exists at all (non-staff)
            non_staff_user = User.objects.filter(email=email).first()
            if non_staff_user is not None:
                # Email exists but user is not staff
                return Response(
                    {"detail": "Access restricted to admin users only."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Non-existent email — return 200 for security (don't reveal existence)
            return Response(
                {"detail": "If an account with that email exists, a password reset email has been sent."},
                status=status.HTTP_200_OK,
            )

        # Trigger allauth password reset
        from allauth.account.forms import ResetPasswordForm
        form = ResetPasswordForm(data={"email": email})
        if form.is_valid():
            form.save(request)

        return Response(
            {"detail": "If an account with that email exists, a password reset email has been sent."},
            status=status.HTTP_200_OK,
        )


class AdminProfileView(APIView):
    """GET/PATCH /api/auth/profile/ — get and update current admin's profile."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        user = request.user
        user_data = UserSerializer(user).data
        try:
            profile = user.userprofile
            profile_data = UserProfileSerializer(profile).data
        except Exception:
            profile_data = None

        return Response(
            {"user": user_data, "profile": profile_data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        user = request.user
        user_serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)

        if not user_serializer.is_valid():
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_serializer.save()

        # Also update UserProfile if profile fields are present
        profile_fields = {"country", "region", "city", "consent_flag"}
        profile_data = {k: v for k, v in request.data.items() if k in profile_fields}
        if profile_data:
            try:
                profile = user.userprofile
                profile_serializer = ProfileUserProfileUpdateSerializer(
                    profile, data=profile_data, partial=True
                )
                if profile_serializer.is_valid():
                    profile_serializer.save()
            except Exception:
                pass

        # Return updated data
        updated_user_data = UserSerializer(user).data
        try:
            profile = user.userprofile
            updated_profile_data = UserProfileSerializer(profile).data
        except Exception:
            updated_profile_data = None

        return Response(
            {"user": updated_user_data, "profile": updated_profile_data},
            status=status.HTTP_200_OK,
        )
