import csv
import io

from cities_light.models import Country
from rest_framework import serializers

from accounts.models import CustomCity
from pages.models.building import Building, BuildingCategory, BuildingSubcategory, CategorySubcategory
from pages.models.climate_type import ClimateType


# ---------------------------------------------------------------------------
# Countries & Cities
# ---------------------------------------------------------------------------

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomCity
        fields = ["id", "name"]


class CountryListSerializer(serializers.ModelSerializer):
    city_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Country
        fields = ["id", "name", "city_count", "status"]

    def get_city_count(self, obj):
        return CustomCity.objects.filter(country=obj).count()

    def get_status(self, obj):
        return "active" if Building.objects.filter(country=obj).exists() else "inactive"


class CountryDetailSerializer(serializers.ModelSerializer):
    cities = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Country
        fields = ["id", "name", "cities", "status"]

    def get_cities(self, obj):
        cities = CustomCity.objects.filter(country=obj).order_by("name")
        return CitySerializer(cities, many=True).data

    def get_status(self, obj):
        return "active" if Building.objects.filter(country=obj).exists() else "inactive"


class CountryCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    cities = serializers.ListField(
        child=serializers.CharField(max_length=200),
        allow_empty=True,
        required=False,
        default=list,
    )

    def validate_name(self, value):
        if Country.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("A country with this name already exists.")
        return value


class CountryUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    add_cities = serializers.ListField(
        child=serializers.CharField(max_length=200),
        allow_empty=True,
        required=False,
        default=list,
    )
    update_cities = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        allow_empty=True,
        required=False,
        default=list,
        help_text='List of {"id": "<id>", "name": "<new_name>"} objects.',
    )

    def validate_name(self, value):
        instance = self.instance
        if Country.objects.filter(name__iexact=value).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError("A country with this name already exists.")
        return value


# ---------------------------------------------------------------------------
# Climate Types
# ---------------------------------------------------------------------------

class ClimateTypeListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    usage_count = serializers.SerializerMethodField()

    class Meta:
        model = ClimateType
        fields = ["id", "name", "description", "status", "usage_count", "created_at"]

    def get_status(self, obj):
        return "active" if Building.objects.filter(climate_zone=obj).exists() else "inactive"

    def get_usage_count(self, obj):
        return Building.objects.filter(climate_zone=obj).count()


class ClimateTypeDetailSerializer(ClimateTypeListSerializer):
    class Meta(ClimateTypeListSerializer.Meta):
        fields = ClimateTypeListSerializer.Meta.fields + ["updated_at"]


class ClimateTypeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClimateType
        fields = ["id", "name", "description"]

    def validate_name(self, value):
        if ClimateType.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("A climate type with this name already exists.")
        return value


class ClimateTypeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClimateType
        fields = ["name", "description"]
        extra_kwargs = {"name": {"required": False}, "description": {"required": False}}

    def validate_name(self, value):
        if ClimateType.objects.filter(name__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A climate type with this name already exists.")
        return value

    def update(self, instance, validated_data):
        # name change cascades automatically via FK — no manual Building update needed
        return super().update(instance, validated_data)


# ---------------------------------------------------------------------------
# Building Types (BuildingCategory + BuildingSubcategory)
# ---------------------------------------------------------------------------

class BuildingSubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BuildingSubcategory
        fields = ["id", "name"]


class BuildingTypeListSerializer(serializers.ModelSerializer):
    has_subtypes = serializers.SerializerMethodField()
    subtype_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = BuildingCategory
        fields = ["id", "name", "has_subtypes", "subtype_count", "status"]

    def get_has_subtypes(self, obj):
        return obj.subcategories.exists()

    def get_subtype_count(self, obj):
        return obj.subcategories.count()

    def get_status(self, obj):
        return "active" if Building.objects.filter(category__category=obj).exists() else "inactive"


class BuildingTypeDetailSerializer(BuildingTypeListSerializer):
    subtypes = serializers.SerializerMethodField()

    class Meta(BuildingTypeListSerializer.Meta):
        fields = BuildingTypeListSerializer.Meta.fields + ["subtypes"]

    def get_subtypes(self, obj):
        subcategories = obj.subcategories.all().order_by("name")
        return BuildingSubcategorySerializer(subcategories, many=True).data


class BuildingTypeCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    has_subtypes = serializers.BooleanField(default=False)
    subtypes = serializers.ListField(
        child=serializers.CharField(max_length=255),
        allow_empty=True,
        required=False,
        default=list,
    )

    def validate_name(self, value):
        if BuildingCategory.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("A building type with this name already exists.")
        return value

    def validate(self, attrs):
        if attrs.get("has_subtypes") and not attrs.get("subtypes"):
            raise serializers.ValidationError(
                {"subtypes": "At least one subtype is required when has_subtypes is true."}
            )
        return attrs


class BuildingTypeUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    add_subtypes = serializers.ListField(
        child=serializers.CharField(max_length=255),
        allow_empty=True,
        required=False,
        default=list,
    )
    remove_subtype_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    update_subtypes = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        allow_empty=True,
        required=False,
        default=list,
        help_text='List of {"id": "<id>", "name": "<new_name>"} objects.',
    )

    def validate_name(self, value):
        if BuildingCategory.objects.filter(name__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A building type with this name already exists.")
        return value