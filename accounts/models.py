import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from cities_light.models import Country, Region, City
from encrypted_json_fields.fields import EncryptedEmailField
from django.forms.models import model_to_dict



class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = EncryptedEmailField(unique=True, blank=False, null=False)

    def __str__(self):
        return self.email

     def to_json(self):
        json_data = model_to_dict(self)
        return json_data


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
    class Role(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        DATA_MANAGER = "data_manager", "Data Manager"
        ADMIN = "admin", "Admin"
        SUPERADMIN = "superadmin", "Superadmin"

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
    )
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    region = models.ForeignKey(
        CustomRegion, on_delete=models.SET_NULL, null=True, blank=True
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
    profile, _ = UserProfile.objects.get_or_create(user=instance)
    # Keep role in sync with Django's superuser/staff flags
    if instance.is_superuser and profile.role != UserProfile.Role.SUPERADMIN:
        profile.role = UserProfile.Role.SUPERADMIN
        profile.save(update_fields=["role"])
    elif instance.is_staff and not instance.is_superuser and profile.role not in (
        UserProfile.Role.ADMIN, UserProfile.Role.SUPERADMIN
    ):
        profile.role = UserProfile.Role.ADMIN
        profile.save(update_fields=["role"])
