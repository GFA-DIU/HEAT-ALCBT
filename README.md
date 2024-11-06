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
```
$ python -m venv .venv
$ source .venv/bin/activate

(.venv) $ pip install -r requirements.txt
(.venv) $ python manage.py migrate
(.venv) $ python manage.py createsuperuser
(.venv) $ python manage.py runserver
(.venv) $ python manage.py cities_light  # populate with city info
# Load the site at http://127.0.0.1:8000
```

The app is based on the [djangox](https://github.com/wsvincent/djangox/assets/766418/a73ea730-a7b4-4e53-bf51-aa68f6816d6a) template, where additional information can be found.

## Additional resources

### HTMX in Django
 - this triggered the decision [Modern JavaScript for Django Developers: Part 5](https://www.saaspegasus.com/guides/modern-javascript-for-django-developers/htmx-alpine/#talking-to-your-django-backend-without-a-full-page-reload-with-htmx)
 - opinionated [django-htmx-fun](https://github.com/guettli/django-htmx-fun/tree/main)
 - opinionated [django-htmx-patterns](https://github.com/spookylukey/django-htmx-patterns/tree/master)
 - resource list by  [htmx.org](https://htmx.org/server-examples/)


### Django
 - [learndjango.com](https://learndjango.com/search/results/?q=view)