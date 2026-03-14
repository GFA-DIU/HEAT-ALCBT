import uuid

from cities_light.models import Country
from django.db import models

from accounts.models import CustomUser, CustomCity


class Organisation(models.Model):
    class Industry(models.TextChoices):
        CONSTRUCTION = "construction", "Construction"
        MANUFACTURING = "manufacturing", "Manufacturing"
        TECHNOLOGY = "technology", "Technology"
        FINANCE = "finance", "Finance"
        HEALTHCARE = "healthcare", "Healthcare"
        EDUCATION = "education", "Education"
        REAL_ESTATE = "real_estate", "Real Estate"
        ENERGY = "energy", "Energy"
        RETAIL = "retail", "Retail"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    industry = models.CharField(max_length=50, choices=Industry.choices)
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="organisations",
    )
    city = models.ForeignKey(
        CustomCity, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="organisations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


class OrganisationMembership(models.Model):
    """Tracks which users belong to which organisations and with what role."""

    class MemberRole(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        DATA_MANAGER = "data_manager", "Data Manager"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="organisation_memberships"
    )
    role = models.CharField(max_length=20, choices=MemberRole.choices, default=MemberRole.VIEWER)
    countries = models.ManyToManyField(
        Country,
        blank=True,
        related_name="organisation_memberships",
        help_text="Countries this member manages within the organisation.",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organisation", "user")
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user} @ {self.organisation} ({self.role})"