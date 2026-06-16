from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Update the Django Sites framework record from SITE_DOMAIN and SITE_NAME env vars"

    def handle(self, *args, **options):
        site = Site.objects.filter(pk=settings.SITE_ID).first()
        if not site:
            self.stderr.write(f"No Site with pk={settings.SITE_ID} found.")
            return
        old = f"{site.domain} / {site.name}"
        site.domain = settings.SITE_DOMAIN
        site.name = settings.SITE_NAME
        site.save()
        self.stdout.write(f"Updated: {old} → {site.domain} / {site.name}")
