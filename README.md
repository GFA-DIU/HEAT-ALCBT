# HEAT Building Life Cycle Assessment


----

## Table of Contents
* **[Installation](#installation)**
  * [Pip](#pip)
  * [Docker](#docker)
* [Next Steps](#next-steps)
* [Contributing](#contributing)
* [Support](#support)
* [License](#license)

----

## Get started

### Select DB configuration
You can chose to use a PostgreSQL DB or a SQLite3 DB by changing the configuration of DATABASES in the `settings.py` file. 

When using the PostgreSQL DB, it is required to setup `POSTGRES_USER`, `POSTGRES_PASSWD`, `POSTGRES_DB` variables in a `.env` file.
It is also required to create a file `.pg_service.conf` in your root directory (`~`) if you are using linux or in the ` %APPDATA%\postgresql` if you are using windows (**Note**: See https://www.postgresql.org/docs/current/libpq-pgservice.html) with the following content:

```
[pg_service]
host=localhost
user=POSTGRES_USER
dbname=POSTGRES_DB
port=5432
```
**Note**: Replace `POSTGRES_USER` and `POSTGRES_DB` with your own values.

Finally create a new file named `.pg_password` in the secrets folder with the following content:
```
localhost:5432:POSTGRES_USER:POSTGRES_DB:POSTGRES_PASSWD
```
**Note**: Replace `POSTGRES_USER`, `POSTGRES_PASSWD` and `POSTGRES_DB` with your own values.

### Installation
```Bash
$ python -m venv .venv
$ source .venv/bin/activate

(.venv) $ pip install -r requirements.txt
(.venv) $ python manage.py migrate
(.venv) $ python manage.py createsuperuser
(.venv) $ python manage.py cities_light
(.venv) $ python manage.py runserver
# Load the site at http://127.0.0.1:8000
```

To load the EPD data from Ökobaudat:
```Bash
(.venv) $ python manage.py load_oekobaudat_epds
```
**Note**: The Ecoplatform Loader expects an API Token `ECO_PLATFORM_TOKEN` in an `.env` file.


To load the EPD data from Ecoplatform:
```
(.venv) $ python manage.py load_ecoplatform_epds
```

If `cities_light` is not being loaded, try:
```Bash
(.venv) $ python manage.py cities_light --force-import-all
```

### Info
The basic `BuildingCategory` and `MaterialCategory` data is automatically imported through the migrations.



### Background Info

The app is based on the [djangox](https://github.com/wsvincent/djangox/assets/766418/a73ea730-a7b4-4e53-bf51-aa68f6816d6a) template, where additional information can be found.

## Additional resources

### HTMX in Django
 - this triggered the decision [Modern JavaScript for Django Developers: Part 5](https://www.saaspegasus.com/guides/modern-javascript-for-django-developers/htmx-alpine/#talking-to-your-django-backend-without-a-full-page-reload-with-htmx)
 - opinionated [django-htmx-fun](https://github.com/guettli/django-htmx-fun/tree/main)
 - opinionated [django-htmx-patterns](https://github.com/spookylukey/django-htmx-patterns/tree/master)
 - resource list by  [htmx.org](https://htmx.org/server-examples/)


### Django
 - [learndjango.com](https://learndjango.com/search/results/?q=view)