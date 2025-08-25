from django.http import JsonResponse
from cookie_consent.models import CookieGroup, Cookie
from cookie_consent.util import get_cookie_value_from_request

# Note: Cookie name must be in snake_case. Otherwise, it does not work.
def get_cookie_groups(request):
    groups_data = []
    
    for group in CookieGroup.objects.all():
        group_data = {
            'id': group.varname,
            'name': group.name,
            'description': group.description,
            'required': group.is_required,
            'enabled': get_cookie_value_from_request(request, group.varname, False)
        }

        cookies = []
        for cookie in Cookie.objects.filter(cookiegroup=group):
            cookie_data = {
                'name': cookie.name,
                'description': cookie.description,
            }
            cookies.append(cookie_data)
        
        group_data['cookies'] = cookies
        groups_data.append(group_data)
    
    return JsonResponse({'groups': groups_data})