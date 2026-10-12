"""The settings module must import cleanly on the production code path.

PR #593's first deploy was rejected by Heroku because settings.py read the
bare name DEBUG at module level, and DEBUG was only assigned inside
`if not IS_HEROKU_APP:`. On a dyno the name did not exist, collectstatic
raised NameError, and the build failed.

Nothing in the rest of the suite can catch that. Every local run and every
test takes the `not IS_HEROKU_APP` branch, so the production half of each
conditional in settings.py is never executed. These tests run a real
subprocess with DYNO set, which is the only thing that flips IS_HEROKU_APP.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _run(*args):
    """Run manage.py as Heroku would: DYNO set, CI absent."""
    env = dict(os.environ)
    env["DYNO"] = "web.1"
    env.pop("CI", None)
    # Django reads this to decide the toolbar; prove it is not consulted
    # before DEBUG exists.
    env.pop("ENABLE_DEBUG_TOOLBAR", None)
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=300)


def test_settings_import_on_a_dyno():
    """`manage.py check` must not raise while importing settings."""
    r = _run("check")
    assert "NameError" not in r.stderr, r.stderr[-2000:]
    assert r.returncode == 0, r.stderr[-2000:]


def test_collectstatic_on_a_dyno():
    """This is the exact command the Heroku Python buildpack runs."""
    r = _run("collectstatic", "--noinput", "--dry-run")
    assert r.returncode == 0, r.stderr[-2000:]


def test_debug_is_false_and_defined_on_a_dyno():
    """DEBUG must be a real name on both branches, and False in production."""
    r = _run("shell", "-c",
             "from django.conf import settings;"
             "import django_project.settings as s;"
             "print('DEBUG_ATTR', settings.DEBUG);"
             "print('DEBUG_NAME', s.DEBUG);"
             "print('TOOLBAR', s.ENABLE_DEBUG_TOOLBAR)")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "DEBUG_ATTR False" in r.stdout, r.stdout
    assert "DEBUG_NAME False" in r.stdout, r.stdout
    assert "TOOLBAR False" in r.stdout, r.stdout


def test_debug_toolbar_is_not_installed_in_production():
    r = _run("shell", "-c",
             "import django_project.settings as s;"
             "print('HAS_TOOLBAR', 'debug_toolbar' in s.INSTALLED_APPS)")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "HAS_TOOLBAR False" in r.stdout, r.stdout
