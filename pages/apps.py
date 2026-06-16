from django.apps import AppConfig
from django.db.models.signals import post_migrate


def update_site_domain(sender, **kwargs):
    """Auto-update the Django Sites framework record after every migration."""
    from django.conf import settings
    try:
        from django.contrib.sites.models import Site
        site = Site.objects.filter(pk=settings.SITE_ID).first()
        if site and (site.domain != settings.SITE_DOMAIN or site.name != settings.SITE_NAME):
            site.domain = settings.SITE_DOMAIN
            site.name = settings.SITE_NAME
            site.save()
    except Exception:
        pass  # Gracefully skip if the sites table doesn't exist yet (first migrate)


class PagesConfig(AppConfig):
    name = "pages"

    def ready(self):
        import pages.signals  # noqa: F401
        post_migrate.connect(update_site_domain, sender=self)
