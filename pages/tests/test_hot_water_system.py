import json
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

from pages.models import Building, HotWaterSystem
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
def hot_water_system_data():
    """Return valid hot water system data for API requests."""
    return {
        "type_of_hot_water_system": "heat-pump",
        "fuel_type": "electricity",
        "operating_hours_per_day": 8.5,
        "operating_days_per_week": 5,
        "operating_weeks_per_year": 52,
        "fuel_consumption": 343.50,
        "power_input": 400.00,
        "baseline_efficiency": 0.85,
        "equipment_efficiency_level": 40.00,
        "heat_recovery_system": "yes",
        "number_of_equipment": 5,
        "energy_efficiency_label": "bee",
        "number_of_stars": 5
    }


@pytest.fixture
def hot_water_system_model_data():
    """Return valid hot water system data for direct model creation."""
    return {
        "type_of_hot_water_system": "heat-pump",
        "fuel_type": "electricity",
        "operating_hours_per_day": 8.5,
        "operating_days_per_week": 5,
        "operating_weeks_per_year": 52,
        "fuel_consumption": 343.50,
        "power_input": 400.00,
        "baseline_efficiency": 0.85,
        "equipment_efficiency_level": 40.00,
        "heat_recovery_system": True,
        "number_of_equipment": 5,
        "energy_efficiency_label": "bee",
        "number_of_stars": 5
    }


@pytest.mark.django_db
class TestHotWaterSystemModel:
    """Test HotWaterSystem model."""

    def test_create_hot_water_system(self, building, hot_water_system_model_data):
        """Test creating a hot water system."""
        hws = HotWaterSystem.objects.create(
            building=building,
            **hot_water_system_model_data
        )

        assert hws.id is not None
        assert hws.building == building
        assert hws.type_of_hot_water_system == "heat-pump"
        assert hws.fuel_type == "electricity"
        assert float(hws.operating_hours_per_day) == 8.5
        assert hws.operating_days_per_week == 5
        assert hws.operating_weeks_per_year == 52
        assert float(hws.fuel_consumption) == 343.50
        assert float(hws.power_input) == 400.00
        assert float(hws.baseline_efficiency) == 0.85
        assert float(hws.equipment_efficiency_level) == 40.00
        assert hws.heat_recovery_system is True
        assert hws.number_of_equipment == 5
        assert hws.energy_efficiency_label == "bee"
        assert hws.number_of_stars == 5

    def test_hot_water_system_str(self, building, hot_water_system_model_data):
        """Test __str__ method."""
        hws = HotWaterSystem.objects.create(
            building=building,
            **hot_water_system_model_data
        )

        assert str(hws) == f"Heat Pump Water Heater - {building.name}"

    def test_multiple_hot_water_systems_per_building(self, building):
        """Test that a building can have multiple hot water systems."""
        hws1 = HotWaterSystem.objects.create(
            building=building,
            type_of_hot_water_system="heat-pump",
            fuel_type="electricity",
            operating_hours_per_day=8,
            operating_days_per_week=5,
            operating_weeks_per_year=52,
            fuel_consumption=100,
            power_input=200,
            baseline_efficiency=0.85,
            equipment_efficiency_level=40,
            heat_recovery_system=True,
            number_of_equipment=2
        )

        hws2 = HotWaterSystem.objects.create(
            building=building,
            type_of_hot_water_system="boiler",
            fuel_type="natural-gas",
            operating_hours_per_day=10,
            operating_days_per_week=7,
            operating_weeks_per_year=52,
            fuel_consumption=200,
            power_input=300,
            baseline_efficiency=0.75,
            equipment_efficiency_level=35,
            heat_recovery_system=False,
            number_of_equipment=1
        )

        assert building.hot_water_systems.count() == 2
        assert hws1 in building.hot_water_systems.all()
        assert hws2 in building.hot_water_systems.all()

    def test_cascade_delete(self, building, hot_water_system_model_data):
        """Test that hot water systems are deleted when building is deleted."""
        building_id = building.id

        HotWaterSystem.objects.create(building=building, **hot_water_system_model_data)
        HotWaterSystem.objects.create(
            building=building,
            type_of_hot_water_system="boiler",
            fuel_type="diesel",
            operating_hours_per_day=5,
            operating_days_per_week=3,
            operating_weeks_per_year=48,
            fuel_consumption=150,
            power_input=250,
            baseline_efficiency=0.70,
            equipment_efficiency_level=30,
            heat_recovery_system=False,
            number_of_equipment=1
        )

        assert HotWaterSystem.objects.filter(building_id=building_id).count() == 2

        building.delete()

        assert HotWaterSystem.objects.filter(building_id=building_id).count() == 0


