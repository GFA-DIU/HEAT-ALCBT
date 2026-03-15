"""
Tests for Ventilation System models, views, and forms.
"""
import json
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

from pages.models.building import Building
from pages.models.building_operation import VentilationSystem
from pages.forms.ventilation_system_form import VentilationSystemForm

User = get_user_model()


def _make_verified_user(username, email, password="testpass123"):
    u = User.objects.create_user(username=username, email=email, password=password)
    EmailAddress.objects.create(user=u, email=email, verified=True, primary=True)
    return u


@pytest.fixture
def user(db):
    """Create a test user."""
    return _make_verified_user('testuser', 'test@example.com')


@pytest.fixture
def other_user(db):
    """Create another test user."""
    return _make_verified_user('otheruser', 'other@example.com')


@pytest.fixture
def building(db, user):
    """Create a test building."""
    return Building.objects.create(
        name='Test Building',
        total_floor_area=1000.00,
        created_by=user
    )


@pytest.fixture
def other_building(db, other_user):
    """Create a building owned by another user."""
    return Building.objects.create(
        name='Other Building',
        total_floor_area=1000.00,
        created_by=other_user
    )


@pytest.fixture
def ventilation_system(db, building):
    """Create a test ventilation system."""
    return VentilationSystem.objects.create(
        building=building,
        ventilation_type='AHU',
        ventilation_capacity='M3H',
        baseline_efficiency_w_cmh=2,
        operation_hours_per_workday=8,
        workdays_per_week=5,
        workweeks_per_year=50,
        total_power_input_kw=1,
        air_flow_rate=500,
        demand_controlled_ventilation=True,
        variable_speed_drives=True,
        number_of_units_installed=5,
        total_energy_consumption_kwh_per_year=5000,
        number_of_stars=4
    )


# ============================================================================
# MODEL TESTS
# ============================================================================

@pytest.mark.django_db
class TestVentilationSystemModel:
    """Tests for the VentilationSystem model."""

    def test_create_ventilation_system(self, building):
        """Test creating a ventilation system."""
        system = VentilationSystem.objects.create(
            building=building,
            ventilation_type='AHU',
            ventilation_capacity='M3H',
            baseline_efficiency_w_cmh=2,
            operation_hours_per_workday=8,
            workdays_per_week=5,
            workweeks_per_year=50,
            total_power_input_kw=1,
            air_flow_rate=500,
            demand_controlled_ventilation=True,
            variable_speed_drives=True,
            number_of_units_installed=5,
        )
        assert system.id is not None
        assert system.building == building
        assert system.ventilation_type == 'AHU'
        assert system.baseline_efficiency_w_cmh == 2

    def test_multiple_systems_per_building(self, building):
        """Test that multiple ventilation systems can be added to one building."""
        system1 = VentilationSystem.objects.create(
            building=building,
            ventilation_type='AHU',
            ventilation_capacity='M3H',
            baseline_efficiency_w_cmh=2,
            operation_hours_per_workday=8,
            workdays_per_week=5,
            workweeks_per_year=50,
            total_power_input_kw=1,
            air_flow_rate=500,
            demand_controlled_ventilation=True,
            variable_speed_drives=True,
            number_of_units_installed=5,
        )
        system2 = VentilationSystem.objects.create(
            building=building,
            ventilation_type='FCU',
            ventilation_capacity='F3M',
            baseline_efficiency_w_cmh=3,
            operation_hours_per_workday=10,
            workdays_per_week=6,
            workweeks_per_year=52,
            total_power_input_kw=2,
            air_flow_rate=800,
            demand_controlled_ventilation=False,
            variable_speed_drives=False,
            number_of_units_installed=3,
        )
        assert VentilationSystem.objects.filter(building=building).count() == 2
        assert system1.id != system2.id

    def test_cascade_delete_on_building_delete(self, building):
        """Test that ventilation systems are deleted when building is deleted."""
        VentilationSystem.objects.create(
            building=building,
            ventilation_type='AHU',
            ventilation_capacity='M3H',
            baseline_efficiency_w_cmh=2,
            operation_hours_per_workday=8,
            workdays_per_week=5,
            workweeks_per_year=50,
            total_power_input_kw=1,
            air_flow_rate=500,
            demand_controlled_ventilation=True,
            variable_speed_drives=True,
            number_of_units_installed=5,
        )
        building_id = building.id
        building.delete()
        assert VentilationSystem.objects.filter(building_id=building_id).count() == 0

    def test_nullable_fields(self, building):
        """Test that optional fields can be null."""
        system = VentilationSystem.objects.create(
            building=building,
            ventilation_type='AHU',
            ventilation_capacity='M3H',
            baseline_efficiency_w_cmh=2,
            operation_hours_per_workday=8,
            workdays_per_week=5,
            workweeks_per_year=50,
            total_power_input_kw=1,
            air_flow_rate=500,
            demand_controlled_ventilation=True,
            variable_speed_drives=True,
            number_of_units_installed=5,
            # Nullable fields
            total_energy_consumption_kwh_per_year=None,
            number_of_stars=None,
        )
        assert system.total_energy_consumption_kwh_per_year is None
        assert system.number_of_stars is None

    def test_ventilation_type_choices(self, building):
        """Test ventilation type choice field."""
        system = VentilationSystem.objects.create(
            building=building,
            ventilation_type='CASSETTE_AC',
            ventilation_capacity='M3H',
            baseline_efficiency_w_cmh=2,
            operation_hours_per_workday=8,
            workdays_per_week=5,
            workweeks_per_year=50,
            total_power_input_kw=1,
            air_flow_rate=500,
            demand_controlled_ventilation=True,
            variable_speed_drives=True,
            number_of_units_installed=5,
        )
        assert system.ventilation_type == 'CASSETTE_AC'
        assert system.get_ventilation_type_display() == 'Ceiling/Wall Mounted Cassette AC'


