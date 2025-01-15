import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.validators import UnicodeUsernameValidator

from encrypted_model_fields.fields import EncryptedEmailField, EncryptedCharField
from cities_light.models import Country, City

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        "username",
        max_length=150,
        unique=True,
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
        validators=[username_validator],
        error_messages={
            "unique": "A user with that username already exists.",
        },
    )
    # Due to the nature of the encrypted data, filtering by values contained in encrypted fields won't work properly. Sorting is also not supported.
    # Therefore any sorting and/or filtering must be done through code and not Django queries.
    first_name = EncryptedCharField("first name", max_length=150, blank=True)
    last_name = EncryptedCharField("last name", max_length=150, blank=True)
    email = EncryptedEmailField("email address", blank=True, unique=True)
    phone = EncryptedCharField("mobile phone", max_length=13)

    def __str__(self):
        return self.email


class UserProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
    )
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)

    def clean(self):
        # Custom validation logic
        if self.city and self.country:
            if self.city.country != self.country:
                raise ValidationError("The selected city does not match the selected country.")

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


@receiver(post_save, sender=CustomUser)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    UserProfile.objects.get_or_create(user=instance)
