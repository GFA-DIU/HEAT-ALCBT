import json
import logging

logger = logging.getLogger(__name__)


class CookieConsentMiddleware:
    # Middleware to handle cookie consent and conditionally disable tracking services
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check cookie consent before processing request
        self.check_cookie_consent(request)
        
        response = self.get_response(request)
        return response

    def check_cookie_consent(self, request):
        """
        Check if user has given consent for analytics cookies
        If not, disable New Relic monitoring for this request
        """
        consent_cookie = request.COOKIES.get('cookie_consent')
        analytics_consent = False
        
        if consent_cookie:
            try:
                consent_data = json.loads(consent_cookie)
                analytics_consent = consent_data.get('analytics', False)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Store consent status in request for use by other components
        request.analytics_consent = analytics_consent
        request.marketing_consent = False
        
        if consent_cookie:
            try:
                consent_data = json.loads(consent_cookie)
                request.marketing_consent = consent_data.get('marketing', False)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # If no analytics consent and New Relic is available, try to disable it
        if not analytics_consent:
            try:
                import newrelic.agent
                newrelic.agent.ignore_transaction()
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"Could not disable New Relic: {e}")


class ConditionalNewRelicMiddleware:
    # Middleware to conditionally load New Relic based on cookie consent
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.newrelic_available = False

        try:
            import newrelic.agent
            self.newrelic_available = True
        except ImportError:
            pass

    def __call__(self, request):
        # Check consent and conditionally apply New Relic
        if self.newrelic_available and not self.has_analytics_consent(request):
            try:
                import newrelic.agent
                newrelic.agent.ignore_transaction()
            except Exception as e:
                logger.warning(f"Could not disable New Relic transaction: {e}")
        
        response = self.get_response(request)
        return response

    def has_analytics_consent(self, request):
        consent_cookie = request.COOKIES.get('cookie_consent')
        if not consent_cookie:
            return False
        
        try:
            consent_data = json.loads(consent_cookie)
            return consent_data.get('analytics', False)
        except (json.JSONDecodeError, TypeError):
            return False