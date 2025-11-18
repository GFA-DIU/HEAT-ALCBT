# Localization Guide

This guide explains how to work with translations in the HEAT-ALCBT project using Django's internationalization (i18n) framework.

## Overview

The project supports multiple languages:
- English (en)
- Vietnamese (vi)

Translation files are managed using GNU gettext `.po` files, which can be edited using free online editors like:
- https://pofile.net/free-po-editor (recommended)
- https://localise.biz/free/poeditor

## Setup

### Prerequisites

You need GNU gettext tools installed to generate translation files:

**Windows:**
- Download from https://mlocati.github.io/articles/gettext-iconv-windows.html
- Add to your system PATH

**Linux:**
```bash
apt-get install gettext
```

**Mac:**
```bash
brew install gettext
```

## Configuration

The project is already configured for i18n in `django_project/settings.py`:

- `USE_I18N = True` - Enables translation system
- `LANGUAGE_CODE = "en-us"` - Default language
- `LANGUAGES` - List of supported languages
- `LOCALE_PATHS` - Location of translation files (`locale/`)
- `LocaleMiddleware` - Detects user's preferred language

Language switching is available at `/i18n/set_language/`.

## Workflow

### 1. Mark Strings for Translation

#### In Python Code

Use `gettext()` or its alias `_()`:

```python
from django.utils.translation import gettext as _

message = _("Welcome to HEAT-ALCBT")
```

For strings evaluated at module load time (model fields, form labels), use `gettext_lazy()`:

```python
from django.utils.translation import gettext_lazy as _

class Building(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name=_("Building Name"),
        help_text=_("Enter the name of the building")
    )

    class Meta:
        verbose_name = _("Building")
        verbose_name_plural = _("Buildings")
```

For pluralization:

```python
from django.utils.translation import ngettext

message = ngettext(
    "%(count)d building analyzed",
    "%(count)d buildings analyzed",
    count
) % {"count": count}
```

#### In Templates

Load the i18n template tags:

```django
{% load i18n %}
```

For simple strings:

```django
<h1>{% translate "Welcome" %}</h1>
```

For strings with variables:

```django
{% blocktranslate with name=building.name %}
Building: {{ name }}
{% endblocktranslate %}
```

For pluralization:

```django
{% blocktranslate count counter=buildings|length %}
{{ counter }} building
{% plural %}
{{ counter }} buildings
{% endblocktranslate %}
```

Add translator comments to provide context:

```django
{# Translators: Button label for saving building data #}
<button>{% translate "Save" %}</button>
```

### 2. Generate Translation Files

After marking strings for translation, generate `.po` files:

```bash
# Generate for all languages
python manage.py makemessages -l en
python manage.py makemessages -l vi

# For JavaScript files
python manage.py makemessages -d djangojs -l en
python manage.py makemessages -d djangojs -l vi

# Generate for all configured languages at once
python manage.py makemessages --all
```

This creates/updates files in:
- `locale/en/LC_MESSAGES/django.po`
- `locale/vi/LC_MESSAGES/django.po`

### 3. Translate Strings

Edit the `.po` files using:

1. **Online editors** (recommended for non-technical translators):
   - Upload the `.po` file to https://pofile.net/free-po-editor
   - Edit translations
   - Download the updated file

2. **Text editor**:
   - Open `locale/vi/LC_MESSAGES/django.po`
   - Find entries like:
     ```
     msgid "Welcome to HEAT-ALCBT"
     msgstr ""
     ```
   - Add translation:
     ```
     msgid "Welcome to HEAT-ALCBT"
     msgstr "Chào mừng đến với HEAT-ALCBT"
     ```

**Important:** Never modify `msgid` values - only edit `msgstr` values.

### 4. Compile Translations

After editing `.po` files, compile them to binary `.mo` files:

```bash
python manage.py compilemessages
```

This creates `.mo` files that Django uses at runtime.

### 5. Test Translations

1. Start the development server:
   ```bash
   python manage.py runserver
   ```

