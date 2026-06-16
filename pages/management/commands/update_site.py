from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


def _clean_domain(raw):
    """Strip protocol and trailing slash — Sites framework stores bare domain only."""
    domain = raw.strip()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.rstrip("/")


class Command(BaseCommand):
    help = "Update the Django Sites framework record from SITE_DOMAIN and SITE_NAME env vars"

    def handle(self, *args, **options):
        site = Site.objects.filter(pk=settings.SITE_ID).first()
        if not site:
            self.stderr.write(f"No Site with pk={settings.SITE_ID} found.")
            return
        old = f"{site.domain} / {site.name}"
        site.domain = _clean_domain(settings.SITE_DOMAIN)
        site.name = settings.SITE_NAME
        site.save()
        self.stdout.write(f"Updated: {old} → {site.domain} / {site.name}")
