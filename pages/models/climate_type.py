from django.db import models


class ClimateType(models.Model):
    """
    Manageable climate type. Seeded from the original ClimateZone TextChoices
    but stored as a proper model so admins can add, edit and describe them.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def usage_count(self):
        return self.buildings.count()

    @property
    def is_active(self):
        return self.buildings.exists()