# ============================================================================
# VIEW TESTS
# ============================================================================

@pytest.mark.django_db
class TestCreateOrUpdateVentilationSystemView:
    """Tests for the create_or_update_ventilation_system view."""

    def test_create_ventilation_system_success(self, client, user, building):
        """Test successfully creating a ventilation system."""
        client.force_login(user)
        url = reverse('ventilation_system_create_update')
        data = {
            'building_uuid': str(building.uuid),
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'yes',
            'number_of_units': 5,
            'annual_energy_consumption': 5000,
            'number_of_stars': 4,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 201
        response_data = response.json()
        assert response_data['success'] is True
        assert 'ventilation_system' in response_data
        assert response_data['ventilation_system']['ventilation_type'] == 'AHU'
        assert VentilationSystem.objects.filter(building=building).count() == 1

    def test_update_ventilation_system_success(self, client, user, ventilation_system):
        """Test successfully updating a ventilation system."""
        client.force_login(user)
        url = reverse('ventilation_system_create_update')
        data = {
            'building_uuid': str(ventilation_system.building.uuid),
            'ventilation_system_id': ventilation_system.id,
            'ventilation_type': 'FCU',
            'ventilation_capacity': 'F3M',
            'baseline_efficiency': 3,
            'operating_hours_per_day': 10,
            'operating_days_per_week': 6,
            'operating_weeks_per_year': 52,
            'power_input': 2000,
            'airflow_rate': 800,
            'demand_controlled_ventilation': 'no',
            'variable_speed_drives': 'no',
            'number_of_units': 3,
            'annual_energy_consumption': 8000,
            'number_of_stars': 5,
        }
        response = client.put(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        ventilation_system.refresh_from_db()
        assert ventilation_system.ventilation_type == 'FCU'
        assert ventilation_system.baseline_efficiency_w_cmh == 3

    def test_create_ventilation_system_missing_building_id(self, client, user):
        """Test creating without building_id returns error."""
        client.force_login(user)
        url = reverse('ventilation_system_create_update')
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False
        assert 'building_uuid' in response_data['errors']

    def test_create_ventilation_system_invalid_data(self, client, user, building):
        """Test creating with invalid data returns validation errors."""
        client.force_login(user)
        url = reverse('ventilation_system_create_update')
        data = {
            'building_uuid': str(building.uuid),
            'ventilation_type': '',  # Required field
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False

    def test_create_ventilation_system_building_not_found(self, client, user):
        """Test creating with non-existent building returns error."""
        client.force_login(user)
        url = reverse('ventilation_system_create_update')
        data = {
            'building_uuid': '00000000-0000-0000-0000-000000000000',
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False

    def test_create_ventilation_system_unauthorized_building(self, client, user, other_building):
        """Test that user cannot create ventilation system for another user's building."""
        client.force_login(user)
        url = reverse('ventilation_system_create_update')
        data = {
            'building_uuid': str(other_building.uuid),
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False

    def test_create_ventilation_system_requires_login(self, client, building):
        """Test that creating a ventilation system requires authentication."""
        url = reverse('ventilation_system_create_update')
        data = {
            'building_uuid': str(building.uuid),
            'ventilation_type': 'AHU',
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
class TestGetVentilationSystemsView:
    """Tests for the get_ventilation_systems view."""

    def test_get_ventilation_systems_success(self, client, user, building, ventilation_system):
        """Test successfully retrieving ventilation systems."""
        client.force_login(user)
        url = reverse('ventilation_system_list', kwargs={'building_uuid': building.uuid})
        response = client.get(url)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert len(response_data['ventilation_systems']) == 1
        assert response_data['ventilation_systems'][0]['id'] == ventilation_system.id

    def test_get_ventilation_systems_empty_list(self, client, user, building):
        """Test retrieving ventilation systems when none exist."""
        client.force_login(user)
        url = reverse('ventilation_system_list', kwargs={'building_uuid': building.uuid})
        response = client.get(url)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert len(response_data['ventilation_systems']) == 0

    def test_get_ventilation_systems_building_not_found(self, client, user):
        """Test retrieving with non-existent building returns error."""
        client.force_login(user)
        url = reverse('ventilation_system_list', kwargs={'building_uuid': '00000000-0000-0000-0000-000000000000'})
        response = client.get(url)
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False

    def test_get_ventilation_systems_unauthorized_building(self, client, user, other_building):
        """Test that user cannot retrieve ventilation systems from another user's building."""
        client.force_login(user)
        url = reverse('ventilation_system_list', kwargs={'building_uuid': other_building.uuid})
        response = client.get(url)
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False

    def test_get_ventilation_systems_requires_login(self, client, building):
        """Test that retrieving ventilation systems requires authentication."""
        url = reverse('ventilation_system_list', kwargs={'building_uuid': building.uuid})
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
class TestDeleteVentilationSystemView:
    """Tests for the delete_ventilation_system view."""

    def test_delete_ventilation_system_success(self, client, user, ventilation_system):
        """Test successfully deleting a ventilation system."""
        client.force_login(user)
        system_id = ventilation_system.id
        url = reverse('ventilation_system_delete', kwargs={'system_id': system_id})
        response = client.delete(url)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert not VentilationSystem.objects.filter(id=system_id).exists()

    def test_delete_ventilation_system_not_found(self, client, user):
        """Test deleting non-existent ventilation system returns error."""
        client.force_login(user)
        url = reverse('ventilation_system_delete', kwargs={'system_id': 99999})
        response = client.delete(url)
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False

    def test_delete_ventilation_system_unauthorized(self, client, user, other_building):
        """Test that user cannot delete ventilation system from another user's building."""
        other_system = VentilationSystem.objects.create(
            building=other_building,
            ventilation_type='AHU',
            ventilation_capacity='M3H',
            baseline_efficiency_w_cmh=2,
            operation_hours_per_workday=8,
            workdays_per_week=5,
            workweeks_per_year=50,
            total_power_input_kw=1,
            air_flow_rate=500,
            demand_controlled_ventilation=True,
            variable_speed_drives=True,
            number_of_units_installed=5,
        )
        client.force_login(user)
        url = reverse('ventilation_system_delete', kwargs={'system_id': other_system.id})
        response = client.delete(url)
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False
        assert VentilationSystem.objects.filter(id=other_system.id).exists()

    def test_delete_ventilation_system_requires_login(self, client, ventilation_system):
        """Test that deleting a ventilation system requires authentication."""
        url = reverse('ventilation_system_delete', kwargs={'system_id': ventilation_system.id})
        response = client.delete(url)
        assert response.status_code == 302  # Redirect to login


# ============================================================================
# FORM TESTS
# ============================================================================

@pytest.mark.django_db
class TestVentilationSystemForm:
    """Tests for the VentilationSystemForm."""

    def test_valid_form_with_all_fields(self):
        """Test form validation with all fields."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'yes',
            'number_of_units': 5,
            'annual_energy_consumption': 5000,
            'number_of_stars': 4,
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors

    def test_valid_form_with_minimal_fields(self):
        """Test form validation with only required fields."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'no',
            'variable_speed_drives': 'no',
            'number_of_units': 5,
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors

    def test_field_name_mapping(self):
        """Test that frontend field names are mapped to backend field names."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,  # Maps to baseline_efficiency_w_cmh
            'operating_hours_per_day': 8,  # Maps to operation_hours_per_workday
            'operating_days_per_week': 5,  # Maps to workdays_per_week
            'operating_weeks_per_year': 50,  # Maps to workweeks_per_year
            'power_input': 1000,  # Maps to total_power_input_kw
            'airflow_rate': 500,  # Maps to air_flow_rate
            'number_of_units': 5,  # Maps to number_of_units_installed
            'annual_energy_consumption': 5000,  # Maps to total_energy_consumption_kwh_per_year
            'number_of_stars': 4,  # Maps to number_of_stars on model
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'yes',
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.baseline_efficiency_w_cmh == 2
        assert system.operation_hours_per_workday == 8
        assert system.workdays_per_week == 5
        assert system.workweeks_per_year == 50
        assert system.total_power_input_kw == 1000
        assert system.air_flow_rate == 500
        assert system.number_of_units_installed == 5
        assert system.total_energy_consumption_kwh_per_year == 5000
        assert system.number_of_stars == 4

    def test_demand_controlled_ventilation_yes_conversion(self):
        """Test that 'yes' string is converted to True for demand_controlled_ventilation."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'no',
            'number_of_units': 5,
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.demand_controlled_ventilation is True

    def test_demand_controlled_ventilation_no_conversion(self):
        """Test that 'no' string is converted to False for demand_controlled_ventilation."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'no',
            'variable_speed_drives': 'yes',
            'number_of_units': 5,
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.demand_controlled_ventilation is False

    def test_variable_speed_drives_yes_conversion(self):
        """Test that 'yes' string is converted to True for variable_speed_drives."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'no',
            'variable_speed_drives': 'yes',
            'number_of_units': 5,
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.variable_speed_drives is True

    def test_variable_speed_drives_no_conversion(self):
        """Test that 'no' string is converted to False for variable_speed_drives."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'no',
            'number_of_units': 5,
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.variable_speed_drives is False

    def test_null_annual_energy_consumption(self):
        """Test that annual_energy_consumption can be null."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'yes',
            'number_of_units': 5,
            'annual_energy_consumption': '',
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.total_energy_consumption_kwh_per_year is None

    def test_null_number_of_stars(self):
        """Test that number_of_stars can be null."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'yes',
            'number_of_units': 5,
            'number_of_stars': '',
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.number_of_stars is None

    def test_positive_annual_energy_consumption_valid(self):
        """Test that a positive annual_energy_consumption value is valid."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'yes',
            'number_of_units': 5,
            'annual_energy_consumption': 100,
        }
        form = VentilationSystemForm(data=data)
        assert form.is_valid(), form.errors

    def test_number_of_stars_out_of_range_low(self):
        """Test that number_of_stars below 1 is invalid."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'yes',
            'number_of_units': 5,
            'number_of_stars': 0,
        }
        form = VentilationSystemForm(data=data)
        assert not form.is_valid()
        assert 'number_of_stars' in form.errors

    def test_number_of_stars_out_of_range_high(self):
        """Test that number_of_stars above 5 is invalid."""
        data = {
            'ventilation_type': 'AHU',
            'ventilation_capacity': 'M3H',
            'baseline_efficiency': 2,
            'operating_hours_per_day': 8,
            'operating_days_per_week': 5,
            'operating_weeks_per_year': 50,
            'power_input': 1000,
            'airflow_rate': 500,
            'demand_controlled_ventilation': 'yes',
            'variable_speed_drives': 'yes',
            'number_of_units': 5,
            'number_of_stars': 6,
        }
        form = VentilationSystemForm(data=data)
        assert not form.is_valid()
        assert 'number_of_stars' in form.errors