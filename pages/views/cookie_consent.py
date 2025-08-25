import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from cookie_consent.models import CookieGroup, Cookie
from cookie_consent.util import accept_cookies, decline_cookies, get_cookie_value_from_request


@require_http_methods(["GET", "POST"])
def cookie_consent_status(request):
    if request.method == "GET":
        status = {}
        
        # Get all cookie groups
        for group in CookieGroup.objects.all():
            group_accepted = get_cookie_value_from_request(request, group.varname, False)
            status[group.varname] = group_accepted
        
        return JsonResponse(status)
    
    elif request.method == "POST":
        data = json.loads(request.body)
        action = data.get('action')
        
        response = JsonResponse({"status": "success"})
        
        if action == "accept_all":
            # Accept all cookies
            for group in CookieGroup.objects.all():
                accept_cookies(response, group.varname)
        
        elif action == "decline_optional":
            # Accept only essential cookies, decline others
            for group in CookieGroup.objects.all():
                if group.varname == 'essential':
                    accept_cookies(response, group.varname)
                else:
                    decline_cookies(response, group.varname)
        
        elif action == "save_custom":
            settings = data.get('settings', {})
            for group in CookieGroup.objects.all():
                group_setting = settings.get(group.varname, False)
                if group_setting:
                    accept_cookies(response, group.varname)
                else:
                    decline_cookies(response, group.varname)
        
        return response


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