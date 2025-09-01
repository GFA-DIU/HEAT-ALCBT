from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Load Global country option for EPDs that are used across multiple countries"

    def handle(self, *args, **options):
        try:
            self.stdout.write('Loading Global country fixture...')
            call_command('loaddata', 'pages/fixtures/global_country.json')
            self.stdout.write(
                self.style.SUCCESS('Successfully loaded Global country fixture')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to load Global country fixture: {e}')
            )