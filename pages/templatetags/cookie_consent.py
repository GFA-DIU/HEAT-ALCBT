import json
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def has_cookie_consent(context, category):
    """
    Check if user has given consent for a specific cookie category
    Categories: necessary, analytics, marketing
    """
    request = context.get('request')
    if not request:
        return False
    
    consent_cookie = request.COOKIES.get('cookie_consent')
    if not consent_cookie:
        return False
    
    try:
        consent_data = json.loads(consent_cookie)
        return consent_data.get(category, False)
    except (json.JSONDecodeError, TypeError):
        return False


@register.simple_tag(takes_context=True)
def cookie_consent_status(context):
    # Get the full cookie consent status
    request = context.get('request')
    if not request:
        return None
    
    consent_cookie = request.COOKIES.get('cookie_consent')
    if not consent_cookie:
        return None
    
    try:
        return json.loads(consent_cookie)
    except (json.JSONDecodeError, TypeError):
        return None


@register.inclusion_tag('cookie_consent/banner.html', takes_context=True)
def cookie_consent_banner(context):
    # Display cookie consent banner if consent hasn't been given
    request = context.get('request')
    show_banner = True
    
    if request:
        consent_cookie = request.COOKIES.get('cookie_consent')
        if consent_cookie:
            try:
                consent_data = json.loads(consent_cookie)
                if consent_data.get('timestamp'):
                    show_banner = False
            except (json.JSONDecodeError, TypeError):
                pass
    
    return {
        'show_banner': show_banner,
        'request': request
    }


@register.inclusion_tag('cookie_consent/settings_modal.html', takes_context=True)
def cookie_settings_modal(context):
    request = context.get('request')
    consent_data = {
        'necessary': True,
        'analytics': False,
        'marketing': False
    }
    
    if request:
        consent_cookie = request.COOKIES.get('cookie_consent')
        if consent_cookie:
            try:
                stored_consent = json.loads(consent_cookie)
                consent_data.update(stored_consent)
            except (json.JSONDecodeError, TypeError):
                pass
    
    return {
        'consent_data': consent_data,
        'request': request
    }