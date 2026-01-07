"""
Tests for Cooling System models, views, and forms (Chiller and Air Conditioner).
"""
import json
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

from pages.models.building import Building
from pages.models.building_operation import CoolingSystemChiller, CoolingSystemAirConditioner
from pages.forms.cooling_system_form import CoolingSystemChillerForm, CoolingSystemAirConditionerForm

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def other_user(db):
    """Create another test user."""
    return User.objects.create_user(
        username='otheruser',
        email='other@example.com',
        password='testpass123'
    )


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
def chiller_system(db, building):
    """Create a test chiller system."""
    return CoolingSystemChiller.objects.create(
        building=building,
        chiller_type='water_cooled',
        year_of_installation=2020,
        refrigerant_type='R-134a',
        refrigerant_quantity_kg=100,
        variable_speed_drives=True,
        heat_recovery_system=False,
        total_cooling_load_rt=500,
        baseline_leakage_factor_percent=2,
        operation_hours_per_workday=10,
        workdays_per_week=5,
        workweeks_per_year=50,
        number_of_chillers=2,
    )


@pytest.fixture
def ac_system(db, building):
    """Create a test air conditioner system."""
    return CoolingSystemAirConditioner.objects.create(
        building=building,
        ac_type='vrv',
        year_of_installation=2021,
        refrigerant_type='R-410A',
        refrigerant_quantity_kg=50,
        total_cooling_load_rt=300,
        baseline_leakage_factor_percent=2,
        operation_hours_per_workday=8,
        workdays_per_week=5,
        workweeks_per_year=50,
        number_of_units=10,
    )


# ============================================================================
# MODEL TESTS - CHILLER
# ============================================================================

@pytest.mark.django_db
class TestCoolingSystemChillerModel:
    """Tests for the CoolingSystemChiller model."""

    def test_create_chiller_system(self, building):
        """Test creating a chiller system."""
        system = CoolingSystemChiller.objects.create(
            building=building,
            chiller_type='water_cooled',
            year_of_installation=2020,
            refrigerant_type='R-134a',
            refrigerant_quantity_kg=100,
            variable_speed_drives=True,
            heat_recovery_system=False,
            total_cooling_load_rt=500,
            baseline_leakage_factor_percent=2,
            number_of_chillers=2,
        )
        assert system.id is not None
        assert system.building == building
        assert system.chiller_type == 'water_cooled'
        assert system.variable_speed_drives is True

    def test_cascade_delete_on_building_delete(self, building):
        """Test that chiller systems are deleted when building is deleted."""
        CoolingSystemChiller.objects.create(
            building=building,
            chiller_type='air_cooled',
            year_of_installation=2020,
            refrigerant_type='R-134a',
            refrigerant_quantity_kg=100,
            variable_speed_drives=False,
            heat_recovery_system=True,
            total_cooling_load_rt=500,
            baseline_leakage_factor_percent=2,
            number_of_chillers=2,
        )
        building_id = building.id
        building.delete()
        assert CoolingSystemChiller.objects.filter(building_id=building_id).count() == 0


# ============================================================================
# MODEL TESTS - AIR CONDITIONER
# ============================================================================

@pytest.mark.django_db
class TestCoolingSystemAirConditionerModel:
    """Tests for the CoolingSystemAirConditioner model."""

    def test_create_ac_system(self, building):
        """Test creating an air conditioner system."""
        system = CoolingSystemAirConditioner.objects.create(
            building=building,
            ac_type='split',
            year_of_installation=2021,
            refrigerant_type='R-410A',
            refrigerant_quantity_kg=50,
            total_cooling_load_rt=300,
            baseline_leakage_factor_percent=2,
            number_of_units=10,
        )
        assert system.id is not None
        assert system.building == building
        assert system.ac_type == 'split'

    def test_cascade_delete_on_building_delete(self, building):
        """Test that AC systems are deleted when building is deleted."""
        CoolingSystemAirConditioner.objects.create(
            building=building,
            ac_type='vrv',
            year_of_installation=2021,
            refrigerant_type='R-410A',
            refrigerant_quantity_kg=50,
            total_cooling_load_rt=300,
            baseline_leakage_factor_percent=2,
            number_of_units=10,
        )
        building_id = building.id
        building.delete()
        assert CoolingSystemAirConditioner.objects.filter(building_id=building_id).count() == 0


# ============================================================================
# VIEW TESTS - CREATE/UPDATE
# ============================================================================

