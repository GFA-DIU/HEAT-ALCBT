import json
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

from pages.models import Building, LiftEscalatorSystem
from pages.models.climate_type import ClimateType

User = get_user_model()


def _make_verified_user(username, email, password="testpass123"):
    u = User.objects.create_user(username=username, email=email, password=password)
    EmailAddress.objects.create(user=u, email=email, verified=True, primary=True)
    return u


@pytest.fixture
def user(db):
    """Create a test user."""
    return _make_verified_user("testuser", "test@example.com")


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
def lift_escalator_system_data():
    """Return valid lift & escalator system data for API requests."""
    return {
        "number_of_lifts": 5,
        "lift_regenerative_features": "yes",
        "vvvf_sleep_mode": "yes",
        "annual_energy_consumption": 12000
    }


@pytest.fixture
def lift_escalator_system_model_data():
    """Return valid lift & escalator system data for direct model creation."""
    return {
        "number_of_lifts": 5,
        "lift_regenerative_features": True,
        "vvvf_sleep_mode": True,
        "annual_energy_consumption_kwh": 12000
    }


@pytest.mark.django_db
class TestLiftEscalatorSystemModel:
    """Test LiftEscalatorSystem model."""

    def test_create_lift_escalator_system(self, building, lift_escalator_system_model_data):
        """Test creating a lift & escalator system."""
        les = LiftEscalatorSystem.objects.create(
            building=building,
            **lift_escalator_system_model_data
        )

        assert les.id is not None
        assert les.building == building
        assert les.number_of_lifts == 5
        assert les.lift_regenerative_features is True
        assert les.vvvf_sleep_mode is True
        assert les.annual_energy_consumption_kwh == 12000

    def test_multiple_lift_escalator_systems_per_building(self, building):
        """Test that a building can have multiple lift & escalator systems."""
        les1 = LiftEscalatorSystem.objects.create(
            building=building,
            number_of_lifts=3,
            lift_regenerative_features=True,
            vvvf_sleep_mode=True,
            annual_energy_consumption_kwh=8000
        )

        les2 = LiftEscalatorSystem.objects.create(
            building=building,
            number_of_lifts=2,
            lift_regenerative_features=False,
            vvvf_sleep_mode=False,
            annual_energy_consumption_kwh=5000
        )

        assert building.lift_escalator_systems.count() == 2
        assert les1 in building.lift_escalator_systems.all()
        assert les2 in building.lift_escalator_systems.all()

    def test_cascade_delete(self, building, lift_escalator_system_model_data):
        """Test that lift & escalator systems are deleted when building is deleted."""
        building_id = building.id

        LiftEscalatorSystem.objects.create(building=building, **lift_escalator_system_model_data)
        LiftEscalatorSystem.objects.create(
            building=building,
            number_of_lifts=2,
            lift_regenerative_features=False,
            vvvf_sleep_mode=False,
            annual_energy_consumption_kwh=6000
        )

        assert LiftEscalatorSystem.objects.filter(building_id=building_id).count() == 2

        building.delete()

        assert LiftEscalatorSystem.objects.filter(building_id=building_id).count() == 0

    def test_nullable_annual_energy_consumption(self, building):
        """Test that annual_energy_consumption_kwh can be null."""
        les = LiftEscalatorSystem.objects.create(
            building=building,
            number_of_lifts=3,
            lift_regenerative_features=True,
            vvvf_sleep_mode=False,
            annual_energy_consumption_kwh=None
        )

        assert les.annual_energy_consumption_kwh is None


