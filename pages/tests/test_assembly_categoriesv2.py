import pytest

from pages.models.assembly import (
    AssemblyCategory,
    AssemblyCategoryTechnique,
    AssemblyTechnique,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "cat, tech",
    [
        # Floor Finish
        ("Floor Finish", "Artificial grass"),
        # Foundations
        ("Foundations", "PCC for Footings"),
        ("Foundations", "Ready-Mix Concrete Columns"),
        # Columns
        ("Columns", "Ready-Mix Concrete Columns"),
        # Finish
        ("Finishes", "Cement Based Plaster"),
        ("Finishes", "White wash"),
        ("Finishes", "Primer"),
        ("Finishes", "Paint"),
        ("Finishes", "Putty"),
        ("Finishes", "Waterproofing"),
        # Miscellaneous
        ("Miscellaneous", "Lintel, Sunshade and Sill Beam"),
        ("Miscellaneous", "Construction chemical"),
        ("Miscellaneous", "Cement Mortar for Tiles"),
        ("Miscellaneous", "Aluminium Doors"),
        ("Miscellaneous", "Aluminium  Windows"),
        ("Miscellaneous", "Fire Doors"),
        ("Miscellaneous", "Anti termite treatment"),
        ("Miscellaneous", "Timber Doors and windows"),
        # Staircases and Ramps
        ("Staircases and Ramps", "In-Situ Reinforced Concrete Staircases and Ramps"),
        ("Staircases and Ramps", "MS Railings"),
        ("Staircases and Ramps", "SS Railings"),
        ("Staircases and Ramps", "Timber Railings"),
    ],
)
def test_edge_categories(cat: str, tech: str):
    """Test if new Edge catgories were added correctly

    ARRANGE: Define categories and techniques.
    ACT: Get categories, techniques, and categoriytechniques
    ASSERT: Get throws error if no match.
    """
    category = AssemblyCategory.objects.get(name=cat)
    technique = AssemblyTechnique.objects.get(name=tech)
    AssemblyCategoryTechnique.objects.get(category=category, technique=technique)
