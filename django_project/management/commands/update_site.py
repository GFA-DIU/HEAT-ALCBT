from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Update Site domain and name from environment variables"

    def handle(self, *args, **options):
        """Update the Site object with domain and name from settings."""
        try:
            site = Site.objects.get(pk=settings.SITE_ID)
            old_domain = site.domain
            old_name = site.name

            site.domain = settings.SITE_DOMAIN
            site.name = settings.SITE_NAME
            site.save()

            if old_domain != site.domain or old_name != site.name:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated Site from '{old_name}' ({old_domain}) "
                        f"to '{site.name}' ({site.domain})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Site already configured: '{site.name}' ({site.domain})"
                    )
                )
        except Site.DoesNotExist:
            # Create the site if it doesn't exist
            site = Site.objects.create(
                pk=settings.SITE_ID,
                domain=settings.SITE_DOMAIN,
                name=settings.SITE_NAME,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created Site: '{site.name}' ({site.domain})"
                )
            )
