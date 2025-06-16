# HEAT Building Life Cycle Assessment

---

## Table of Contents

- **[Get Started](#get-started)**

  - [Docker Database](#docker-database)
  - [Installation](#installation)
  - [Load EPD Data](#load-epd-data)
  - [PostGres](#postgres)

- [Contribute](#contribute)
  - [Unit Tests](#unit-tests)
  - [Deploy to Heroku](#deploy-to-heroku)
- [Support](#support)
- [License](#license)

---

## Get started

In local development we use a dockerized postgres instance.

**Note:** The Django config automatically checks if this is the production environment or not.

### Docker Database

Start the postgres DB

```Bash
$ docker compose up db
```

### Installation

Next, start the Django application

```Bash
$ python -m venv .venv
$ source .venv/bin/activate

(.venv) $ pip install -r requirements.dev.txt
(.venv) $ python manage.py migrate
(.venv) $ python manage.py createsuperuser
(.venv) $ python manage.py create_email_address # Creates an email_address for the superuser (Needed for all_auth to work)
(.venv) $ python manage.py cities_light
(.venv) $ python manage.py runserver
# Load the site at http://127.0.0.1:8000
```

The basic `BuildingCategory` and `MaterialCategory` data is automatically imported through the migrations.

If `cities_light` is not being loaded, try:

```Bash
(.venv) $ python manage.py cities_light --force-import-all
```

#### Load EPD Data

To load the EPD data from Ökobaudat:

```Bash
(.venv) $ python manage.py load_oekobaudat_epds
```

**Note**: The Ecoplatform Loader expects an API Token `ECO_PLATFORM_TOKEN` in an `.env` file.

To load the EPD data from Ecoplatform:

```Bash
(.venv) $ python manage.py load_ecoplatform_epds
```

To load all generic EPDs found under `pages/data`:
```Bash
(.venv) $ python manage.py load_local_epds
```

To load a specific set of local EPDs, name the relevant file with one of the keynames found in `pages/management/commands/load_local_epds.py`. See for example below:

```Bash
(.venv) $ python manage.py load_local_epds --file EDGE_HANDBOOK_EPDs
```

### Loading Labels

Load EPD (manual) label mappings from label file
```Bash
(.venv) $ python manage.py map_GCCA_EPD_label
```

### PostGres

To inspect the data tables in postgres instead of Django admin

```Bash
$ pgcli -h localhost -p 5432 -U postgres -d postgres
```

## Contribute

Follow the installation steps [above](#installation).

### Deploy to Heroku

To deploy to the production server you need to be added to the repository with the relevant roles. Once you obtain an authentication token, you can contribute like this through the Heroku CLI.

```Bash
$ heroku login -i
$ git push heroku main
```

### Unit Tests

To execute Unit tests, run

```Bash
(.venv) $ pytest
```

## Support

For support, please reach out to the maintainers or [kontakt@heat-international.de](mailto:kontakt@heat-international.de).

## License