@pytest.mark.django_db
class TestHotWaterSystemViews:
    """Test Hot Water System API views."""

    def test_create_hot_water_system_success(self, client, user, building, hot_water_system_data):
        """Test successful creation of hot water system via API."""
        client.force_login(user)

        payload = {
            "building_id": str(building.id),
            **hot_water_system_data
        }

        response = client.post(
            reverse("hot_water_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "hot_water_system" in data
        assert data["hot_water_system"]["type_of_hot_water_system"] == "heat-pump"
        assert data["hot_water_system"]["fuel_type"] == "electricity"

        # Verify in database
        assert HotWaterSystem.objects.filter(building=building).count() == 1

    def test_create_hot_water_system_missing_building_id(self, client, user, hot_water_system_data):
        """Test creation fails when building_id is missing."""
        client.force_login(user)

        response = client.post(
            reverse("hot_water_system_create_update"),
            data=json.dumps(hot_water_system_data),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "building_id" in data["errors"]

    def test_create_hot_water_system_invalid_building_id(self, client, user, hot_water_system_data):
        """Test creation fails when building doesn't exist."""
        client.force_login(user)

        payload = {
            "building_id": "00000000-0000-0000-0000-000000000000",
            **hot_water_system_data
        }

        response = client.post(
            reverse("hot_water_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_create_hot_water_system_missing_required_fields(self, client, user, building):
        """Test creation fails when required fields are missing."""
        client.force_login(user)

        payload = {
            "building_id": str(building.id),
            "type_of_hot_water_system": "heat-pump"
            # Missing other required fields
        }

        response = client.post(
            reverse("hot_water_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "errors" in data

    def test_create_hot_water_system_invalid_field_values(self, client, user, building, hot_water_system_data):
        """Test creation fails with invalid field values."""
        client.force_login(user)

        hot_water_system_data["operating_hours_per_day"] = 25  # Invalid: > 24
        payload = {
            "building_id": str(building.id),
            **hot_water_system_data
        }

        response = client.post(
            reverse("hot_water_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False

    def test_update_hot_water_system_success(self, client, user, building, hot_water_system_data, hot_water_system_model_data):
        """Test successful update of hot water system."""
        client.force_login(user)

        # Create a hot water system first
        hws = HotWaterSystem.objects.create(building=building, **hot_water_system_model_data)

        # Update data
        updated_data = hot_water_system_data.copy()
        updated_data["power_input"] = 500.00
        updated_data["number_of_equipment"] = 10

        payload = {
            "building_id": str(building.id),
            "hot_water_system_id": hws.id,
            **updated_data
        }

        response = client.put(
            reverse("hot_water_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert float(data["hot_water_system"]["power_input"]) == 500.00
        assert data["hot_water_system"]["number_of_equipment"] == 10

        # Verify in database
        hws.refresh_from_db()
        assert float(hws.power_input) == 500.00
        assert hws.number_of_equipment == 10

    def test_get_hot_water_systems_success(self, client, user, building, hot_water_system_data, hot_water_system_model_data):
        """Test retrieving hot water systems for a building."""
        client.force_login(user)

        # Create multiple hot water systems
        HotWaterSystem.objects.create(building=building, **hot_water_system_model_data)
        HotWaterSystem.objects.create(
            building=building,
            type_of_hot_water_system="boiler",
            fuel_type="diesel",
            operating_hours_per_day=6,
            operating_days_per_week=4,
            operating_weeks_per_year=50,
            fuel_consumption=200,
            power_input=300,
            baseline_efficiency=0.70,
            equipment_efficiency_level=30,
            heat_recovery_system=False,
            number_of_equipment=2
        )

        response = client.get(
            reverse("hot_water_system_list", kwargs={"building_id": building.id})
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "hot_water_systems" in data
        assert len(data["hot_water_systems"]) == 2

    def test_get_hot_water_systems_empty(self, client, user, building):
        """Test retrieving hot water systems when none exist."""
        client.force_login(user)

        response = client.get(
            reverse("hot_water_system_list", kwargs={"building_id": building.id})
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["hot_water_systems"]) == 0

    def test_delete_hot_water_system_success(self, client, user, building, hot_water_system_model_data):
        """Test successful deletion of hot water system."""
        client.force_login(user)

        hws = HotWaterSystem.objects.create(building=building, **hot_water_system_model_data)

        response = client.delete(
            reverse("hot_water_system_delete", kwargs={"system_id": hws.id})
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify deletion
        assert not HotWaterSystem.objects.filter(id=hws.id).exists()

    def test_delete_hot_water_system_not_found(self, client, user):
        """Test deletion fails when system doesn't exist."""
        client.force_login(user)

        response = client.delete(
            reverse("hot_water_system_delete", kwargs={"system_id": 99999})
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_unauthorized_access(self, client, building, hot_water_system_data):
        """Test that unauthenticated users cannot access endpoints."""
        # Try to create without login
        payload = {
            "building_id": str(building.id),
            **hot_water_system_data
        }

        response = client.post(
            reverse("hot_water_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 302  # Redirect to login

    def test_user_cannot_modify_other_users_building(self, client, building, hot_water_system_data):
        """Test that users cannot modify hot water systems for buildings they don't own."""
        # Create another user
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="otherpass123"
        )

        client.force_login(other_user)

        payload = {
            "building_id": str(building.id),
            **hot_water_system_data
        }

        response = client.post(
            reverse("hot_water_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 404  # Building not found for this user


@pytest.mark.django_db
class TestHotWaterSystemForm:
    """Test HotWaterSystemForm validation."""

    def test_form_valid_with_all_required_fields(self, building, hot_water_system_data):
        """Test form is valid with all required fields."""
        from pages.forms.hot_water_system_form import HotWaterSystemForm

        form = HotWaterSystemForm(data=hot_water_system_data)
        assert form.is_valid()

    def test_form_invalid_missing_required_field(self, building):
        """Test form is invalid when required field is missing."""
        from pages.forms.hot_water_system_form import HotWaterSystemForm

        data = {
            "type_of_hot_water_system": "heat-pump",
            # Missing other required fields
        }

        form = HotWaterSystemForm(data=data)
        assert not form.is_valid()

    def test_form_converts_yes_no_to_boolean(self, building, hot_water_system_data):
        """Test form converts 'yes'/'no' strings to boolean."""
        from pages.forms.hot_water_system_form import HotWaterSystemForm

        hot_water_system_data["heat_recovery_system"] = "yes"
        form = HotWaterSystemForm(data=hot_water_system_data)
        assert form.is_valid()
        assert form.cleaned_data["heat_recovery_system"] is True

        hot_water_system_data["heat_recovery_system"] = "no"
        form = HotWaterSystemForm(data=hot_water_system_data)
        assert form.is_valid()
        assert form.cleaned_data["heat_recovery_system"] is False

    def test_form_validation_energy_label_requires_stars(self, hot_water_system_data):
        """Test that providing energy label without stars produces validation error."""
        from pages.forms.hot_water_system_form import HotWaterSystemForm

        hot_water_system_data["energy_efficiency_label"] = "bee"
        hot_water_system_data["number_of_stars"] = None

        form = HotWaterSystemForm(data=hot_water_system_data)
        assert not form.is_valid()
        assert "number_of_stars" in form.errors


@pytest.mark.django_db
class TestBuildingSetupIntegration:
    """Test integration of HWS with building setup flow."""

    def test_complete_building_setup_creates_hot_water_systems(self, client, user, building, hot_water_system_data):
        """Test that completing building setup creates HWS records from session data."""
        client.force_login(user)

        # Simulate the frontend saving HWS data to session
        session = client.session
        session["building_id"] = str(building.id)
        session["building_form_data"] = {
            "operational-details/hot-water-system": [
                hot_water_system_data,
                {
                    "type_of_hot_water_system": "boiler",
                    "fuel_type": "diesel",
                    "operating_hours_per_day": 10.0,
                    "operating_days_per_week": 7,
                    "operating_weeks_per_year": 52,
                    "fuel_consumption": 500.0,
                    "power_input": 600.0,
                    "baseline_efficiency": 0.75,
                    "equipment_efficiency_level": 35.0,
                    "heat_recovery_system": "no",
                    "number_of_equipment": 2,
                }
            ]
        }
        session.save()

        # Complete the building setup
        response = client.post(reverse("complete_building_setup"))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify HWS records were created
        assert HotWaterSystem.objects.filter(building=building).count() == 2

        # Verify session was cleared
        assert "building_form_data" not in client.session

    def test_complete_building_setup_validates_hws_data(self, client, user, building):
        """Test that invalid HWS data returns validation errors."""
        client.force_login(user)

        # Set up session with invalid HWS data
        session = client.session
        session["building_id"] = str(building.id)
        session["building_form_data"] = {
            "operational-details/hot-water-system": [
                {
                    "type_of_hot_water_system": "heat-pump",
                    "fuel_type": "electricity",
                    "operating_hours_per_day": 30,  # Invalid: > 24
                    "operating_days_per_week": 5,
                    "operating_weeks_per_year": 52,
                    "fuel_consumption": 100.0,
                    "power_input": 200.0,
                    "baseline_efficiency": 0.85,
                    "equipment_efficiency_level": 40.0,
                    "heat_recovery_system": "yes",
                    "number_of_equipment": 1,
                }
            ]
        }
        session.save()

        # Attempt to complete building setup
        response = client.post(reverse("complete_building_setup"))

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "errors" in data

        # Verify no HWS records were created
        assert HotWaterSystem.objects.filter(building=building).count() == 0

    def test_complete_building_setup_without_building_id(self, client, user):
        """Test that setup fails if no building_id in session."""
        client.force_login(user)

        # Set up session without building_id
        session = client.session
        session["building_form_data"] = {
            "operational-details/hot-water-system": []
        }
        session.save()

        response = client.post(reverse("complete_building_setup"))

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "must be created before" in data["error"].lower()