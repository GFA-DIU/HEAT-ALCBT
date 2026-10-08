"""Repair EPD source URLs that no longer resolve.

Two separate breakages, both verified over HTTP before this was written.

1. The six official Cambodian cement EPDs
   Their URLs were built from the registration number without stripping the
   programme prefix or the zero padding, so "EPD-IES-0022826" became
   ".../library/epd-0022826". The library slug has no hyphen and no leading
   zeros.

       .../library/epd-0022826   HTTP 404
       .../library/epd22826      HTTP 200

   pages/data/cambodia_official_epds.csv carries the same mistake and is
   corrected separately, so a re-import cannot reintroduce it.

2. 393 records pointing at soda4LCA servers (data.environdec.com,
   epdnorway.lca-data.com, ibudata.lca-data.com and friends)
   The `resource/processes/<uuid>` form is the machine-readable API path and
   returns HTTP 400 to a browser. The human-readable page is `datasetdetail`.

       /resource/datastocks/<ds>/processes/<uuid>?version=V   HTTP 400
       /datasetdetail/process.xhtml?uuid=<uuid>&version=V     HTTP 200

   Note oekobaudat.de uses a similar-looking path under /OEKOBAU.DAT/ which
   does resolve, so it is deliberately left alone.

Every rewritten URL is fetched before it is saved. Anything that does not come
back 200 is left exactly as it was and listed at the end - a broken link is
better than a confidently wrong one.

    python manage.py fix_epd_source_urls --dry-run
    python manage.py fix_epd_source_urls
    python manage.py fix_epd_source_urls --no-verify   # skip the HTTP check
"""
import re
from collections import Counter

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.epd import EPD

requests.packages.urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (BEAT link check)"}

# .../library/epd-0022826  ->  .../library/epd22826
CAMBODIA = re.compile(r"(environdec\.com/library/)epd-0*(\d+)", re.I)

# soda4LCA API path -> the human-readable page. The leading group keeps the
# scheme and host; /OEKOBAU.DAT/ paths do not match because of the `/resource/`
# anchor immediately after the host.
SODA = re.compile(
    r"^(https?://[^/]+)/resource/(?:datastocks/[0-9a-f-]{36}/)?"
    r"processes/([0-9a-f-]{36})(?:\?version=([\d.]+))?",
    re.I,
)


def rewrite(url):
    """Return the repaired URL, or None if this one needs no change."""
    if CAMBODIA.search(url):
        return CAMBODIA.sub(r"\1epd\2", url)
    m = SODA.match(url)
    if m:
        base, uuid, version = m.groups()
        new = "%s/datasetdetail/process.xhtml?uuid=%s" % (base, uuid)
        if version:
            new += "&version=%s" % version
        return new
    return None


class Command(BaseCommand):
    help = "Repair EPD source URLs that return 404/400."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change and roll back.")
        parser.add_argument("--no-verify", action="store_true",
                            help="Skip the HTTP check (offline use).")

    def handle(self, *args, **opts):
        try:
            with transaction.atomic():
                self._run(verify=not opts["no_verify"])
                if opts["dry_run"]:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING("\nDry run - rolled back, nothing written."))
            return
        self.stdout.write(self.style.SUCCESS("\nDone."))

    def _run(self, verify):
        # Group by URL so each distinct link is fetched once, not once per EPD.
        by_url = {}
        for e in EPD.objects.exclude(source__isnull=True).only("id", "source"):
            s = (e.source or "").strip()
            if s.lower().startswith("http"):
                by_url.setdefault(s, []).append(e)

        pending = {u: rewrite(u) for u in by_url}
        pending = {u: n for u, n in pending.items() if n and n != u}
        affected = sum(len(by_url[u]) for u in pending)
        self.stdout.write("distinct URLs needing repair: %d  (covering %d EPDs)"
                          % (len(pending), affected))

        checked, skipped = {}, []
        if verify:
            self.stdout.write("verifying each replacement over HTTP...")
            for old, new in pending.items():
                try:
                    r = requests.get(new, headers=HEADERS, timeout=45, verify=False)
                    ok = r.status_code == 200 and len(r.content) > 2000
                except Exception as exc:
                    ok, r = False, exc
                if ok:
                    checked[old] = new
                else:
                    skipped.append((old, new, getattr(r, "status_code", type(r).__name__)))
        else:
            checked = pending

        stats = Counter()
        for old, new in checked.items():
            for e in by_url[old]:
                e.source = new
                e.save(update_fields=["source"])
                stats["cambodia library slug" if CAMBODIA.search(old)
                      else "soda4LCA datasetdetail"] += 1

        self.stdout.write("\nrepaired:")
        for k, v in stats.most_common():
            self.stdout.write("   %4d EPDs  %s" % (v, k))

        if skipped:
            self.stdout.write(self.style.WARNING(
                "\nleft unchanged - the replacement did not return 200:"))
            for old, new, code in skipped[:20]:
                self.stdout.write("   [%s] %s" % (code, old[:86]))
            if len(skipped) > 20:
                self.stdout.write("   ... %d total" % len(skipped))


class _Rollback(Exception):
    """Internal: unwinds the transaction after a dry run."""