2. Change language using:
   - Browser language preferences (detected automatically)
   - Language switcher in the UI (if implemented)
   - Manually: POST to `/i18n/set_language/` with `language` parameter

## Best Practices

### DO:

- Use named placeholders: `_("Welcome %(name)s") % {"name": user.name}`
- Use `gettext_lazy()` for model fields and class attributes
- Add translator comments for ambiguous strings
- Keep translation strings concise and complete sentences
- Use consistent terminology across the application

### DON'T:

- Split sentences: `_("Welcome") + " " + _("to our site")`
- Use f-strings with immediate evaluation: `_(f"Welcome {name}")`
- Concatenate translated strings
- Translate the same English string to different meanings (use `pgettext()` for context)

### Handling Variables

Use named string interpolation:

```python
# Good
message = _("%(count)d buildings in %(city)s") % {
    "count": building_count,
    "city": city_name
}

# Bad - positional arguments make translation difficult
message = _("%d buildings in %s") % (building_count, city_name)
```

### Context for Ambiguous Strings

Use `pgettext()` when the same English word has different meanings:

```python
from django.utils.translation import pgettext

# "May" as month
month = pgettext("month name", "May")

# "May" as permission
permission = pgettext("permission", "May")
```

## File Structure

```
project_root/
├── locale/
│   ├── en/
│   │   └── LC_MESSAGES/
│   │       ├── django.po      # English translations
│   │       ├── django.mo      # Compiled (auto-generated)
│   │       ├── djangojs.po    # JavaScript translations
│   │       └── djangojs.mo    # Compiled JS (auto-generated)
│   └── vi/
│       └── LC_MESSAGES/
│           ├── django.po      # Vietnamese translations
│           ├── django.mo      # Compiled (auto-generated)
│           ├── djangojs.po    # JavaScript translations
│           └── djangojs.mo    # Compiled JS (auto-generated)
```

**Note:** Never commit `.mo` files to version control - they are auto-generated.

## Language Detection Order

Django's `LocaleMiddleware` detects language preference in this order:

1. URL prefix (if using `i18n_patterns()`)
2. Session/cookie (`django_language`)
3. Browser's `Accept-Language` header
4. `LANGUAGE_CODE` setting (fallback)

## Common Issues

### makemessages fails with "Can't find msguniq"

**Solution:** Install GNU gettext tools (see Prerequisites section)

### Translations not appearing

**Checklist:**
1. Did you compile messages? Run `python manage.py compilemessages`
2. Is `USE_I18N = True` in settings?
3. Is `LocaleMiddleware` in `MIDDLEWARE`?
4. Did you restart the development server?
5. Is your browser sending the correct `Accept-Language` header?

### New strings not extracted

**Solution:**
- Make sure strings are wrapped in `gettext()` or `{% translate %}`
- Re-run `python manage.py makemessages -l vi`
- Check that files aren't ignored by `.gitignore`

### Strings appear in English despite translation

**Causes:**
- `.mo` file not compiled - run `compilemessages`
- `msgstr` is empty in `.po` file
- Using f-strings incorrectly: `_(f"text {var}")` evaluates before translation

## Resources

- [Django i18n documentation](https://docs.djangoproject.com/en/5.2/topics/i18n/translation/)
- [GNU gettext manual](https://www.gnu.org/software/gettext/manual/)
- [Free .po file editor](https://pofile.net/free-po-editor)
- [Lokalise Django guide](https://lokalise.com/blog/django-i18n-beginners-guide/)

## Adding a New Language

1. Add language to `LANGUAGES` in `settings.py`:
   ```python
   LANGUAGES = [
       ('en', 'English'),
       ('vi', 'Vietnamese'),
       ('th', 'Thai'),  # New language
   ]
   ```

2. Create translation files:
   ```bash
   python manage.py makemessages -l th
   ```

3. Translate strings in `locale/th/LC_MESSAGES/django.po`

4. Compile translations:
   ```bash
   python manage.py compilemessages
   ```

5. Update `cities_light` configuration if needed:
   ```python
   CITIES_LIGHT_TRANSLATION_LANGUAGES = ["en", "abbr", "th"]
   ```