"""
Tests for Cooling System models, views, and forms (Chiller and Air Conditioner).
"""
import json
import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

from pages.models.building import Building
from pages.models.building_operation import CoolingSystemChiller, CoolingSystemAirConditioner
from pages.forms.cooling_system_form import CoolingSystemChillerForm, CoolingSystemAirConditionerForm

User = get_user_model()


def _make_verified_user(username, email, password):
    u = User.objects.create_user(username=username, email=email, password=password)
    EmailAddress.objects.create(user=u, email=email, verified=True, primary=True)
    return u


@pytest.fixture
def user(db):
    return _make_verified_user('testuser', 'test@example.com', 'testpass123')


@pytest.fixture
def other_user(db):
    return _make_verified_user('otheruser', 'other@example.com', 'testpass123')


@pytest.fixture
def building(db, user):
    return Building.objects.create(
        name='Test Building',
        total_floor_area=1000.00,
        created_by=user
    )


@pytest.fixture
def other_building(db, other_user):
    return Building.objects.create(
        name='Other Building',
        total_floor_area=1000.00,
        created_by=other_user
    )


@pytest.fixture
def chiller_system(db, building):
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
    """Create a test air conditioner system with new fields."""
    return CoolingSystemAirConditioner.objects.create(
        building=building,
        ac_type='vrv',
        year_of_installation=2021,
        refrigerant_type='R-410A',
        refrigerant_quantity_kg=50,
        cooling_capacity_per_unit_kw=Decimal('10.548'),  # 3 Ton in kW
        eer_iseer_cop=Decimal('4.0'),
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

    def test_create_chiller_system(self, building):
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

    def test_create_ac_system(self, building):
        system = CoolingSystemAirConditioner.objects.create(
            building=building,
            ac_type='split',
            year_of_installation=2021,
            refrigerant_type='R-410A',
            refrigerant_quantity_kg=50,
            cooling_capacity_per_unit_kw=Decimal('5.274'),  # 1.5 Ton
            eer_iseer_cop=Decimal('3.2'),
            baseline_leakage_factor_percent=2,
            number_of_units=10,
        )
        assert system.id is not None
        assert system.building == building
        assert system.ac_type == 'split'
        assert system.cooling_capacity_per_unit_kw == Decimal('5.274')
        assert system.eer_iseer_cop == Decimal('3.2')

    def test_ac_system_new_fields_nullable(self, building):
        """New fields (cooling_capacity_per_unit_kw, eer_iseer_cop, power_input_per_unit_kw) are nullable."""
        system = CoolingSystemAirConditioner.objects.create(
            building=building,
            ac_type='window',
            year_of_installation=2020,
            refrigerant_type='R-410A',
            refrigerant_quantity_kg=5,
            baseline_leakage_factor_percent=2,
            number_of_units=1,
        )
        assert system.cooling_capacity_per_unit_kw is None
        assert system.eer_iseer_cop is None
        assert system.power_input_per_unit_kw is None

    def test_cascade_delete_on_building_delete(self, building):
        CoolingSystemAirConditioner.objects.create(
            building=building,
            ac_type='vrv',
            year_of_installation=2021,
            refrigerant_type='R-410A',
            refrigerant_quantity_kg=50,
            cooling_capacity_per_unit_kw=Decimal('10.548'),
            eer_iseer_cop=Decimal('4.0'),
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

    def test_create_chiller_system_success(self, client, user, building):
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_uuid': str(building.uuid),
            'cooling_system_type': 'chiller',
            'chiller_system': 'water-cooled',
            'year_of_installation': 2020,
            'type_of_refrigerants': 'R-134a',
            'refrigerant_quantity': 100,
            'installation_of_variable_speed_drives': 'yes',
            'installation_of_heat_recovery_systems': 'no',
            'total_cooling_load': 500,
            'baseline_leakage_factor': 2,
            'number_of_chillers': 2,
        }
        response = client.post(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 201
        response_data = response.json()
        assert response_data['success'] is True
        assert response_data['cooling_system']['cooling_system_type'] == 'chiller'
        assert CoolingSystemChiller.objects.filter(building=building).count() == 1

    def test_create_ac_system_success(self, client, user, building):
        """Test creating AC with new cooling_capacity_per_unit + eer_iseer_cop fields."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_uuid': str(building.uuid),
            'cooling_system_type': 'air_conditioner',
            'type_of_air_condition': 'vrv',
            'year_of_installation': 2021,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 50,
            'cooling_capacity_per_unit': '3',
            'cooling_capacity_unit': 'ton',
            'eer_iseer_cop': '4.0',
            'baseline_leakage_factor': 2,
            'number_of_units': 10,
            'hours_per_day': 8,
            'days_per_week': 5,
            'weeks_per_year': 50,
        }
        response = client.post(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 201
        response_data = response.json()
        assert response_data['success'] is True
        assert response_data['cooling_system']['cooling_system_type'] == 'air_conditioner'
        # Capacity should be stored as kW (3 Ton × 3.516 = 10.548)
        assert response_data['cooling_system']['cooling_capacity_per_unit_kw'] == pytest.approx(10.548, abs=0.001)
        assert CoolingSystemAirConditioner.objects.filter(building=building).count() == 1

    def test_create_ac_system_kw_unit(self, client, user, building):
        """Test creating AC with capacity provided directly in kW."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_uuid': str(building.uuid),
            'cooling_system_type': 'air_conditioner',
            'type_of_air_condition': 'split',
            'year_of_installation': 2022,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 20,
            'cooling_capacity_per_unit': '5.5',
            'cooling_capacity_unit': 'kw',
            'eer_iseer_cop': '3.2',
            'baseline_leakage_factor': 2,
            'number_of_units': 5,
            'hours_per_day': 10,
            'days_per_week': 5,
            'weeks_per_year': 52,
        }
        response = client.post(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 201
        response_data = response.json()
        assert response_data['cooling_system']['cooling_capacity_per_unit_kw'] == pytest.approx(5.5, abs=0.001)

    def test_create_ac_system_with_power_input(self, client, user, building):
        """Test creating AC with optional power_input_per_unit field."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_uuid': str(building.uuid),
            'cooling_system_type': 'air_conditioner',
            'type_of_air_condition': 'window',
            'year_of_installation': 2021,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 5,
            'cooling_capacity_per_unit': '1.5',
            'cooling_capacity_unit': 'ton',
            'eer_iseer_cop': '3.0',
            'power_input_per_unit': '1.75',
            'baseline_leakage_factor': 2,
            'number_of_units': 3,
            'hours_per_day': 8,
            'days_per_week': 5,
            'weeks_per_year': 50,
        }
        response = client.post(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 201
        response_data = response.json()
        assert response_data['cooling_system']['power_input_per_unit_kw'] == pytest.approx(1.75, abs=0.001)

    def test_create_packaged_ac_success(self, client, user, building):
        """Test creating packaged AC with subtype."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_uuid': str(building.uuid),
            'cooling_system_type': 'air_conditioner',
            'type_of_air_condition': 'packaged',
            'packaged_subtype': 'rooftop',
            'year_of_installation': 2020,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 30,
            'cooling_capacity_per_unit': '5',
            'cooling_capacity_unit': 'ton',
            'eer_iseer_cop': '3.0',
            'baseline_leakage_factor': 2,
            'number_of_units': 4,
            'hours_per_day': 10,
            'days_per_week': 5,
            'weeks_per_year': 50,
        }
        response = client.post(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 201
        response_data = response.json()
        assert response_data['success'] is True
        assert response_data['cooling_system']['packaged_subtype'] == 'rooftop'

    def test_update_chiller_system_success(self, client, user, chiller_system):
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_uuid': str(chiller_system.building.uuid),
            'cooling_system_id': chiller_system.id,
            'cooling_system_type': 'chiller',
            'chiller_system': 'air-cooled',
            'year_of_installation': 2022,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 150,
            'installation_of_variable_speed_drives': 'no',
            'installation_of_heat_recovery_systems': 'yes',
            'total_cooling_load': 600,
            'baseline_leakage_factor': 3,
            'number_of_chillers': 3,
        }
        response = client.put(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        chiller_system.refresh_from_db()
        assert chiller_system.chiller_type == 'air_cooled'
        assert chiller_system.year_of_installation == 2022

    def test_update_ac_system_success(self, client, user, ac_system):
        """Test updating an AC system with new fields."""
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_uuid': str(ac_system.building.uuid),
            'cooling_system_id': ac_system.id,
            'cooling_system_type': 'air_conditioner',
            'type_of_air_condition': 'vrv',
            'year_of_installation': 2023,
            'type_of_refrigerants': 'R-32',
            'refrigerant_quantity': 40,
            'cooling_capacity_per_unit': '12',
            'cooling_capacity_unit': 'kw',
            'eer_iseer_cop': '4.5',
            'baseline_leakage_factor': 2,
            'number_of_units': 8,
            'hours_per_day': 10,
            'days_per_week': 5,
            'weeks_per_year': 52,
        }
        response = client.put(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        ac_system.refresh_from_db()
        assert ac_system.year_of_installation == 2023
        assert ac_system.cooling_capacity_per_unit_kw == Decimal('12.000')

    def test_create_cooling_system_missing_type(self, client, user, building):
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {'building_uuid': str(building.uuid), 'year_of_installation': 2020}
        response = client.post(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 400
        assert response.json()['errors'].get('cooling_system_type') is not None

    def test_create_cooling_system_invalid_type(self, client, user, building):
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {'building_uuid': str(building.uuid), 'cooling_system_type': 'invalid_type'}
        response = client.post(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 400
        assert response.json()['success'] is False

    def test_create_cooling_system_unauthorized_building(self, client, user, other_building):
        client.force_login(user)
        url = reverse('cooling_system_create_update')
        data = {
            'building_uuid': str(other_building.uuid),
            'cooling_system_type': 'chiller',
            'chiller_system': 'water-cooled',
            'year_of_installation': 2020,
            'type_of_refrigerants': 'R-134a',
            'refrigerant_quantity': 100,
        }
        response = client.post(url, data=json.dumps(data), content_type='application/json')
        assert response.status_code == 404
        assert response.json()['success'] is False


# ============================================================================
# VIEW TESTS - GET
# ============================================================================

@pytest.mark.django_db
class TestGetCoolingSystemsView:

    def test_get_cooling_systems_success(self, client, user, building, chiller_system, ac_system):
        client.force_login(user)
        url = reverse('cooling_system_list', kwargs={'building_uuid': str(building.uuid)})
        response = client.get(url)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert len(response_data['cooling_systems']) == 2
        system_types = [s['cooling_system_type'] for s in response_data['cooling_systems']]
        assert 'chiller' in system_types
        assert 'air_conditioner' in system_types

    def test_get_cooling_systems_includes_new_ac_fields(self, client, user, building, ac_system):
        """Response includes cooling_capacity_per_unit_kw, eer_iseer_cop, power_input_per_unit_kw."""
        client.force_login(user)
        url = reverse('cooling_system_list', kwargs={'building_uuid': str(building.uuid)})
        response = client.get(url)
        ac = next(s for s in response.json()['cooling_systems'] if s['cooling_system_type'] == 'air_conditioner')
        assert 'cooling_capacity_per_unit_kw' in ac
        assert 'eer_iseer_cop' in ac
        assert 'power_input_per_unit_kw' in ac
        assert ac['cooling_capacity_per_unit_kw'] == pytest.approx(10.548, abs=0.001)
        assert ac['eer_iseer_cop'] == pytest.approx(4.0, abs=0.01)

    def test_get_cooling_systems_empty_list(self, client, user, building):
        client.force_login(user)
        url = reverse('cooling_system_list', kwargs={'building_uuid': str(building.uuid)})
        response = client.get(url)
        assert response.status_code == 200
        assert response.json()['cooling_systems'] == []

    def test_get_cooling_systems_unauthorized_building(self, client, user, other_building):
        client.force_login(user)
        url = reverse('cooling_system_list', kwargs={'building_uuid': str(other_building.uuid)})
        response = client.get(url)
        assert response.status_code == 404
        assert response.json()['success'] is False


# ============================================================================
# VIEW TESTS - DELETE
# ============================================================================

@pytest.mark.django_db
class TestDeleteCoolingSystemView:

    def test_delete_chiller_system_success(self, client, user, chiller_system):
        client.force_login(user)
        system_id = chiller_system.id
        url = reverse('cooling_system_delete', kwargs={'system_id': system_id})
        response = client.delete(f'{url}?cooling_system_type=chiller')
        assert response.status_code == 200
        assert response.json()['success'] is True
        assert not CoolingSystemChiller.objects.filter(id=system_id).exists()

    def test_delete_ac_system_success(self, client, user, ac_system):
        client.force_login(user)
        system_id = ac_system.id
        url = reverse('cooling_system_delete', kwargs={'system_id': system_id})
        response = client.delete(f'{url}?cooling_system_type=air_conditioner')
        assert response.status_code == 200
        assert response.json()['success'] is True
        assert not CoolingSystemAirConditioner.objects.filter(id=system_id).exists()

    def test_delete_cooling_system_missing_type(self, client, user, chiller_system):
        client.force_login(user)
        url = reverse('cooling_system_delete', kwargs={'system_id': chiller_system.id})
        response = client.delete(url)
        assert response.status_code == 400
        assert 'cooling_system_type' in response.json()['errors']

    def test_delete_cooling_system_not_found(self, client, user):
        client.force_login(user)
        url = reverse('cooling_system_delete', kwargs={'system_id': 99999})
        response = client.delete(f'{url}?cooling_system_type=chiller')
        assert response.status_code == 404
        assert response.json()['success'] is False

    def test_delete_cooling_system_unauthorized(self, client, user, other_building):
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
        assert response.json()['success'] is False
        assert CoolingSystemChiller.objects.filter(id=other_chiller.id).exists()


# ============================================================================
# FORM TESTS - CHILLER
# ============================================================================

@pytest.mark.django_db
class TestCoolingSystemChillerForm:

    def _base_chiller_data(self, chiller_type='water-cooled', **overrides):
        data = {
            'chiller_system': chiller_type,
            'year_of_installation': 2020,
            'type_of_refrigerants': 'R-134a',
            'refrigerant_quantity': 100,
            'installation_of_variable_speed_drives': 'yes',
            'installation_of_heat_recovery_systems': 'no',
            'total_cooling_load': 500,
            'baseline_leakage_factor': 2,
            'number_of_chillers': 2,
        }
        data.update(overrides)
        return data

    def test_valid_chiller_form(self):
        form = CoolingSystemChillerForm(data=self._base_chiller_data())
        assert form.is_valid(), form.errors

    def test_field_name_mapping(self):
        form = CoolingSystemChillerForm(data=self._base_chiller_data())
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.chiller_type == 'water_cooled'
        assert system.refrigerant_type == 'R-134a'
        assert system.refrigerant_quantity_kg == 100
        assert system.variable_speed_drives is True
        assert system.heat_recovery_system is False

    def test_boolean_conversion(self):
        data = self._base_chiller_data(
            chiller_type='air-cooled',
            installation_of_variable_speed_drives='no',
            installation_of_heat_recovery_systems='yes',
        )
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

    def _base_ac_data(self, ac_type='vrv', **overrides):
        """Return minimal valid AC form data using new fields."""
        data = {
            'type_of_air_condition': ac_type,
            'year_of_installation': 2021,
            'type_of_refrigerants': 'R-410A',
            'refrigerant_quantity': 50,
            'cooling_capacity_per_unit': '3',
            'cooling_capacity_unit': 'ton',
            'eer_iseer_cop': '4.0',
            'baseline_leakage_factor': 2,
            'number_of_units': 10,
            'hours_per_day': 8,
            'days_per_week': 5,
            'weeks_per_year': 50,
        }
        data.update(overrides)
        return data

    def test_valid_ac_form_vrv(self):
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data('vrv'))
        assert form.is_valid(), form.errors

    def test_valid_ac_form_window(self):
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data('window'))
        assert form.is_valid(), form.errors

    def test_valid_ac_form_split(self):
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data('split'))
        assert form.is_valid(), form.errors

    def test_valid_ac_form_packaged(self):
        data = self._base_ac_data('packaged')
        data['packaged_subtype'] = 'rooftop'
        form = CoolingSystemAirConditionerForm(data=data)
        assert form.is_valid(), form.errors

    def test_field_name_mapping(self):
        """Frontend field names are correctly mapped to model field names."""
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data('split'))
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.ac_type == 'split'
        assert system.refrigerant_type == 'R-410A'
        assert system.refrigerant_quantity_kg == 50
        assert system.number_of_units == 10

    def test_capacity_conversion_ton_to_kw(self):
        """3 Ton → 10.548 kW (3 × 3.516)."""
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data(cooling_capacity_per_unit='3', cooling_capacity_unit='ton'))
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.cooling_capacity_per_unit_kw == Decimal('10.548')

    def test_capacity_conversion_btu_to_kw(self):
        """12000 BTU/hr → 3.516 kW (1 Ton equivalent)."""
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data(cooling_capacity_per_unit='12000', cooling_capacity_unit='btu_hr'))
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.cooling_capacity_per_unit_kw == Decimal('3.516')

    def test_capacity_unit_kw_no_conversion(self):
        """Value in kW is stored as-is."""
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data(cooling_capacity_per_unit='5.5', cooling_capacity_unit='kw'))
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.cooling_capacity_per_unit_kw == Decimal('5.500')

    def test_eer_iseer_cop_stored(self):
        """EER/ISEER/COP value is correctly stored."""
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data(eer_iseer_cop='3.8'))
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.eer_iseer_cop == Decimal('3.8')

    def test_eer_zero_is_invalid(self):
        """EER of zero must fail validation."""
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data(eer_iseer_cop='0'))
        assert not form.is_valid()
        assert 'eer_iseer_cop' in form.errors

    def test_eer_negative_is_invalid(self):
        """Negative EER must fail validation."""
        form = CoolingSystemAirConditionerForm(data=self._base_ac_data(eer_iseer_cop='-1'))
        assert not form.is_valid()
        assert 'eer_iseer_cop' in form.errors

    def test_power_input_per_unit_optional(self):
        """power_input_per_unit is optional — form is valid without it."""
        data = self._base_ac_data()
        data.pop('cooling_capacity_per_unit', None)  # ensure not set
        data['cooling_capacity_per_unit'] = '3'
        form = CoolingSystemAirConditionerForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.power_input_per_unit_kw is None

    def test_power_input_per_unit_stored(self):
        """power_input_per_unit is mapped to power_input_per_unit_kw."""
        data = self._base_ac_data()
        data['power_input_per_unit'] = '1.75'
        form = CoolingSystemAirConditionerForm(data=data)
        assert form.is_valid(), form.errors
        system = form.save(commit=False)
        assert system.power_input_per_unit_kw == Decimal('1.75')

    def test_energy_efficiency_label_valid(self):
        data = self._base_ac_data()
        data['energy_efficiency_label'] = 'B'
        form = CoolingSystemAirConditionerForm(data=data)
        assert form.is_valid(), form.errors
        assert form.cleaned_data['energy_efficiency_label'] == 'B'

    def test_energy_efficiency_label_invalid(self):
        data = self._base_ac_data()
        data['energy_efficiency_label'] = 'Z'
        form = CoolingSystemAirConditionerForm(data=data)
        assert not form.is_valid()
        assert 'energy_efficiency_label' in form.errors

    def test_number_of_stars_valid(self):
        data = self._base_ac_data()
        data['number_of_stars'] = 3
        form = CoolingSystemAirConditionerForm(data=data)
        assert form.is_valid(), form.errors
        assert form.cleaned_data['number_of_stars'] == 3

    def test_number_of_stars_out_of_range(self):
        data = self._base_ac_data()
        data['number_of_stars'] = 6
        form = CoolingSystemAirConditionerForm(data=data)
        assert not form.is_valid()
        assert 'number_of_stars' in form.errors