@pytest.mark.django_db
class TestCreateOrUpdateCoolingSystemView:
    """Tests for the create_or_update_cooling_system view."""

    def test_create_chiller_system_success(self, client, user, building):
        """Test successfully creating a chiller system."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_id': str(building.id),
            'cooling_system_type': 'chiller',
            'chiller_system': 'water-cooled',
            'year_of_installation': 2020,
            'type_of_refrigerants': 'R-134a',
            'refrigerant_quantity': 100,
            'installation_of_variable_speed_drives': 'yes',
            'installation_of_heat_recovery_systems': 'no',
            'total_chiller_system': 500,
            'baseline_leakage_factor': 2,
            'number_of_chillers': 2,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 201
        response_data = response.json()
        assert response_data['success'] is True
        assert response_data['cooling_system']['cooling_system_type'] == 'chiller'
        assert CoolingSystemChiller.objects.filter(building=building).count() == 1

    def test_create_ac_system_success(self, client, user, building):
        """Test successfully creating an air conditioner system."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_id': str(building.id),
            'cooling_system_type': 'air_conditioner',
            'type_of_air_condition': 'vrv',
            'year_of_installation': 2021,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 50,
            'total_cooling_load_for_split_vrv': 300,
            'baseline_leakage_factor': 2,
            'number_of_split_vrv_units': 10,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 201
        response_data = response.json()
        assert response_data['success'] is True
        assert response_data['cooling_system']['cooling_system_type'] == 'air_conditioner'
        assert CoolingSystemAirConditioner.objects.filter(building=building).count() == 1

    def test_update_chiller_system_success(self, client, user, chiller_system):
        """Test successfully updating a chiller system."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_id': str(chiller_system.building.id),
            'cooling_system_id': chiller_system.id,
            'cooling_system_type': 'chiller',
            'chiller_system': 'air-cooled',
            'year_of_installation': 2022,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 150,
            'installation_of_variable_speed_drives': 'no',
            'installation_of_heat_recovery_systems': 'yes',
            'total_chiller_system': 600,
            'baseline_leakage_factor': 3,
            'number_of_chillers': 3,
        }
        response = client.put(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        chiller_system.refresh_from_db()
        assert chiller_system.chiller_type == 'air_cooled'
        assert chiller_system.year_of_installation == 2022

    def test_create_cooling_system_missing_type(self, client, user, building):
        """Test creating without cooling_system_type returns error."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_id': str(building.id),
            'year_of_installation': 2020,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False
        assert 'cooling_system_type' in response_data['errors']

    def test_create_cooling_system_invalid_type(self, client, user, building):
        """Test creating with invalid cooling_system_type returns error."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_id': str(building.id),
            'cooling_system_type': 'invalid_type',
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False

    def test_create_cooling_system_unauthorized_building(self, client, user, other_building):
        """Test that user cannot create cooling system for another user's building."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_id': str(other_building.id),
            'cooling_system_type': 'chiller',
            'chiller_system': 'water-cooled',
            'year_of_installation': 2020,
            'type_of_refrigerants': 'R-134a',
            'refrigerant_quantity': 100,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False


# ============================================================================
# VIEW TESTS - GET
# ============================================================================

@pytest.mark.django_db
class TestGetCoolingSystemsView:
    """Tests for the get_cooling_systems view."""

    def test_get_cooling_systems_success(self, client, user, building, chiller_system, ac_system):
        """Test successfully retrieving both chiller and AC systems."""
        client.force_login(user)
        url = reverse('cooling_system_list', kwargs={'building_id': building.id})
        response = client.get(url)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert len(response_data['cooling_systems']) == 2

        # Check that both types are present
        system_types = [s['cooling_system_type'] for s in response_data['cooling_systems']]
        assert 'chiller' in system_types
        assert 'air_conditioner' in system_types

    def test_get_cooling_systems_empty_list(self, client, user, building):
        """Test retrieving cooling systems when none exist."""
        client.force_login(user)
        url = reverse('cooling_system_list', kwargs={'building_id': building.id})
        response = client.get(url)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert len(response_data['cooling_systems']) == 0

    def test_get_cooling_systems_unauthorized_building(self, client, user, other_building):
        """Test that user cannot retrieve cooling systems from another user's building."""
        client.force_login(user)
        url = reverse('cooling_system_list', kwargs={'building_id': other_building.id})
        response = client.get(url)
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False


# ============================================================================
# VIEW TESTS - DELETE
# ============================================================================

