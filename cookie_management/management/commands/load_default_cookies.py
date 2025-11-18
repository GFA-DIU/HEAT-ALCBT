from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Load default cookie groups and cookies'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Loading default cookie groups and cookies...'))
        
        try:
            call_command('loaddata', 'initial_cookie_groups.json')
            self.stdout.write(
                self.style.SUCCESS(
                    'Successfully loaded default cookie groups and cookies'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error loading default cookie groups: {e}'
                )
            )