"""No template may use a {# #} comment that spans more than one line.

Django's `{# #}` comments only reach the end of the line. A block written
across several lines is therefore a comment on its first line and ordinary
text on the rest, which renders straight onto the page. It has happened twice
on the Savings tab and once on the cooling form, each time shipping a
paragraph of source commentary into the UI where a user could read it.

Use `{% comment %} ... {% endcomment %}` for anything longer than one line.
"""
import os
import re

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "templates",
)


def _offenders():
    bad = []
    for root, _, files in os.walk(TEMPLATES_DIR):
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if "{#" in line and "#}" not in line:
                        bad.append("%s:%d" % (os.path.relpath(path, TEMPLATES_DIR), n))
    return bad


def test_no_multiline_hash_comments():
    offenders = _offenders()
    assert not offenders, (
        "{# #} only comments its own line; these will render to the page as "
        "text. Use {% comment %}...{% endcomment %}:\n  " + "\n  ".join(offenders)
    )
