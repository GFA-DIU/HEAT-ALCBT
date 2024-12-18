import logging
from django.db import models
from django.utils.translation import gettext as _
from cities_light.models import Country, City
from geopy.geocoders import Nominatim
from accounts.models import CustomUser

logger = logging.getLogger(__name__)

class BaseModel(models.Model):
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
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    street = models.CharField(_("Street"), max_length=255, null=True, blank=True)
    number = models.IntegerField(_("Number"), null=True, blank=True)
    zip = models.IntegerField(_("ZIP"), null=True, blank=True)

    # Longitude & latitude
    longitude = models.FloatField(_("Longitude"), null=True, blank=True)
    latitude = models.FloatField(_("Latitude"), null=True, blank=True)

    def address(self):
        address_string = [str(self.number)] if  self.number else []
        if self.street:
            address_string.append(self.street)
        if self.zip:
            address_string.append(str(self.zip))
        address_string.append(str(self.city or self.country))
        return ", ".join(address_string)

    def save(self, *args, **kwargs):
        self.longitude, self.latitude = None, None
        if self.city: 
            if self.number and self.street and self.zip:
                self.calculate_lon_lat()
            else:
                self.longitude, self.latitude = self.city.longitude, self.city.latitude
        super().save(*args, **kwargs)

    def calculate_lon_lat(self):
        geolocator = Nominatim(
            user_agent="Beat/1.0 (https://d2innovate.eu/; ramon.zalabardo@gfa-group.de)"
        )
        try:
            location = geolocator.geocode(self.address())
            self.longitude, self.latitude = location.longitude, location.latitude
        except Exception as error:
            logger.error(error)
            self.longitude, self.latitude = self.city.longitude, self.city.latitude
    class Meta:
        abstract = True  # This ensures it won't create its own table.
