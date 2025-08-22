from django.test import TestCase
from pages.models import (
    AssemblyCategory,
    AssemblyCategoryTechnique,
    AssemblyTechnique
)
import uuid  # for generating unique test names


class AssemblyCategorySignalTest(TestCase):

    def test_null_entry_created_on_category_creation(self):
        # Generate a unique category name
        unique_name = f"Walls_{uuid.uuid4().hex[:6]}"
        category = AssemblyCategory.objects.create(name=unique_name, tag="W")

        # Ensure exactly one null entry is created
        self.assertTrue(
            AssemblyCategoryTechnique.objects.filter(category=category, technique=None).exists()
        )

    def test_no_duplicate_null_entries_on_multiple_saves(self):
        unique_name = f"Beams_{uuid.uuid4().hex[:6]}"
        category = AssemblyCategory.objects.create(name=unique_name, tag="B")

        # Saving the category again should not create a new null entry
        category.save()
        null_entries = AssemblyCategoryTechnique.objects.filter(category=category, technique=None)
        self.assertEqual(null_entries.count(), 1)

    def test_adding_techniques_does_not_duplicate_null_entry(self):
        unique_name = f"Columns_{uuid.uuid4().hex[:6]}"
        category = AssemblyCategory.objects.create(name=unique_name, tag="C")

        technique = AssemblyTechnique.objects.create(name=f"Welding_{uuid.uuid4().hex[:4]}")
        AssemblyCategoryTechnique.objects.create(category=category, technique=technique)

        # Null entry remains, plus one technique entry
        entries = AssemblyCategoryTechnique.objects.filter(category=category)
        self.assertEqual(entries.count(), 2)
        self.assertTrue(entries.filter(technique=None).exists())
        self.assertTrue(entries.filter(technique=technique).exists())
