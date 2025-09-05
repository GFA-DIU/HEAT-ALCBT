import os
import logging
import uuid

from django.db import models
from django.utils.translation import gettext as _
from cities_light.models import Country
from geopy.geocoders import Nominatim
from accounts.models import CustomUser, CustomCity, CustomRegion

NOMINATIM_AGENT_STRING = os.environ.get("NOMINATIM_AGENT_STRING")
logger = logging.getLogger(__name__)


class ALCBTCountryManager:
    @staticmethod
    def get_alcbt_countries():
        ALCBT_COUNTRY_CODES = ["ID", "TH", "VN", "KH", "IN"]
        return Country.objects.filter(code2__in=ALCBT_COUNTRY_CODES).order_by("name")
    
    @staticmethod
    def get_all_countries():
        return Country.objects.all().order_by("name")


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)
    public = models.BooleanField(
        _("Public"), help_text=_("Is it visible to all roles"), default=False
    )
    draft = models.BooleanField(
        _("Draft"), help_text=_("Is it still a draft"), default=False
    )

    class Meta:
        abstract = True  # This ensures it won't create its own table.


class BaseGeoModel(models.Model):
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    region = models.ForeignKey(CustomRegion, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(CustomCity, on_delete=models.SET_NULL, null=True, blank=True)
    street = models.CharField(_("Street"), max_length=255, null=True, blank=True)
    number = models.IntegerField(_("Number"), null=True, blank=True)
    zip = models.IntegerField(_("ZIP"), null=True, blank=True)

    # Longitude & latitude
    longitude = models.FloatField(_("Longitude"), null=True, blank=True)
    latitude = models.FloatField(_("Latitude"), null=True, blank=True)

    def address(self):
        address_string = [str(self.number)] if self.number else []
        if self.street:
            address_string.append(self.street)
        if self.zip:
            address_string.append(str(self.zip))
        address_string.append(str(self.city or self.country))
        return ", ".join(address_string)

    def save(self, *args, **kwargs):
        if self.longitude and self.latitude:
            pass

        elif self.number and self.street and self.zip:
            self.calculate_lon_lat()

        elif self.city:
            self.longitude, self.latitude = self.city.longitude, self.city.latitude

        else:
            self.longitude, self.latitude = None, None
        super().save(*args, **kwargs)

    def calculate_lon_lat(self):
        try:
            geolocator = Nominatim(user_agent=NOMINATIM_AGENT_STRING)
            location = geolocator.geocode(self.address())
            self.longitude, self.latitude = location.longitude, location.latitude
        except Exception as error:
            logger.error(error)
            if self.city:
                self.longitude, self.latitude = self.city.longitude, self.city.latitude

    class Meta:
        abstract = True  # This ensures it won't create its own table.