@pytest.mark.django_db
class TestLiftEscalatorSystemViews:
    """Test Lift & Escalator System API views."""

    def test_create_lift_escalator_system_success(self, client, user, building, lift_escalator_system_data):
        """Test successful creation of lift & escalator system via API."""
        client.force_login(user)

        payload = {
            "building_uuid": str(building.uuid),
            **lift_escalator_system_data
        }

        response = client.post(
            reverse("lift_escalator_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "lift_escalator_system" in data
        assert data["lift_escalator_system"]["number_of_lifts"] == 5
        assert data["lift_escalator_system"]["lift_regenerative_features"] is True

        # Verify in database
        assert LiftEscalatorSystem.objects.filter(building=building).count() == 1

    def test_create_lift_escalator_system_missing_building_id(self, client, user, lift_escalator_system_data):
        """Test creation fails when building_id is missing."""
        client.force_login(user)

        response = client.post(
            reverse("lift_escalator_system_create_update"),
            data=json.dumps(lift_escalator_system_data),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "building_uuid" in data["errors"]

    def test_create_lift_escalator_system_invalid_building_id(self, client, user, lift_escalator_system_data):
        """Test creation fails when building doesn't exist."""
        client.force_login(user)

        payload = {
            "building_uuid": "00000000-0000-0000-0000-000000000000",
            **lift_escalator_system_data
        }

        response = client.post(
            reverse("lift_escalator_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_create_lift_escalator_system_missing_required_fields(self, client, user, building):
        """Test creation fails when required fields are missing."""
        client.force_login(user)

        payload = {
            "building_uuid": str(building.uuid),
            # Missing number_of_lifts which is the only required field
        }

        response = client.post(
            reverse("lift_escalator_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "errors" in data

    def test_update_lift_escalator_system_success(self, client, user, building, lift_escalator_system_data, lift_escalator_system_model_data):
        """Test successful update of lift & escalator system."""
        client.force_login(user)

        # Create a lift & escalator system first
        les = LiftEscalatorSystem.objects.create(building=building, **lift_escalator_system_model_data)

        # Update data
        updated_data = lift_escalator_system_data.copy()
        updated_data["number_of_lifts"] = 10
        updated_data["lift_regenerative_features"] = "no"

        payload = {
            "building_uuid": str(building.uuid),
            "lift_escalator_system_id": les.id,
            **updated_data
        }

        response = client.put(
            reverse("lift_escalator_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["lift_escalator_system"]["number_of_lifts"] == 10
        assert data["lift_escalator_system"]["lift_regenerative_features"] is False

        # Verify in database
        les.refresh_from_db()
        assert les.number_of_lifts == 10
        assert les.lift_regenerative_features is False

    def test_get_lift_escalator_systems_success(self, client, user, building, lift_escalator_system_model_data):
        """Test retrieving lift & escalator systems for a building."""
        client.force_login(user)

        # Create multiple lift & escalator systems
        LiftEscalatorSystem.objects.create(building=building, **lift_escalator_system_model_data)
        LiftEscalatorSystem.objects.create(
            building=building,
            number_of_lifts=3,
            lift_regenerative_features=False,
            vvvf_sleep_mode=False,
            annual_energy_consumption_kwh=7000
        )

        response = client.get(
            reverse("lift_escalator_system_list", kwargs={"building_uuid": building.uuid})
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "lift_escalator_systems" in data
        assert len(data["lift_escalator_systems"]) == 2

    def test_get_lift_escalator_systems_empty(self, client, user, building):
        """Test retrieving lift & escalator systems when none exist."""
        client.force_login(user)

        response = client.get(
            reverse("lift_escalator_system_list", kwargs={"building_uuid": building.uuid})
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["lift_escalator_systems"]) == 0

    def test_delete_lift_escalator_system_success(self, client, user, building, lift_escalator_system_model_data):
        """Test successful deletion of lift & escalator system."""
        client.force_login(user)

        les = LiftEscalatorSystem.objects.create(building=building, **lift_escalator_system_model_data)

        response = client.delete(
            reverse("lift_escalator_system_delete", kwargs={"system_id": les.id})
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify deletion
        assert not LiftEscalatorSystem.objects.filter(id=les.id).exists()

    def test_delete_lift_escalator_system_not_found(self, client, user):
        """Test deletion fails when system doesn't exist."""
        client.force_login(user)

        response = client.delete(
            reverse("lift_escalator_system_delete", kwargs={"system_id": 99999})
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_unauthorized_access(self, client, building, lift_escalator_system_data):
        """Test that unauthenticated users cannot access endpoints."""
        # Try to create without login
        payload = {
            "building_uuid": str(building.uuid),
            **lift_escalator_system_data
        }

        response = client.post(
            reverse("lift_escalator_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 302  # Redirect to login

    def test_user_cannot_modify_other_users_building(self, client, building, lift_escalator_system_data):
        """Test that users cannot modify lift & escalator systems for buildings they don't own."""
        # Create another user
        other_user = _make_verified_user("otheruser", "other@example.com", "otherpass123")

        client.force_login(other_user)

        payload = {
            "building_uuid": str(building.uuid),
            **lift_escalator_system_data
        }

        response = client.post(
            reverse("lift_escalator_system_create_update"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 404  # Building not found for this user


@pytest.mark.django_db
class TestLiftEscalatorSystemForm:
    """Test LiftEscalatorSystemForm validation."""

    def test_form_valid_with_all_fields(self, lift_escalator_system_data):
        """Test form is valid with all fields."""
        from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm

        form = LiftEscalatorSystemForm(data=lift_escalator_system_data)
        assert form.is_valid()

    def test_form_invalid_missing_required_field(self):
        """Test form is invalid when required field is missing."""
        from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm

        data = {
            # Missing number_of_lifts which is required
            "lift_regenerative_features": "yes",
            "vvvf_sleep_mode": "yes",
        }

        form = LiftEscalatorSystemForm(data=data)
        assert not form.is_valid()
        assert "number_of_lifts" in form.errors

    def test_form_converts_yes_no_to_boolean(self, lift_escalator_system_data):
        """Test form converts 'yes'/'no' strings to boolean."""
        from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm

        lift_escalator_system_data["lift_regenerative_features"] = "yes"
        lift_escalator_system_data["vvvf_sleep_mode"] = "no"

        form = LiftEscalatorSystemForm(data=lift_escalator_system_data)
        assert form.is_valid()
        assert form.cleaned_data["lift_regenerative_features"] is True
        assert form.cleaned_data["vvvf_sleep_mode"] is False

    def test_form_handles_field_name_mapping(self):
        """Test form correctly maps annual_energy_consumption to annual_energy_consumption_kwh."""
        from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm

        data = {
            "number_of_lifts": 5,
            "lift_regenerative_features": "yes",
            "vvvf_sleep_mode": "yes",
            "annual_energy_consumption": 12000  # Frontend field name
        }

        form = LiftEscalatorSystemForm(data=data)
        assert form.is_valid()
        assert form.cleaned_data["annual_energy_consumption_kwh"] == 12000

    def test_form_allows_null_annual_energy_consumption(self):
        """Test form allows null annual energy consumption."""
        from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm

        data = {
            "number_of_lifts": 5,
            "lift_regenerative_features": "yes",
            "vvvf_sleep_mode": "no",
            "annual_energy_consumption": None
        }

        form = LiftEscalatorSystemForm(data=data)
        assert form.is_valid()
        assert form.cleaned_data["annual_energy_consumption_kwh"] is None

    def test_form_rejects_negative_annual_energy_consumption(self):
        """Test form rejects negative annual energy consumption."""
        from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm

        data = {
            "number_of_lifts": 5,
            "lift_regenerative_features": "yes",
            "vvvf_sleep_mode": "yes",
            "annual_energy_consumption": -1000
        }

        form = LiftEscalatorSystemForm(data=data)
        assert not form.is_valid()
        assert "annual_energy_consumption_kwh" in form.errors