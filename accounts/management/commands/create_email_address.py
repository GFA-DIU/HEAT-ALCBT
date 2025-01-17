from allauth.account.models import EmailAddress
from accounts.models import CustomUser
from django.db import transaction
from django.core.management.base import BaseCommand
from django.contrib.auth.management.commands.createsuperuser import Command as CreateSuperuserCommand

class Command(BaseCommand):
    help = 'Custom command to create EmailAddress for new superusers'

    def handle(self, *args, **options):
      # Get all superusers without a related EmailAddress
      superusers_without_email = CustomUser.objects.filter(is_superuser=True).exclude(
          emailaddress__isnull=False
      )

      # Prepare a list of EmailAddress instances to create
      email_addresses = [
          EmailAddress(user=superuser, email=superuser.email, verified=True, primary=True)
          for superuser in superusers_without_email
      ]

      # Use bulk_create to efficiently create all records in one query
      with transaction.atomic():
          EmailAddress.objects.bulk_create(email_addresses)
