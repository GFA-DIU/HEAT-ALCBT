from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import UserProfile
from api.emails import send_organisation_invitation
from pages.models.organisation import Organisation, OrganisationMembership

User = get_user_model()


# ---------------------------------------------------------------------------
# Nested helpers
# ---------------------------------------------------------------------------

class MemberUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "full_name", "role"]

    def get_role(self, obj):
        try:
            return obj.userprofile.role
        except Exception:
            return None

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class MembershipSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)
    countries = serializers.SerializerMethodField()

    class Meta:
        model = OrganisationMembership
        fields = ["id", "user", "role", "countries", "joined_at"]

    def get_countries(self, obj):
        return [{"id": c.id, "name": c.name} for c in obj.countries.all()]


# ---------------------------------------------------------------------------
# Invite user payload (used inside create/update)
# ---------------------------------------------------------------------------

class InviteUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=OrganisationMembership.MemberRole.choices)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email address.")
        return value


# ---------------------------------------------------------------------------
# Organisation create
# ---------------------------------------------------------------------------

class OrganisationCreateSerializer(serializers.ModelSerializer):
    invite_users = InviteUserSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Organisation
        fields = ["id", "name", "industry", "country", "city", "invite_users"]

    def create(self, validated_data):
        invite_users = validated_data.pop("invite_users", [])
        organisation = Organisation.objects.create(**validated_data)
        added_by = self.context.get("request").user if self.context.get("request") else None

        for invite in invite_users:
            user = User.objects.get(email=invite["email"])
            OrganisationMembership.objects.get_or_create(
                organisation=organisation,
                user=user,
                defaults={"role": invite["role"]},
            )
            _sync_user_role(user, invite["role"])
            if added_by:
                send_organisation_invitation(user, organisation, invite["role"], added_by)

        return organisation


# ---------------------------------------------------------------------------
# Organisation update (also used to add/update members)
# ---------------------------------------------------------------------------

class OrganisationUpdateSerializer(serializers.ModelSerializer):
    invite_users = InviteUserSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Organisation
        fields = ["name", "industry", "country", "city", "invite_users"]
        extra_kwargs = {f: {"required": False} for f in ["name", "industry", "country", "city"]}

    def update(self, instance, validated_data):
        invite_users = validated_data.pop("invite_users", [])
        added_by = self.context.get("request").user if self.context.get("request") else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        for invite in invite_users:
            user = User.objects.get(email=invite["email"])
            membership, created = OrganisationMembership.objects.get_or_create(
                organisation=instance,
                user=user,
                defaults={"role": invite["role"]},
            )
            if not created and membership.role != invite["role"]:
                membership.role = invite["role"]
                membership.save(update_fields=["role"])
            _sync_user_role(user, invite["role"])
            # Only send invitation email for newly added members
            if created and added_by:
                send_organisation_invitation(user, instance, invite["role"], added_by)

        return instance


# ---------------------------------------------------------------------------
# Organisation list item (compact)
# ---------------------------------------------------------------------------

class OrganisationListSerializer(serializers.ModelSerializer):
    country = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    admins = serializers.SerializerMethodField()
    total_emissions = serializers.SerializerMethodField()
    buildings_count = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = [
            "id", "name", "industry",
            "country", "city",
            "created_at",
            "status", "admins",
            "buildings_count", "total_emissions",
        ]

    def get_country(self, obj):
        if obj.country:
            return {"id": obj.country.id, "name": obj.country.name}
        return None

    def get_city(self, obj):
        if obj.city:
            return {"id": obj.city.id, "name": obj.city.name}
        return None

    def get_status(self, obj):
        return "active" if obj.buildings.exists() else "inactive"

    def get_admins(self, obj):
        admin_memberships = obj.memberships.filter(
            role=OrganisationMembership.MemberRole.ADMIN
        ).select_related("user")
        return [
            {
                "id": str(m.user.id),
                "name": m.user.get_full_name() or m.user.username,
            }
            for m in admin_memberships
        ]

    def get_buildings_count(self, obj):
        return obj.buildings.count()

    def get_total_emissions(self, obj):
        """Sum total carbon footprint * floor area across all buildings (in tCO2e)."""
        from pages.views.building.building_stats import calculate_total_carbon_footprint
        total = Decimal("0.0")
        for building in obj.buildings.all():
            try:
                carbon_per_m2 = calculate_total_carbon_footprint(building)
                if carbon_per_m2 and building.total_floor_area:
                    total += carbon_per_m2 * building.total_floor_area
            except Exception:
                pass
        return round(total / 1000, 2)  # kgCO2e → tCO2e


