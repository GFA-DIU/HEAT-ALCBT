from django.core.paginator import Paginator
from django.db.models import Prefetch
from dataclasses import dataclass
from typing import Optional

from pages.models.assembly import Assembly


@dataclass
class ProcessedAssemblyTemplate:
    """Dataclass to hold processed assembly template information for display."""

    id: str
    name: str
    mode: str
    dimension: str
    dimension_display: str
    country_name: Optional[str]
    city_name: Optional[str]
    category_name: Optional[str]
    technique_name: Optional[str]
    comment: Optional[str]
    description: Optional[str]
    material_count: int
    created_at: str
    is_template: bool
    is_public: bool


class AssemblyTemplateLazyProcessor:
    """
    Lazy processor for Assembly templates to handle efficient pagination
    and preprocessing of template data for display.
    """

    def __init__(self, queryset):
        self.queryset = queryset

    def __iter__(self):
        for template in self.queryset:
            yield self.template_processing(template)

    def __len__(self):
        # Handle both querysets and lists
        if hasattr(self.queryset, 'model') and hasattr(self.queryset, 'count'):
            # This is a Django queryset - use the count method to avoid full evaluation
            return self.queryset.count()
        else:
            # This is a list or other iterable - use len()
            return len(self.queryset)

    def __getitem__(self, index):
        """
        Supports slicing for the LazyWrapper.

        Args:
            index (int or slice): The index or slice to retrieve.

        Returns:
            ProcessedAssemblyTemplate or list[ProcessedAssemblyTemplate]: The preprocessed item(s).
        """
        if isinstance(index, slice):
            # Slicing the queryset and applying preprocessing lazily
            return [self.template_processing(template) for template in self.queryset[index]]
        elif isinstance(index, int):
            # Single item access
            if index < 0:
                # Handle negative indexing
                index += len(self)
            if index < 0 or index >= len(self):
                raise IndexError("Index out of range")
            return self.template_processing(self.queryset[index])
        else:
            raise TypeError("Invalid argument type")

    def template_processing(self, template: Assembly):
        """Encapsulates the logic for preprocessing Assembly templates."""

        # Get first classification for display
        classification = template.classification

        return ProcessedAssemblyTemplate(
            id=str(template.pk),
            name=template.name,
            mode=template.mode,
            dimension=template.dimension,
            dimension_display=template.get_dimension_display(),
            country_name=template.country.name if template.country else None,
            city_name=template.city.name if template.city else None,
            category_name=classification.category.name if classification and classification.category else None,
            technique_name=classification.technique.name if classification and classification.technique else None,
            comment=template.comment,
            description=template.description,
            material_count=len(getattr(template, 'prefetched_products', [])) if hasattr(template, 'prefetched_products') else template.structuralproduct_set.count(),
            created_at=template.created_at.strftime("%B %d, %Y") if template.created_at else "",
            is_template=template.is_template,
            is_public=template.is_public,
        )


def get_paginated_templates(queryset, page_number=1, per_page=12):
    """
    Get paginated assembly templates with lazy processing.

    Args:
        queryset: Assembly queryset
        page_number: Page number to retrieve
        per_page: Number of items per page

    Returns:
        Paginated Page object with processed templates
    """
    # Prefetch related data for efficiency
    prefetched_queryset = prefetch_assembly_templates(queryset)

    # Create lazy processor
    lazy_queryset = AssemblyTemplateLazyProcessor(prefetched_queryset)

    # Setup pagination
    paginator = Paginator(lazy_queryset, per_page)
    return paginator.get_page(page_number)


def prefetch_assembly_templates(templates):
    """
    Prefetch related data for Assembly templates to improve performance.
    """
    from pages.models.assembly import StructuralProduct

    return (
        templates
        .select_related(
            "country",
            "city",
            "created_by",
        )
        .prefetch_related(
            Prefetch(
                "structuralproduct_set",
                queryset=StructuralProduct.objects.select_related(
                    "epd",
                    "classification__category",
                    "classification__technique"
                ),
                to_attr="prefetched_products",
            )
        )
    )