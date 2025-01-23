from cities_light.models import City

class CustomCity(City):
    class Meta:
        proxy = True 

    def __str__(self):
        return self.name # Show only city name