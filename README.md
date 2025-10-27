# HEAT Building Life Cycle Assessment

---

## Table of Contents

- **[Get Started](#get-started)**

  - [Docker Database](#docker-database)
  - [Installation](#installation)
  - [Load EPD Data](#load-epd-data)
  - [PostGres](#postgres)

- [Contribute](#contribute)
  - [Deploy to Heroku](#deploy-to-heroku)
  - [Unit Tests](#unit-tests)
  - [Load testing](#load-testing)
- [Support](#support)
- [License](#license)

---

## Get started

In local development we use a dockerized postgres instance.

**Note:** The Django config automatically checks if this is the production environment or not.

### Docker Database

Start the postgres DB

```Bash
docker compose up db
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
(.venv) $ python manage.py load_country_global # Adds a "Global" country option for EPDs
(.venv) $ python manage.py load_default_cookies # Creates the default cookies
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
pgcli -h localhost -p 5432 -U postgres -d postgres
```

To load heroku DB snapshot (custom/tar PostgreSQL), follow these steps:

1. Spin-up the DB and identify the container

```Bash
docker compose up -d db
DB_CID=$(docker compose ps -q db)
echo "$DB_CID"
```

2. Verify snapshot and move into container

```Bash
$ SNAPSHOT=./path/to/snapshot
# custom/tar shows 'PostgreSQL custom database dump' or 'POSIX tar'
$ file "$SNAPSHOT"
$ docker cp "$SNAPSHOT" "$DB_CID":/tmp/snapshot.dump
```

3. Restore custom dump with `pg_restore`

```Bash
# Drop + recreate target DB inside the container (avoid lingering objects)
$ docker exec -i "$DB_CID" bash -lc 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'

# restore from snapshot
$ docker exec -i "$DB_CID" bash -lc 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges -j 4 /tmp/snapshot.dump'
```

4. Smoke test the restore

```Bash
docker exec -it "$DB_CID" psql -U postgres -d postgres -c '\dt'    # list tables
docker exec -it "$DB_CID" psql -U postgres -d postgres -c 'select now();'
```

## Contribute

Follow the installation steps [above](#installation).

### Deploy to Heroku

To deploy to the production server you need to be added to the repository with the relevant roles. Once you obtain an authentication token, you can contribute like this through the Heroku CLI.

```Bash
heroku login -i
git push heroku main
```

For executing any necessary migrations, connect via `SSH` or the Heroku-Webinterface.

For executing scripts not warranting their own command, execute them as follows with `python manage.py shell`:

```Python
with open('path/to/your_script.py') as f:
    exec(f.read())
```

### Unit Tests

To execute Unit tests, run

```Bash
(.venv) $ pytest
```

### Load testing

Execute for production server with the GUI as follows:

```Bash
(.venv) $ locust -f load_testing/locust/locustfile.py --host https://beat-alcbt.gggi.org
```

## Support

For support, please reach out to the maintainers or [kontakt@heat-international.de](mailto:kontakt@heat-international.de).

## License

[Apache 2.0](LICENSE)

The tool was built with the public Django template `wsvincent/lithium`. As requested, the copyright notice is included below:

```Text
djangox: Copyright (c) 2020 William Vincent
django-allauth: Copyright (c) 2010 Raymond Penners and contributors
cookie-cutter-django: Copyright (c) 2013-2020 Daniel Greenfeld

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
```
