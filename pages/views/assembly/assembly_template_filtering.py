from django.db.models import Q
from django.shortcuts import get_object_or_404

from pages.models.assembly import Assembly, AssemblyCategory, AssemblyTechnique, AssemblyDimension


def get_filtered_assembly_templates(request, user):
    """
    Filter assembly templates based on request parameters.
    Returns both user templates and generic templates separately.
    """
    # Start with base querysets
    user_templates = Assembly.objects.filter(
        created_by=user,
        is_template=True,
        is_boq=False
    ).select_related('country', 'city').prefetch_related(
        'structuralproduct_set__epd',
        'structuralproduct_set__classification__category',
        'structuralproduct_set__classification__technique'
    )
    
    generic_templates = Assembly.objects.filter(
        mode='generic',
        is_template=True,
        is_boq=False
    ).select_related('country', 'city').prefetch_related(
        'structuralproduct_set__epd',
        'structuralproduct_set__classification__category', 
        'structuralproduct_set__classification__technique'
    )
    
    # Apply filters if this is a filter request
    if (
        request.method == "POST" 
        and request.POST.get("action") == "filter"
    ) or (
        request.method == "GET" 
        and any(request.GET.get(param) for param in ['search_query', 'category', 'technique', 'dimension', 'country', 'template_type'])
    ):
        req = request.POST if request.method == "POST" else request.GET
        
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
            try:
                category = get_object_or_404(AssemblyCategory, pk=int(category_id))
                # Filter by assemblies that have structural products with this category
                user_templates = user_templates.filter(
                    structuralproduct_set__classification__category=category
                ).distinct()
                generic_templates = generic_templates.filter(
                    structuralproduct_set__classification__category=category
                ).distinct()
            except (ValueError, TypeError):
                pass
        
        # Technique filter
        if technique_id := req.get("technique"):
            try:
                technique = get_object_or_404(AssemblyTechnique, pk=int(technique_id))
                user_templates = user_templates.filter(
                    structuralproduct_set__classification__technique=technique
                ).distinct()
                generic_templates = generic_templates.filter(
                    structuralproduct_set__classification__technique=technique
                ).distinct()
            except (ValueError, TypeError):
                pass
        
        # Dimension filter
        if dimension := req.get("dimension"):
            if dimension in [choice[0] for choice in AssemblyDimension.choices]:
                user_templates = user_templates.filter(dimension=dimension)
                generic_templates = generic_templates.filter(dimension=dimension)
        
        # Country filter
        if country_id := req.get("country"):
            try:
                user_templates = user_templates.filter(country_id=int(country_id))
                generic_templates = generic_templates.filter(country_id=int(country_id))
            except (ValueError, TypeError):
                pass
        
        # Template type filter
        template_type = req.get("template_type")
        if template_type == "user":
            generic_templates = Assembly.objects.none()  # Empty queryset
        elif template_type == "generic":
            user_templates = Assembly.objects.none()  # Empty queryset
    
    return user_templates.order_by('name'), generic_templates.order_by('name')