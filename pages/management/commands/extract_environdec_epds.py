"""Pull GWP figures out of the published environdec PDFs into a review CSV.

This writes a CSV for a human to check. It does not touch the database - the
import is a separate, later step, deliberately, because numbers read out of a
PDF have to be looked at before they become carbon figures in a tool.

For each row of the shortlist it:
  1. fetches the library page and finds the document link on it
  2. downloads the PDF (cached on disk, so a re-run costs nothing)
  3. reads the module header row and maps the GWP values onto it
  4. writes one output row, or a refusal with the reason

Anything it cannot read confidently is written out with status=REFUSED and an
empty GWP, never a guess. See pages/scripts/environdec/pdf_extract.py for why.

    python manage.py extract_environdec_epds --limit 20
    python manage.py extract_environdec_epds --in shortlist.csv --out parsed.csv
"""
import csv
import os
import re
import time

import requests
from django.core.management.base import BaseCommand

from pages.scripts.environdec.pdf_extract import extract_from_pdf

requests.packages.urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (BEAT EPD import)"}

# The library page carries the document link for its own EPD.
DOC_LINK = re.compile(
    r"https://api\.prod\.environdec\.com/api/v1/EPDLibrary/Files/EPDs/"
    r"[0-9a-f-]{36}/Documents", re.I)

OUT_FIELDS = [
    "status", "country", "material_group", "product", "manufacturer",
    "registration_number", "gwp_a1a3", "declared_amount", "declared_unit",
    "gwp_a4", "gwp_a5", "gwp_c", "gwp_d", "url", "reason", "header_row",
]


class Command(BaseCommand):
    help = "Extract GWP from environdec PDFs into a CSV for review."

    def add_arguments(self, parser):
        parser.add_argument("--in", dest="infile",
                            default=os.path.expanduser(
                                "~/Downloads/environdec_shortlist_404.csv"))
        parser.add_argument("--out", dest="outfile",
                            default=os.path.expanduser(
                                "~/Downloads/environdec_parsed.csv"))
        parser.add_argument("--cache", default=None,
                            help="Directory for downloaded PDFs (default: ./.epd_pdfs)")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after N rows (0 = all).")
        parser.add_argument("--delay", type=float, default=0.5,
                            help="Seconds between network calls.")

    def handle(self, *args, **o):
        cache = o["cache"] or os.path.join(os.getcwd(), ".epd_pdfs")
        os.makedirs(cache, exist_ok=True)

        rows = list(csv.DictReader(open(o["infile"], encoding="utf-8-sig")))
        if o["limit"]:
            rows = rows[:o["limit"]]
        self.stdout.write("rows to process: %d" % len(rows))

        out = []
        ok = refused = 0
        for n, r in enumerate(rows, 1):
            res = self._one(r, cache, o["delay"])
            out.append(res)
            if res["status"] == "OK":
                ok += 1
            else:
                refused += 1
            if n % 10 == 0 or n == len(rows):
                self.stdout.write("   %d/%d   parsed %d   refused %d"
                                  % (n, len(rows), ok, refused))

        with open(o["outfile"], "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
            w.writeheader()
            for r in out:
                w.writerow(r)

        self.stdout.write(self.style.SUCCESS(
            "\nparsed %d, refused %d  ->  %s" % (ok, refused, o["outfile"])))
        if refused:
            self.stdout.write("refusal reasons:")
            from collections import Counter
            for reason, c in Counter(r["reason"] for r in out
                                     if r["status"] != "OK").most_common(8):
                self.stdout.write("   %4d  %s" % (c, reason[:88]))

    # ------------------------------------------------------------------
    def _one(self, row, cache, delay):
        base = {k: row.get(k, "") for k in
                ("country", "material_group", "product", "manufacturer",
                 "registration_number", "url")}
        out = dict.fromkeys(OUT_FIELDS, "")
        out.update(base)

        slug = re.sub(r"\W+", "_", (row.get("registration_number") or
                                    row.get("url") or "epd"))[:60]
        path = os.path.join(cache, slug + ".pdf")

        if not os.path.exists(path):
            try:
                page = requests.get(row["url"], headers=HEADERS, timeout=60,
                                    verify=False)
                time.sleep(delay)
                link = DOC_LINK.search(page.text)
                if not link:
                    out.update(status="REFUSED",
                               reason="no document link on the library page")
                    return out
                pdf = requests.get(link.group(0), headers=HEADERS, timeout=120,
                                   verify=False)
                time.sleep(delay)
                if pdf.status_code != 200 or not pdf.content[:4] == b"%PDF":
                    out.update(status="REFUSED",
                               reason="document download returned %s" % pdf.status_code)
                    return out
                with open(path, "wb") as fh:
                    fh.write(pdf.content)
            except Exception as exc:
                out.update(status="REFUSED",
                           reason="fetch failed: %s" % type(exc).__name__)
                return out

        res = extract_from_pdf(path)
        if not res["ok"]:
            out.update(status="REFUSED", reason=res["reason"])
            return out

        mods = res["modules"]
        out.update(
            status="OK",
            gwp_a1a3=res["gwp_a1a3"],
            declared_amount=res["declared_amount"] or "",
            declared_unit=res["declared_unit"] or "",
            gwp_a4=mods.get("A4", ""),
            gwp_a5=mods.get("A5", ""),
            gwp_c=sum(v for k, v in mods.items() if k.startswith("C")) or "",
            gwp_d=mods.get("D", ""),
            header_row=res["header"],
        )
        return out
