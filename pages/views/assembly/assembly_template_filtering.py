from django.db.models import Q
from django.shortcuts import get_object_or_404

from pages.models.assembly import Assembly, AssemblyCategory, AssemblyTechnique, AssemblyDimension
import logging

def get_filtered_assembly_templates(request, user):
    """
    Filter assembly templates based on request parameters.
    Returns both user templates and generic templates.
    """
    user_templates = Assembly.objects.filter(
        created_by=user,
        is_template=True,
        is_boq=False
    ).select_related('country', 'city').prefetch_related(
        'structuralproduct_set__epd',
        'structuralproduct_set__classification__category',
        'structuralproduct_set__classification__technique'
    )

    # Generic templates are public templates (is_public=True) but exclude user's own templates to avoid duplication where it is user template and is_public=True
    generic_templates = Assembly.objects.filter(
        is_public=True,
        is_template=True,
        is_boq=False
    ).exclude(
        created_by=user
    ).select_related('country', 'city').prefetch_related(
        'structuralproduct_set__epd',
        'structuralproduct_set__classification__category',
        'structuralproduct_set__classification__technique'
    )

    if (
            request.method == "POST"
            and request.POST.get("action") == "filter"
    ) or (
            request.method == "GET"
            and any(request.GET.get(param) for param in
                    ['search_query', 'category', 'technique', 'dimension', 'country', 'template_type'])
    ):
        req = request.POST if request.method == "POST" else request.GET

        logger = logging.getLogger(__name__)
        logger.info(f"Filtering templates with params: {dict(req)}")

        # Text search filter
        if search_query := req.get("search_query"):
            search_terms = search_query.split()
            query = Q()
            for term in search_terms:
                query &= Q(name__icontains=term)
            user_templates = user_templates.filter(query)
            generic_templates = generic_templates.filter(query)

        # Category filter
        if category_id := req.get("category"):
            if category_id.strip():
                try:
                    category = get_object_or_404(AssemblyCategory, pk=int(category_id))
                    user_templates = user_templates.filter(
                        structuralproduct__classification__category=category
                    ).distinct()
                    generic_templates = generic_templates.filter(
                        structuralproduct__classification__category=category
                    ).distinct()
                    logger.info(f"Filtered by category: {category.name}")
                except (ValueError, TypeError, AssemblyCategory.DoesNotExist):
                    logger.warning(f"Invalid category ID: {category_id}")
                    pass

        # Technique filter
        if technique_id := req.get("technique"):
            if technique_id.strip():
                try:
                    technique = get_object_or_404(AssemblyTechnique, pk=int(technique_id))
                    user_templates = user_templates.filter(
                        structuralproduct__classification__technique=technique
                    ).distinct()
                    generic_templates = generic_templates.filter(
                        structuralproduct__classification__technique=technique
                    ).distinct()
                    logger.info(f"Filtered by technique: {technique.name}")
                except (ValueError, TypeError, AssemblyTechnique.DoesNotExist):
                    logger.warning(f"Invalid technique ID: {technique_id}")
                    pass

        # Dimension filter
        if dimension := req.get("dimension"):
            if dimension in [choice[0] for choice in AssemblyDimension.choices]:
                user_templates = user_templates.filter(dimension=dimension)
                generic_templates = generic_templates.filter(dimension=dimension)

        # Country filter
        if country_id := req.get("country"):
            if country_id.strip():
                try:
                    user_templates = user_templates.filter(country_id=int(country_id))
                    generic_templates = generic_templates.filter(country_id=int(country_id))
                    logger.info(f"Filtered by country ID: {country_id}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid country ID: {country_id}")
                    pass

        # Template type filter
        template_type = req.get("template_type")
        if template_type == "user":
            # Show only user's private templates (is_public=False)
            user_templates = user_templates.filter(is_public=False)
            generic_templates = Assembly.objects.none()
        elif template_type == "generic":
            # Show only public templates (is_public=True) regardless of who created them
            user_templates = Assembly.objects.none()
            generic_templates = Assembly.objects.filter(
                is_public=True,
                is_template=True,
                is_boq=False
            ).select_related('country', 'city').prefetch_related(
                'structuralproduct_set__epd',
                'structuralproduct_set__classification__category',
                'structuralproduct_set__classification__technique'
            )
            if search_query:
                query = Q()
                for term in search_query.split():
                    query &= Q(name__icontains=term)
                generic_templates = generic_templates.filter(query)
            if category_id and category_id.strip():
                try:
                    generic_templates = generic_templates.filter(
                        structuralproduct__classification__category_id=int(category_id)
                    ).distinct()
                except (ValueError, TypeError):
                    pass
            if technique_id and technique_id.strip():
                try:
                    generic_templates = generic_templates.filter(
                        structuralproduct__classification__technique_id=int(technique_id)
                    ).distinct()
                except (ValueError, TypeError):
                    pass
            if dimension and dimension in [choice[0] for choice in AssemblyDimension.choices]:
                generic_templates = generic_templates.filter(dimension=dimension)
            if country_id and country_id.strip():
                try:
                    generic_templates = generic_templates.filter(country_id=int(country_id))
                except (ValueError, TypeError):
                    pass


    return user_templates.order_by('name'), generic_templates.order_by('name')