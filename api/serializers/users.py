from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation
from cities_light.models import Country
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from accounts.models import CustomCity, CustomRegion, UserProfile
from pages.models.organisation import Organisation, OrganisationMembership

User = get_user_model()


# ---------------------------------------------------------------------------
# User list / detail
# ---------------------------------------------------------------------------

class UserOrganisationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    role = serializers.CharField()


class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    organisations = serializers.SerializerMethodField()
    countries = serializers.SerializerMethodField()
    app_access = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name", "full_name",
            "role", "organisations", "countries", "app_access",
            "last_login", "is_active", "date_joined", "profile",
        ]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_role(self, obj):
        try:
            return obj.userprofile.role
        except Exception:
            return UserProfile.Role.VIEWER

    def get_organisations(self, obj):
        memberships = obj.organisation_memberships.select_related("organisation")
        return [
            {"id": str(m.organisation.id), "name": m.organisation.name, "role": m.role}
            for m in memberships
        ]

    def get_countries(self, obj):
        result = []
        for m in obj.organisation_memberships.prefetch_related("countries"):
            for c in m.countries.all():
                if not any(item["id"] == c.id for item in result):
                    result.append({"id": c.id, "name": c.name})
        return result

    def get_app_access(self, obj):
        """Returns list of apps the user has access to: web and/or admin."""
        access = ["web"]  # All users with accounts have web access
        if obj.is_staff:
            access.append("admin")
        return access

    def get_is_active(self, obj):
        """Active = account is active AND email is verified."""
        if not obj.is_active:
            return False
        try:
            return EmailAddress.objects.filter(user=obj, verified=True).exists()
        except Exception:
            return obj.is_active

    def get_profile(self, obj):
        try:
            p = obj.userprofile
            return {
                "country": {"id": p.country.id, "name": p.country.name} if p.country else None,
                "region": {"id": p.region.id, "name": p.region.name} if p.region else None,
                "city": {"id": p.city.id, "name": p.city.name} if p.city else None,
                "consent_flag": p.consent_flag,
            }
        except Exception:
            return None


# ---------------------------------------------------------------------------
# User create
# ---------------------------------------------------------------------------

class UserCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, default="")
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=UserProfile.Role.choices)
    organisation_id = serializers.UUIDField(required=False, allow_null=True)
    organisation_role = serializers.ChoiceField(
        choices=OrganisationMembership.MemberRole.choices,
        required=False,
        default=OrganisationMembership.MemberRole.VIEWER,
    )
    country_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
        help_text="IDs of countries to assign within the organisation membership.",
    )
    all_countries = serializers.BooleanField(
        required=False, default=False,
        help_text="If true, assigns all available countries to this membership.",
    )
    # UserProfile location fields (user's personal location)
    profile_country_id = serializers.IntegerField(required=False, allow_null=True)
    profile_region_id = serializers.IntegerField(required=False, allow_null=True)
    profile_city_id = serializers.IntegerField(required=False, allow_null=True)
    consent_flag = serializers.BooleanField(required=False, default=True)

    def validate_email(self, value):
        if EmailAddress.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs.get("organisation_id") is None and attrs.get("country_ids"):
            raise serializers.ValidationError(
                {"country_ids": "Cannot assign countries without an organisation."}
            )
        return attrs

    def create(self, validated_data):
        email = validated_data["email"]
        role = validated_data["role"]
        org_id = validated_data.get("organisation_id")
        org_role = validated_data.get("organisation_role", OrganisationMembership.MemberRole.VIEWER)
        country_ids = validated_data.get("country_ids", [])
        all_countries = validated_data.get("all_countries", False)

        with transaction.atomic():
            username = email.split("@")[0]
            base = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1

            # Determine is_staff / is_superuser from role
            is_staff = role in (UserProfile.Role.ADMIN, UserProfile.Role.SUPERADMIN)
            is_superuser = role == UserProfile.Role.SUPERADMIN

            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=validated_data["first_name"],
                last_name=validated_data.get("last_name", ""),
                is_staff=is_staff,
                is_superuser=is_superuser,
                # No password — user must set one via password reset
                password=None,
            )

            # Set role and location on UserProfile
            profile = user.userprofile
            profile.role = role
            if validated_data.get("profile_country_id"):
                profile.country_id = validated_data["profile_country_id"]
            if validated_data.get("profile_region_id"):
                profile.region_id = validated_data["profile_region_id"]
            if validated_data.get("profile_city_id"):
                profile.city_id = validated_data["profile_city_id"]
            profile.consent_flag = validated_data.get("consent_flag", True)
            profile.save()

            # Allauth EmailAddress (unverified — they'll click link)
            EmailAddress.objects.create(
                user=user, email=email, primary=True, verified=False
            )

            # Organisation membership
            if org_id:
                try:
                    org = Organisation.objects.get(pk=org_id)
                    membership, _ = OrganisationMembership.objects.get_or_create(
                        organisation=org, user=user, defaults={"role": org_role}
                    )
                    if all_countries:
                        membership.countries.set(Country.objects.all())
                    elif country_ids:
                        membership.countries.set(Country.objects.filter(id__in=country_ids))
                except Organisation.DoesNotExist:
                    pass

        # Send verification email (outside transaction)
        request = self.context.get("request")
        if request:
            try:
                send_email_confirmation(request, user, signup=True)
            except Exception:
                pass

        return user