# ---------------------------------------------------------------------------
# Organisation detail (full, includes members)
# ---------------------------------------------------------------------------

class OrganisationDetailSerializer(OrganisationListSerializer):
    members = serializers.SerializerMethodField()

    class Meta(OrganisationListSerializer.Meta):
        fields = OrganisationListSerializer.Meta.fields + ["members", "updated_at"]

    def get_members(self, obj):
        memberships = obj.memberships.select_related(
            "user", "user__userprofile"
        ).prefetch_related("countries")
        return MembershipSerializer(memberships, many=True).data


# ---------------------------------------------------------------------------
# Building list serializer (admin tool)
# ---------------------------------------------------------------------------

class AdminBuildingSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="pk")
    uuid = serializers.UUIDField()
    name = serializers.CharField()
    country = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    region = serializers.SerializerMethodField()
    climate_zone = serializers.SerializerMethodField()

    def get_climate_zone(self, obj):
        if obj.climate_zone:
            return {"id": obj.climate_zone.id, "name": obj.climate_zone.name}
        return None
    total_floor_area = serializers.DecimalField(max_digits=10, decimal_places=2)
    category = serializers.SerializerMethodField()
    construction_year = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    created_by = serializers.SerializerMethodField()
    organisation = serializers.SerializerMethodField()
    total_carbon_footprint = serializers.SerializerMethodField()
    total_embodied_carbon = serializers.SerializerMethodField()
    total_operational_carbon = serializers.SerializerMethodField()
    draft = serializers.BooleanField()
    public = serializers.BooleanField()

    def get_country(self, obj):
        if obj.country:
            return {"id": obj.country.id, "name": obj.country.name}
        return None

    def get_city(self, obj):
        if obj.city:
            return {"id": obj.city.id, "name": obj.city.name}
        return None

    def get_region(self, obj):
        if obj.region:
            return {"id": obj.region.id, "name": obj.region.name}
        return None

    def get_category(self, obj):
        if obj.category:
            return {
                "category": obj.category.category.name if obj.category.category else None,
                "subcategory": obj.category.subcategory.name if obj.category.subcategory else None,
            }
        return None

    def get_created_by(self, obj):
        if obj.created_by:
            return {
                "id": str(obj.created_by.id),
                "name": obj.created_by.get_full_name() or obj.created_by.username,
            }
        return None

    def get_organisation(self, obj):
        if obj.organisation:
            return {"id": str(obj.organisation.id), "name": obj.organisation.name}
        return None

    def get_total_carbon_footprint(self, obj):
        return self.context.get("stats", {}).get(str(obj.pk), {}).get("total_carbon_footprint")

    def get_total_embodied_carbon(self, obj):
        return self.context.get("stats", {}).get(str(obj.pk), {}).get("total_embodied_carbon")

    def get_total_operational_carbon(self, obj):
        return self.context.get("stats", {}).get(str(obj.pk), {}).get("total_operational_carbon")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sync_user_role(user, membership_role):
    """Sync Django is_staff and UserProfile role when a user is made admin."""
    if membership_role == OrganisationMembership.MemberRole.ADMIN:
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        try:
            profile = user.userprofile
            if profile.role not in (UserProfile.Role.ADMIN, UserProfile.Role.SUPERADMIN):
                profile.role = UserProfile.Role.ADMIN
                profile.save(update_fields=["role"])
        except Exception:
            pass