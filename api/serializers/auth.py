from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from allauth.account.models import EmailAddress

from accounts.models import UserProfile

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        # Django's ModelBackend supports username= kwarg; allauth uses email as username
        user = authenticate(request=self.context.get("request"), username=email, password=password)

        if user is None:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_staff:
            raise serializers.ValidationError(
                {"non_field_errors": "Access restricted to admin users only."},
                code="not_admin",
            )

        email_verified = EmailAddress.objects.filter(user=user, verified=True).exists()
        if not email_verified:
            raise serializers.ValidationError({"email": "Email address is not verified."})

        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="userprofile.role", read_only=True, default=None)

    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "is_staff", "is_superuser", "role"]
        read_only_fields = fields


class CountryField(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class RegionField(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class CityField(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class UserProfileSerializer(serializers.ModelSerializer):
    country = CountryField(read_only=True)
    region = RegionField(read_only=True)
    city = CityField(read_only=True)

    class Meta:
        model = UserProfile
        fields = ["role", "country", "region", "city", "consent_flag"]
        read_only_fields = fields


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating CustomUser fields: username, first_name, last_name."""

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]

    def validate_username(self, value):
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value


class ProfileUserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating UserProfile fields: country, region, city, consent_flag."""

    class Meta:
        model = UserProfile
        fields = ["country", "region", "city", "consent_flag"]
