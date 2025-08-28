import pytest
from pages.models import AssemblyCategory, AssemblyCategoryTechnique, AssemblyTechnique


@pytest.fixture(autouse=True)
def clean_db():
    """Automatically clean relevant tables before each test."""
    AssemblyCategoryTechnique.objects.all().delete()
    AssemblyCategory.objects.all().delete()
    AssemblyTechnique.objects.all().delete()


@pytest.mark.django_db
def test_create_category_auto_creates_null_join():
    """When a new AssemblyCategory is created, a null join must be created automatically."""
    category = AssemblyCategory.objects.create(name="Walls", tag="W01")

    # Auto-created join should exist
    joins = AssemblyCategoryTechnique.objects.filter(category=category)
    assert joins.count() == 1

    join = joins.first()
    assert join.technique is None
    assert join.description is None


@pytest.mark.django_db
def test_create_category_with_technique_and_null_join():
    """If we add a technique manually, it should coexist with the auto-created null join."""
    category = AssemblyCategory.objects.create(name="Floors", tag="F01")
    technique = AssemblyTechnique.objects.create(name="Concrete")

    # Add technique manually
    AssemblyCategoryTechnique.objects.create(category=category, technique=technique)

    joins = AssemblyCategoryTechnique.objects.filter(category=category)
    assert joins.count() == 2

    techniques = [j.technique for j in joins]
    assert None in techniques  # the auto-created null join
    assert technique in techniques  # the manual join


@pytest.mark.django_db
def test_unique_null_technique_logic():
    """Multiple null techniques are allowed; adding one manually increases count."""
    category = AssemblyCategory.objects.create(name="Roof", tag="R01")

    # Check the auto-created null join exists
    initial_null_count = AssemblyCategoryTechnique.objects.filter(category=category, technique=None).count()
    assert initial_null_count == 1

    # Add another null technique manually
    AssemblyCategoryTechnique.objects.create(category=category, technique=None)

    # There should now be 2 entries with None technique
    null_techniques = AssemblyCategoryTechnique.objects.filter(category=category, technique=None)
    assert null_techniques.count() == 2


@pytest.mark.django_db
def test_bulk_create_does_not_auto_create_null_joins():
    """bulk_create bypasses custom manager's create(), so no null joins should be created automatically."""
    categories = [
        AssemblyCategory(name="Cat1", tag="C01"),
        AssemblyCategory(name="Cat2", tag="C02"),
    ]
    AssemblyCategory.objects.bulk_create(categories)

    # Null joins won't exist yet
    assert AssemblyCategoryTechnique.objects.count() == 0

    # Manually create null joins
    for category in AssemblyCategory.objects.all():
        AssemblyCategoryTechnique.objects.get_or_create(category=category, technique=None)

    assert AssemblyCategoryTechnique.objects.count() == 2
