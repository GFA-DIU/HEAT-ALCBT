import json
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

from pages.models import Building, LightingSystem
from pages.models.climate_type import ClimateType

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def building(db, user):
    """Create a test building."""
    climate, _ = ClimateType.objects.get_or_create(name="tropical-wet")
    return Building.objects.create(
        name="Test Building",
        climate_zone=climate,
        total_floor_area=1000.00,
        reference_period=50,
        created_by=user
    )


@pytest.fixture
def lighting_system_data():
    """Return valid lighting system data for API requests."""
    return {
        "room_type": "OFFICE_CONFERENCE",
        "area_of_room": 50,
        "lighting_type": "LED",
        "number_of_bulbs": 10,
        "operating_hours_per_day": 8,
        "operating_days_per_week": 5,
        "operating_weeks_per_year": 52,
        "bulb_power_rating": 15,
        "baseline_lpd": 10,
        "installation_of_sensors": "yes",
        "annual_energy_consumption": 3120,
        "number_of_stars": 4
    }


@pytest.fixture
def lighting_system_model_data():
    """Return valid lighting system data for direct model creation."""
    return {
        "room_type": "OFFICE_CONFERENCE",
        "area_of_room": 50,
        "lighting_bulb_type": "LED",
        "number_of_bulbs": 10,
        "operation_hours_per_workday": 8,
        "workdays_per_week": 5,
        "workweeks_per_year": 52,
        "light_bulb_power_rating_w": 15,
        "baseline_lighting_power_density": 10,
        "sensors_installed": True,
        "total_energy_consumption_kwh_per_year": 3120,
        "energy_efficiency_label": 4
    }


@pytest.mark.django_db
class TestLightingSystemModel:
    """Test LightingSystem model."""

    def test_create_lighting_system(self, building, lighting_system_model_data):
        """Test creating a lighting system."""
        ls = LightingSystem.objects.create(
            building=building,
            **lighting_system_model_data
        )

        assert ls.id is not None
        assert ls.building == building
        assert ls.room_type == "OFFICE_CONFERENCE"
        assert ls.area_of_room == 50
        assert ls.lighting_bulb_type == "LED"
        assert ls.number_of_bulbs == 10
        assert ls.sensors_installed is True

    def test_multiple_lighting_systems_per_building(self, building):
        """Test that a building can have multiple lighting systems."""
        ls1 = LightingSystem.objects.create(
            building=building,
            room_type="OFFICE_CONFERENCE",
            area_of_room=50,
            lighting_bulb_type="LED",
            number_of_bulbs=10,
            operation_hours_per_workday=8,
            workdays_per_week=5,
            workweeks_per_year=52,
            light_bulb_power_rating_w=15,
            sensors_installed=True
        )

        ls2 = LightingSystem.objects.create(
            building=building,
            room_type="HOSPITAL_PATIENT",
            area_of_room=30,
            lighting_bulb_type="CFL",
            number_of_bulbs=5,
            operation_hours_per_workday=24,
            workdays_per_week=7,
            workweeks_per_year=52,
            light_bulb_power_rating_w=20,
            sensors_installed=False
        )

        assert building.lighting_systems.count() == 2
        assert ls1 in building.lighting_systems.all()
        assert ls2 in building.lighting_systems.all()

    def test_cascade_delete(self, building, lighting_system_model_data):
        """Test that lighting systems are deleted when building is deleted."""
        building_id = building.id

        LightingSystem.objects.create(building=building, **lighting_system_model_data)
        LightingSystem.objects.create(
            building=building,
            room_type="HOSPITAL_PATIENT",
            area_of_room=30,
            lighting_bulb_type="CFL",
            number_of_bulbs=5,
            operation_hours_per_workday=24,
            workdays_per_week=7,
            workweeks_per_year=52,
            light_bulb_power_rating_w=20,
            sensors_installed=False
        )

        assert LightingSystem.objects.filter(building_id=building_id).count() == 2

        building.delete()

        assert LightingSystem.objects.filter(building_id=building_id).count() == 0

    def test_nullable_fields(self, building):
        """Test that nullable fields can be null."""
        ls = LightingSystem.objects.create(
            building=building,
            room_type="OFFICE_CONFERENCE",
            area_of_room=50,
            lighting_bulb_type="LED",
            number_of_bulbs=10,
            operation_hours_per_workday=8,
            workdays_per_week=5,
            workweeks_per_year=52,
            light_bulb_power_rating_w=15,
            sensors_installed=False,
            baseline_lighting_power_density=None,
            total_energy_consumption_kwh_per_year=None,
            energy_efficiency_label=None
        )

        assert ls.baseline_lighting_power_density is None
        assert ls.total_energy_consumption_kwh_per_year is None
        assert ls.energy_efficiency_label is None


