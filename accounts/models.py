import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from cities_light.models import Country, Region, City
from encrypted_json_fields.fields import EncryptedEmailField


class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = EncryptedEmailField(unique=True, blank=False, null=False)

    def __str__(self):
        return self.email


class CustomCity(City):
    class Meta:
        proxy = True

    def __str__(self):
        return self.name  # Show only city name


class CustomRegion(Region):
    class Meta:
        proxy = True

    def __str__(self):
        return self.name  # Show only city name


class UserProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
    )
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    city = models.ForeignKey(
        CustomCity, on_delete=models.SET_NULL, null=True, blank=True
    )    
    consent_flag = models.BooleanField(
        default=True,
        verbose_name="Share with BEAT tool maintainers",
    )
    
    def clean(self):
        # Custom validation logic
        if self.city and self.country:
            if self.city.country != self.country:
                raise ValidationError(
                    "The selected city does not match the selected country."
                )

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


@receiver(post_save, sender=CustomUser)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    UserProfile.objects.get_or_create(user=instance)
