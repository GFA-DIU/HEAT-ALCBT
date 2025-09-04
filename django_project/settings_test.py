from .settings import *  # Import all base settings

# Use test database
DATABASES = {
    'default': {
        'ENGINE': os.getenv("PG_ENGINE"),
        'NAME': os.getenv("PG_DB_TEST"),
        'USER': os.getenv("PG_USER"),
        'PASSWORD': os.getenv("PG_PASS"),
        'HOST': os.getenv("PG_HOST"),  # Or your PostgreSQL server IP
        'PORT': os.getenv("PG_PORT"),  # Default PostgreSQL port
    }
}