# ---------------------------------------------------------------------------
# User update
# ---------------------------------------------------------------------------

class UserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    role = serializers.ChoiceField(choices=UserProfile.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)
    organisation_id = serializers.UUIDField(required=False, allow_null=True)
    organisation_role = serializers.ChoiceField(
        choices=OrganisationMembership.MemberRole.choices, required=False,
    )
    country_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False,
    )
    all_countries = serializers.BooleanField(required=False)
    # UserProfile location fields
    profile_country_id = serializers.IntegerField(required=False, allow_null=True)
    profile_region_id = serializers.IntegerField(required=False, allow_null=True)
    profile_city_id = serializers.IntegerField(required=False, allow_null=True)
    consent_flag = serializers.BooleanField(required=False)

    def validate_email(self, value):
        user = self.context.get("user_instance")
        if EmailAddress.objects.filter(email__iexact=value).exclude(user=user).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def update(self, instance, validated_data):
        with transaction.atomic():
            # Basic fields
            for field in ("first_name", "last_name", "is_active"):
                if field in validated_data:
                    setattr(instance, field, validated_data[field])

            new_email = validated_data.get("email")
            if new_email and new_email != instance.email:
                instance.email = new_email
                # Update allauth EmailAddress too
                EmailAddress.objects.filter(user=instance, primary=True).update(
                    email=new_email, verified=False
                )

            new_role = validated_data.get("role")
            profile_fields = {}
            if new_role:
                instance.is_staff = new_role in (UserProfile.Role.ADMIN, UserProfile.Role.SUPERADMIN)
                instance.is_superuser = new_role == UserProfile.Role.SUPERADMIN
                profile_fields["role"] = new_role
            if "profile_country_id" in validated_data:
                profile_fields["country_id"] = validated_data["profile_country_id"]
            if "profile_region_id" in validated_data:
                profile_fields["region_id"] = validated_data["profile_region_id"]
            if "profile_city_id" in validated_data:
                profile_fields["city_id"] = validated_data["profile_city_id"]
            if "consent_flag" in validated_data:
                profile_fields["consent_flag"] = validated_data["consent_flag"]
            if profile_fields:
                try:
                    for attr, val in profile_fields.items():
                        setattr(instance.userprofile, attr, val)
                    instance.userprofile.save()
                except Exception:
                    pass

            instance.save()

            # Organisation membership update
            org_id = validated_data.get("organisation_id")
            if org_id is not None:
                try:
                    org = Organisation.objects.get(pk=org_id)
                    org_role = validated_data.get("organisation_role", OrganisationMembership.MemberRole.VIEWER)
                    membership, created = OrganisationMembership.objects.get_or_create(
                        organisation=org, user=instance, defaults={"role": org_role}
                    )
                    if not created and "organisation_role" in validated_data:
                        membership.role = org_role
                        membership.save(update_fields=["role"])

                    if validated_data.get("all_countries"):
                        membership.countries.set(Country.objects.all())
                    elif "country_ids" in validated_data:
                        membership.countries.set(
                            Country.objects.filter(id__in=validated_data["country_ids"])
                        )
                except Organisation.DoesNotExist:
                    pass

        return instance


# ---------------------------------------------------------------------------
# CSV import row serializer (reuses create logic)
# ---------------------------------------------------------------------------

class UserImportRowSerializer(serializers.Serializer):
    """Validates a single row from a users CSV import."""
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, default="")
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=UserProfile.Role.choices, default=UserProfile.Role.VIEWER)
    organisation_name = serializers.CharField(required=False, allow_blank=True)
    organisation_role = serializers.ChoiceField(
        choices=OrganisationMembership.MemberRole.choices,
        required=False,
        default=OrganisationMembership.MemberRole.VIEWER,
    )

    def validate_email(self, value):
        if EmailAddress.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(f"User with email '{value}' already exists.")
        return value