@pytest.mark.django_db
class TestDeleteCoolingSystemView:
    """Tests for the delete_cooling_system view."""

    def test_delete_chiller_system_success(self, client, user, chiller_system):
        """Test successfully deleting a chiller system."""
        client.force_login(user)
        system_id = chiller_system.id
        url = reverse('cooling_system_delete', kwargs={'system_id': system_id})
        response = client.delete(f'{url}?cooling_system_type=chiller')
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert not CoolingSystemChiller.objects.filter(id=system_id).exists()

    def test_delete_ac_system_success(self, client, user, ac_system):
        """Test successfully deleting an AC system."""
        client.force_login(user)
        system_id = ac_system.id
        url = reverse('cooling_system_delete', kwargs={'system_id': system_id})
        response = client.delete(f'{url}?cooling_system_type=air_conditioner')
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert not CoolingSystemAirConditioner.objects.filter(id=system_id).exists()

    def test_delete_cooling_system_missing_type(self, client, user, chiller_system):
        """Test deleting without cooling_system_type returns error."""
        client.force_login(user)
        url = reverse('cooling_system_delete', kwargs={'system_id': chiller_system.id})
        response = client.delete(url)
        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False
        assert 'cooling_system_type' in response_data['errors']

    def test_delete_cooling_system_not_found(self, client, user):
        """Test deleting non-existent cooling system returns error."""
        client.force_login(user)
        url = reverse('cooling_system_delete', kwargs={'system_id': 99999})
        response = client.delete(f'{url}?cooling_system_type=chiller')
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False

    def test_delete_cooling_system_unauthorized(self, client, user, other_building):
        """Test that user cannot delete cooling system from another user's building."""
        other_chiller = CoolingSystemChiller.objects.create(
            building=other_building,
            chiller_type='water_cooled',
            year_of_installation=2020,
            refrigerant_type='R-134a',
            refrigerant_quantity_kg=100,
            variable_speed_drives=True,
            heat_recovery_system=False,
            total_cooling_load_rt=500,
            baseline_leakage_factor_percent=2,
            number_of_chillers=2,
        )
        client.force_login(user)
        url = reverse('cooling_system_delete', kwargs={'system_id': other_chiller.id})
        response = client.delete(f'{url}?cooling_system_type=chiller')
        assert response.status_code == 404
        response_data = response.json()
        assert response_data['success'] is False
        assert CoolingSystemChiller.objects.filter(id=other_chiller.id).exists()


# ============================================================================
# FORM TESTS - CHILLER
# ============================================================================

@pytest.mark.django_db
class TestCoolingSystemChillerForm:
    """Tests for the CoolingSystemChillerForm."""

    def test_valid_chiller_form(self):
        """Test form validation with chiller data."""
        data = {
            'chiller_system': 'water-cooled',
            'year_of_installation': 2020,
            'type_of_refrigerants': 'R-134a',
            'refrigerant_quantity': 100,
            'installation_of_variable_speed_drives': 'yes',
            'installation_of_heat_recovery_systems': 'no',
            'total_chiller_system': 500,
            'baseline_leakage_factor': 2,
            'number_of_chillers': 2,
        }
        form = CoolingSystemChillerForm(data=data)
        assert form.is_valid(), form.errors

    def test_field_name_mapping(self):
        """Test that frontend field names are mapped to backend field names."""
        data = {
            'chiller_system': 'water-cooled',
            'year_of_installation': 2020,
            'type_of_refrigerants': 'R-134a',
            'refrigerant_quantity': 100,
            'installation_of_variable_speed_drives': 'yes',
            'installation_of_heat_recovery_systems': 'no',
            'total_chiller_system': 500,
            'baseline_leakage_factor': 2,
            'number_of_chillers': 2,
        }
        form = CoolingSystemChillerForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.chiller_type == 'water_cooled'
        assert system.refrigerant_type == 'R-134a'
        assert system.refrigerant_quantity_kg == 100
        assert system.variable_speed_drives is True
        assert system.heat_recovery_system is False

    def test_boolean_conversion(self):
        """Test that yes/no strings are converted to boolean."""
        data = {
            'chiller_system': 'air-cooled',
            'year_of_installation': 2020,
            'type_of_refrigerants': 'R-134a',
            'refrigerant_quantity': 100,
            'installation_of_variable_speed_drives': 'no',
            'installation_of_heat_recovery_systems': 'yes',
            'total_chiller_system': 500,
            'baseline_leakage_factor': 2,
            'number_of_chillers': 2,
        }
        form = CoolingSystemChillerForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.variable_speed_drives is False
        assert system.heat_recovery_system is True


# ============================================================================
# FORM TESTS - AIR CONDITIONER
# ============================================================================

@pytest.mark.django_db
class TestCoolingSystemAirConditionerForm:
    """Tests for the CoolingSystemAirConditionerForm."""

    def test_valid_ac_form(self):
        """Test form validation with air conditioner data."""
        data = {
            'type_of_air_condition': 'vrv',
            'year_of_installation': 2021,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 50,
            'total_cooling_load_for_split_vrv': 300,
            'baseline_leakage_factor': 2,
            'number_of_split_vrv_units': 10,
        }
        form = CoolingSystemAirConditionerForm(data=data)
        assert form.is_valid(), form.errors

    def test_field_name_mapping(self):
        """Test that frontend field names are mapped to backend field names."""
        data = {
            'type_of_air_condition': 'split',
            'year_of_installation': 2021,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 50,
            'total_cooling_load_for_split_vrv': 300,
            'baseline_leakage_factor': 2,
            'number_of_split_vrv_units': 10,
        }
        form = CoolingSystemAirConditionerForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.ac_type == 'split'
        assert system.refrigerant_type == 'R-410A'
        assert system.refrigerant_quantity_kg == 50
        assert system.total_cooling_load_rt == 300
        assert system.number_of_units == 10