@pytest.mark.django_db
class TestLightingSystemViews:
    """Test Lighting System API views."""

    def test_create_lighting_system_success(self, client, user, building, lighting_system_data):
        """Test successful creation of lighting system via API."""
        client.force_login(user)

        payload = {
            "building_id": str(building.id),
            **lighting_system_data
        }

        response = client.post(
            reverse("lighting_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "lighting_system" in data
        assert data["lighting_system"]["room_type"] == "OFFICE_CONFERENCE"
        assert data["lighting_system"]["sensors_installed"] is True

        # Verify in database
        assert LightingSystem.objects.filter(building=building).count() == 1

    def test_create_lighting_system_missing_building_id(self, client, user, lighting_system_data):
        """Test creation fails when building_id is missing."""
        client.force_login(user)

        response = client.post(
            reverse("lighting_system_create_update"),
            data=json.dumps(lighting_system_data),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "building_id" in data["errors"]

    def test_create_lighting_system_invalid_building_id(self, client, user, lighting_system_data):
        """Test creation fails when building doesn't exist."""
        client.force_login(user)

        payload = {
            "building_id": "00000000-0000-0000-0000-000000000000",
            **lighting_system_data
        }

        response = client.post(
            reverse("lighting_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_create_lighting_system_missing_required_fields(self, client, user, building):
        """Test creation fails when required fields are missing."""
        client.force_login(user)

        payload = {
            "building_id": str(building.id),
            # Missing all required fields
        }

        response = client.post(
            reverse("lighting_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "errors" in data

    def test_update_lighting_system_success(self, client, user, building, lighting_system_data, lighting_system_model_data):
        """Test successful update of lighting system."""
        client.force_login(user)

        # Create a lighting system first
        ls = LightingSystem.objects.create(building=building, **lighting_system_model_data)

        # Update data
        updated_data = lighting_system_data.copy()
        updated_data["number_of_bulbs"] = 20
        updated_data["installation_of_sensors"] = "no"

        payload = {
            "building_id": str(building.id),
            "lighting_system_id": ls.id,
            **updated_data
        }

        response = client.put(
            reverse("lighting_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["lighting_system"]["number_of_bulbs"] == 20
        assert data["lighting_system"]["sensors_installed"] is False

        # Verify in database
        ls.refresh_from_db()
        assert ls.number_of_bulbs == 20
        assert ls.sensors_installed is False

    def test_get_lighting_systems_success(self, client, user, building, lighting_system_model_data):
        """Test retrieving lighting systems for a building."""
        client.force_login(user)

        # Create multiple lighting systems
        LightingSystem.objects.create(building=building, **lighting_system_model_data)
        LightingSystem.objects.create(
            building=building,
            room_type="HOSPITAL_PATIENT",
            area_of_room=30,
            lighting_bulb_type="CFL",
            number_of_bulbs=5,
            operation_hours_per_workday=24,
            workdays_per_week=7,
            workweeks_per_year=52,
            light_bulb_power_rating_w=20,
            sensors_installed=False
        )

        response = client.get(
            reverse("lighting_system_list", kwargs={"building_id": building.id})
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "lighting_systems" in data
        assert len(data["lighting_systems"]) == 2

    def test_get_lighting_systems_empty(self, client, user, building):
        """Test retrieving lighting systems when none exist."""
        client.force_login(user)

        response = client.get(
            reverse("lighting_system_list", kwargs={"building_id": building.id})
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["lighting_systems"]) == 0

    def test_delete_lighting_system_success(self, client, user, building, lighting_system_model_data):
        """Test successful deletion of lighting system."""
        client.force_login(user)

        ls = LightingSystem.objects.create(building=building, **lighting_system_model_data)

        response = client.delete(
            reverse("lighting_system_delete", kwargs={"system_id": ls.id})
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify deletion
        assert not LightingSystem.objects.filter(id=ls.id).exists()

    def test_delete_lighting_system_not_found(self, client, user):
        """Test deletion fails when system doesn't exist."""
        client.force_login(user)

        response = client.delete(
            reverse("lighting_system_delete", kwargs={"system_id": 99999})
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_unauthorized_access(self, client, building, lighting_system_data):
        """Test that unauthenticated users cannot access endpoints."""
        # Try to create without login
        payload = {
            "building_id": str(building.id),
            **lighting_system_data
        }

        response = client.post(
            reverse("lighting_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 302  # Redirect to login

    def test_user_cannot_modify_other_users_building(self, client, building, lighting_system_data):
        """Test that users cannot modify lighting systems for buildings they don't own."""
        # Create another user
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="otherpass123"
        )

        client.force_login(other_user)

        payload = {
            "building_id": str(building.id),
            **lighting_system_data
        }

        response = client.post(
            reverse("lighting_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 404  # Building not found for this user


@pytest.mark.django_db
class TestLightingSystemForm:
    """Test LightingSystemForm validation."""

    def test_form_valid_with_all_fields(self, lighting_system_data):
        """Test form is valid with all fields."""
        from pages.forms.lighting_system_form import LightingSystemForm

        form = LightingSystemForm(data=lighting_system_data)
        assert form.is_valid()

    def test_form_invalid_missing_required_field(self):
        """Test form is invalid when required field is missing."""
        from pages.forms.lighting_system_form import LightingSystemForm

        data = {
            # Missing room_type which is required
            "area_of_room": 50,
        }

        form = LightingSystemForm(data=data)
        assert not form.is_valid()
        assert "room_type" in form.errors

    def test_form_converts_yes_no_to_boolean(self, lighting_system_data):
        """Test form converts 'yes'/'no' strings to boolean."""
        from pages.forms.lighting_system_form import LightingSystemForm

        lighting_system_data["installation_of_sensors"] = "yes"

        form = LightingSystemForm(data=lighting_system_data)
        assert form.is_valid()
        assert form.cleaned_data["sensors_installed"] is True

        lighting_system_data["installation_of_sensors"] = "no"
        form = LightingSystemForm(data=lighting_system_data)
        assert form.is_valid()
        assert form.cleaned_data["sensors_installed"] is False

    def test_form_handles_field_name_mapping(self):
        """Test form correctly maps frontend field names to model field names."""
        from pages.forms.lighting_system_form import LightingSystemForm

        data = {
            "room_type": "OFFICE_CONFERENCE",
            "area_of_room": 50,
            "lighting_type": "LED",  # Frontend field name
            "number_of_bulbs": 10,
            "operating_hours_per_day": 8,  # Frontend field name
            "operating_days_per_week": 5,  # Frontend field name
            "operating_weeks_per_year": 52,  # Frontend field name
            "bulb_power_rating": 15,  # Frontend field name
            "installation_of_sensors": "yes",  # Frontend field name
        }

        form = LightingSystemForm(data=data)
        assert form.is_valid()
        assert form.cleaned_data["lighting_bulb_type"] == "LED"
        assert form.cleaned_data["operation_hours_per_workday"] == 8
        assert form.cleaned_data["workdays_per_week"] == 5
        assert form.cleaned_data["workweeks_per_year"] == 52
        assert form.cleaned_data["light_bulb_power_rating_w"] == 15
        assert form.cleaned_data["sensors_installed"] is True

    def test_form_allows_null_optional_fields(self):
        """Test form allows null optional fields."""
        from pages.forms.lighting_system_form import LightingSystemForm

        data = {
            "room_type": "OFFICE_CONFERENCE",
            "area_of_room": 50,
            "lighting_type": "LED",
            "number_of_bulbs": 10,
            "operating_hours_per_day": 8,
            "operating_days_per_week": 5,
            "operating_weeks_per_year": 52,
            "bulb_power_rating": 15,
            "installation_of_sensors": "no",
            "baseline_lpd": None,
            "annual_energy_consumption": None,
            "number_of_stars": None
        }

        form = LightingSystemForm(data=data)
        assert form.is_valid()
        assert form.cleaned_data["baseline_lighting_power_density"] is None
        assert form.cleaned_data["total_energy_consumption_kwh_per_year"] is None
        assert form.cleaned_data["energy_efficiency_label"] is None

    def test_form_rejects_negative_values(self):
        """Test form rejects negative values for positive fields."""
        from pages.forms.lighting_system_form import LightingSystemForm

        data = {
            "room_type": "OFFICE_CONFERENCE",
            "area_of_room": 50,
            "lighting_type": "LED",
            "number_of_bulbs": 10,
            "operating_hours_per_day": 8,
            "operating_days_per_week": 5,
            "operating_weeks_per_year": 52,
            "bulb_power_rating": 15,
            "installation_of_sensors": "no",
            "baseline_lpd": -10  # Negative value
        }

        form = LightingSystemForm(data=data)
        assert not form.is_valid()
        assert "baseline_lighting_power_density" in form.errors

    def test_form_validates_energy_efficiency_label_range(self):
        """Test form validates energy efficiency label is between 1 and 5."""
        from pages.forms.lighting_system_form import LightingSystemForm

        data = {
            "room_type": "OFFICE_CONFERENCE",
            "area_of_room": 50,
            "lighting_type": "LED",
            "number_of_bulbs": 10,
            "operating_hours_per_day": 8,
            "operating_days_per_week": 5,
            "operating_weeks_per_year": 52,
            "bulb_power_rating": 15,
            "installation_of_sensors": "no",
            "number_of_stars": 6  # Out of range
        }

        form = LightingSystemForm(data=data)
        assert not form.is_valid()
        assert "energy_efficiency_label" in form.errors