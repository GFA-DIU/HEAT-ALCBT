import base64
import io
import os
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.views.decorators.http import require_http_methods

from pages.models.building import Building
from pages.views.building.building_stats import get_building_detail_statistics, get_building_chart_data


def _get_logo_b64(filename):
    path = os.path.join(settings.BASE_DIR, "static", "images", "logos", filename)
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(filename)[1].lstrip(".").lower()
        mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
        return f"data:{mime};base64,{data}"
    except FileNotFoundError:
        return ""


def _get_icon_b64(filename):
    path = os.path.join(settings.BASE_DIR, "static", "assets", "icons", filename)
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/svg+xml;base64,{data}"
    except FileNotFoundError:
        return ""


def _building_location(building):
    parts = []
    if building.region:
        parts.append(str(building.region))
    if building.country:
        parts.append(str(building.country))
    return ", ".join(parts)


def _boq_links(building, request):
    links = []
    for f in building.boq_files.all():
        url = request.build_absolute_uri(f.file.url)
        links.append((f.original_filename or os.path.basename(f.file.name), url))
    return links


def _donut_card_html(operational, embodied, leaf_icon, card_donut_b64):
    """When we have the full card screenshot, embed it directly — it already has border/styling."""
    if card_donut_b64:
        return f'<img src="{card_donut_b64}" style="width:210pt; display:block; margin:0 auto;"/>'

    # Fallback plain card (no screenshot)
    op_color = "#7d52f4"
    em_color = "#222530"
    op_fmt = f"{operational:,.1f}"
    em_fmt = f"{embodied:,.1f}"
    leaf_img = f'<img src="{leaf_icon}" style="width:16pt;height:16pt;vertical-align:middle;margin-right:6pt;"/>' if leaf_icon else ""
    chart_section = ""

    return f"""<div style="border:1pt solid #e5e7eb; border-radius:16pt; padding:16pt 18pt 20pt 18pt; margin-bottom:12pt;">
  <p style="border:none; font-size:10pt; font-weight:600; color:#1f2937; margin-bottom:0; margin-top:0;">
    {leaf_img}<span style="vertical-align:middle;">Whole Life Carbon Cycle</span>
  </p>
  {chart_section}
  <p style="border:none; font-size:9pt; color:#6b7280; margin-bottom:4pt; margin-top:0; line-height:1.4;">
    <span style="display:inline-block; width:7pt; height:7pt; border-radius:50%; background-color:{op_color}; vertical-align:middle; margin-right:6pt;"></span>Operational carbon: {op_fmt} kgCO<sub>2</sub>eq/m&#178;
  </p>
  <p style="border:none; font-size:9pt; color:#6b7280; margin-bottom:0; margin-top:0; line-height:1.4;">
    <span style="display:inline-block; width:7pt; height:7pt; border-radius:50%; background-color:{em_color}; vertical-align:middle; margin-right:6pt;"></span>Embodied carbon: {em_fmt} kgCO<sub>2</sub>eq/m&#178;
  </p>
</div>"""


def _chart_img(b64, width="100%", height=None):
    """Embed a captured card image."""
    if not b64:
        return '<p style="color:#9ca3af;font-size:9pt;text-align:center;font-style:italic;">Chart not available</p>'
    h_style = f"height:{height};" if height else ""
    return f'<img src="{b64}" style="width:{width};{h_style} display:block; margin:0 auto;"/>'


def _build_context(building, request, card_donut="", card_assembly="", card_material="", card_savings=""):
    location = _building_location(building)
    boq_links = _boq_links(building, request)
    coords = None
    if building.latitude and building.longitude:
        coords = f"{building.latitude:.6f}, {building.longitude:.6f}"
    address = None
    parts = []
    if building.zip:
        parts.append(str(building.zip))
    if building.street:
        num = f"{building.number} " if building.number else ""
        parts.append(f"{num}{building.street}")
    if parts:
        address = ", ".join(parts)

    stats = get_building_detail_statistics(building)
    operational = float(stats["total_operational_carbon"])
    embodied = float(stats["total_embodied_carbon"])
    total = float(stats["total_carbon_footprint"])
    savings_pct = float(stats["carbon_savings_percentage"])
    op_pct = round((operational / total * 100)) if total else 0
    em_pct = round((embodied / total * 100)) if total else 0
    leaf_icon = _get_icon_b64("leaf-line.svg")
    donut_card = _donut_card_html(operational, embodied, leaf_icon, card_donut)

    def fmt(val):
        return f"{val:,.1f}"

    return {
        "building": building,
        "location": location,
        "boq_links": boq_links,
        "coords": coords,
        "address": address,
        "report_date": date.today().strftime("%-d %B %Y") if os.name != "nt" else date.today().strftime("%#d %B %Y"),
        "alcbt_logo": _get_logo_b64("ALCBT_logo.png"),
        "sponsor_logo": _get_logo_b64("sponsor-2.png"),
        "assessor_name": f"{request.user.first_name} {request.user.last_name}".strip() or "[Assessor Name]",
        "organisation": str(building.organisation) if building.organisation else "[Organisation Name]",
        "total_carbon": fmt(total),
        "embodied_carbon": fmt(embodied),
        "operational_carbon": fmt(operational),
        "savings_pct": f"{savings_pct:.1f}",
        "op_pct": op_pct,
        "em_pct": em_pct,
        "donut_card": donut_card,
        "card_donut": card_donut,
        "card_assembly": card_assembly,
        "card_material": card_material,
        "card_savings": card_savings,
    }


# ── PDF ──────────────────────────────────────────────────────────────────────

PDF_CSS = """
@page {
    size: A4;
    margin: 2.8cm 2cm 2.8cm 2cm;
    @frame header_frame {
        -pdf-frame-content: pdf-header;
        left: 2cm; right: 2cm;
        top: 0.6cm; height: 1cm;
    }
    @frame footer_frame {
        -pdf-frame-content: pdf-footer;
        left: 2cm; right: 2cm;
        bottom: 0.6cm; height: 1cm;
    }
}
@page cover_page {
    size: A4;
    margin: 2cm;
    @frame content_frame {
        left: 0; right: 0; top: 0; bottom: 0;
    }
}
* { box-sizing: border-box; margin: 0; padding: 0; border: none; }
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10pt;
    color: #1f2937;
    line-height: 1.5;
}

/* Header / footer frames */
#pdf-header {
    border-bottom: 0.5pt solid #d1d5db;
    padding-bottom: 4pt;
    font-size: 8pt;
    color: #6b7280;
}
#pdf-header table { width: 100%; }
#pdf-footer {
    border-top: 0.5pt solid #d1d5db;
    padding-top: 4pt;
    font-size: 8pt;
    color: #9ca3af;
}
#pdf-footer table { width: 100%; }
.footer-right { text-align: right; }

/* Cover */
.cover-page { -pdf-page-template: cover_page; }
.cover-report-title {
    font-size: 22pt;
    font-weight: 800;
    color: #0f2744;
    margin-bottom: 6pt;
}
.cover-building-sub {
    font-size: 11pt;
    color: #6b7280;
    margin-bottom: 28pt;
}
.info-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 36pt;
}
.info-table .odd td { background-color: #f3f4f6; }
.info-table td {
    padding: 8pt 10pt;
    font-size: 10pt;
}
.info-table .label-col {
    font-weight: bold;
    width: 40%;
    color: #374151;
}

/* Section heading */
.section-heading {
    font-size: 12pt;
    font-weight: bold;
    color: #0f2744;
    border-bottom: 2pt solid #1d6fa8;
    padding-bottom: 5pt;
    margin-top: 0pt;
    margin-bottom: 10pt;
}

/* Detail rows via table */
.detail-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9.5pt;
}
.detail-table td {
    padding: 2pt 4pt;
    vertical-align: top;
    border: none;
    line-height: 1.3;
}
.detail-table .dlabel {
    width: 46%;
    font-weight: bold;
    color: #374151;
}
.detail-table .dvalue {
    color: #111827;
}
.detail-table a { color: #1d6fa8; }

/* Developer under logos — pushed toward bottom of cover page */
.dev-under-section {
    margin-top: 120pt;
}
.dev-under-label {
    font-size: 9pt;
    font-weight: bold;
    color: #374151;
    margin-bottom: 10pt;
}
.logos-table {
    width: 100%;
    border-collapse: collapse;
}
.logos-table td { vertical-align: middle; padding: 0; }

.page-break { page-break-before: always; }

/* Body text */
.body-text {
    font-size: 10pt;
    color: #374151;
    line-height: 1.6;
    margin-bottom: 10pt;
    margin-top: 0;
}

/* Figure caption */
.fig-caption {
    font-size: 8.5pt;
    color: #6b7280;
    text-align: center;
    margin-top: 6pt;
    margin-bottom: 12pt;
    font-style: italic;
}

/* Subsection heading (2.1, 2.2 etc) */
.subsection-heading {
    font-size: 11pt;
    font-weight: bold;
    color: #1d6fa8;
    margin-top: 16pt;
    margin-bottom: 10pt;
}

/* Info callout banner */
.callout {
    background-color: #eff6ff;
    border-left: 3pt solid #1d6fa8;
    padding: 10pt 12pt;
    font-size: 9.5pt;
    color: #374151;
    margin-bottom: 16pt;
}

/* Headline metrics grid */
.metrics-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 12pt;
}
.metrics-table td {
    padding: 10pt 12pt;
    vertical-align: top;
    width: 33%;
}
.metrics-table .row-bg { background-color: #f3f4f6; }
.metric-label {
    font-size: 8pt;
    color: #6b7280;
    margin-bottom: 3pt;
}
.metric-value {
    font-size: 18pt;
    font-weight: 900;
    color: #111827;
    line-height: 1;
}
.metric-unit {
    font-size: 8pt;
    color: #6b7280;
}

/* Donut card — mirrors live card */
.donut-card {
    border: 0.5pt solid #e5e7eb;
    border-radius: 12pt;
    padding: 12pt 14pt 16pt 14pt;
    margin-bottom: 14pt;
}
.donut-card-header {
    font-size: 10pt;
    font-weight: 600;
    color: #374151;
    margin-bottom: 14pt;
}
.donut-card-header img {
    vertical-align: middle;
    margin-right: 6pt;
    width: 16pt;
    height: 16pt;
}
.legend-dot {
    display: inline-block;
    width: 7pt;
    height: 7pt;
    border-radius: 50%;
    margin-right: 6pt;
    vertical-align: middle;
}
.legend-row {
    font-size: 9pt;
    color: #6b7280;
    margin-bottom: 5pt;
}

/* Highlighted numbers in paragraph */
.highlight {
    background-color: #fef08a;
    padding: 0 2pt;
}
.body-text {
    font-size: 10pt;
    color: #374151;
    line-height: 1.6;
    margin-bottom: 10pt;
}
"""


def _pdf_html(ctx):
    b = ctx["building"]
    loc = ctx["location"]
    header_text = f"{b.name} &middot; {loc}" if loc else b.name

    boq_html = "&#8212;"
    if ctx["boq_links"]:
        boq_html = " &nbsp; ".join(f'<a href="{u}">{n}</a>' for n, u in ctx["boq_links"])

    cert = "Yes" if b.has_certification else "No"

    cat = subcat = ""
    if b.category:
        cat = str(b.category.category) if b.category.category else ""
        subcat = str(b.category.subcategory) if b.category.subcategory else ""

    alcbt_img = f'<img src="{ctx["alcbt_logo"]}" style="width:100%; max-width:220pt"/>' if ctx["alcbt_logo"] else ""
    sponsor_img = f'<img src="{ctx["sponsor_logo"]}" style="width:100%; max-width:180pt"/>' if ctx["sponsor_logo"] else ""

    def dr(label, value):
        v = value if value else "&#8212;"
        return f'<tr><td class="dlabel">{label}</td><td class="dvalue">{v}</td></tr>'

    coords = ctx["coords"] or None
    addr = ctx["address"] or None
    floors_below = b.floors_below_ground if b.floors_below_ground is not None else None
    cond_area = f"{b.cond_floor_area} m&#178;" if b.cond_floor_area else None

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>{PDF_CSS}</style>
</head>
<body>

<!-- Running header (shown on all pages via @frame, hidden on cover via cover_page template) -->
<div id="pdf-header">
  <table><tr>
    <td>BEAT Whole Life Carbon Assessment Report</td>
    <td style="text-align:right">{header_text}</td>
  </tr></table>
</div>

<!-- Running footer -->
<div id="pdf-footer">
  <table><tr>
    <td>Confidential &#8212; BEAT</td>
    <td class="footer-right">Page <pdf:pagenumber/> of <pdf:pagecount/></td>
  </tr></table>
</div>

<!-- ===== COVER PAGE ===== -->
<div class="cover-page">
  <table style="width:110%; margin-left:-5%; background-color:#0f2744; margin-bottom:24pt;">
    <tr><td style="padding:14pt 0pt 4pt 5%; font-size:26pt; font-weight:900; color:#ffffff; line-height:1;">BEAT</td></tr>
    <tr><td style="padding:0pt 0pt 14pt 5%; font-size:10pt; color:#ffffff;">Building Emissions Assessment Tool</td></tr>
  </table>

  <p class="cover-report-title" style="padding-left:5%;">Whole Life Carbon Assessment Report</p>
  <p class="cover-building-sub" style="padding-left:5%;">{b.name} &nbsp;&middot;&nbsp; {loc}</p>

  <table class="info-table">
    <tr class="odd"><td class="label-col">Report date</td><td>{ctx["report_date"]}</td></tr>
    <tr><td class="label-col">Prepared by</td><td>{ctx["assessor_name"]}</td></tr>
    <tr class="odd"><td class="label-col">Organisation</td><td>{ctx["organisation"]}</td></tr>
    <tr><td class="label-col">Assessment tool</td><td>BEAT</td></tr>
  </table>

  <div class="dev-under-section">
    <p class="dev-under-label">Developer under:</p>
    <table class="logos-table">
      <tr>
        <td style="width:55%">{alcbt_img}</td>
        <td style="width:45%">{sponsor_img}</td>
      </tr>
    </table>
  </div>
</div>

<!-- ===== PAGE 2: BUILDING DETAILS ===== -->
<div class="page-break"></div>

<p class="section-heading">1. Building Details</p>

<table class="detail-table">
  {dr("Building name or Code:", b.name)}
  {dr("Address (Zip, Street):", addr)}
  {dr("Coordinates:", coords)}
  {dr("Country:", str(b.country) if b.country else None)}
  {dr("Region or State:", str(b.region) if b.region else None)}
  {dr("City:", str(b.city) if b.city else None)}
  {dr("Building type:", cat)}
  {dr("Building sub-type:", subcat)}
  {dr("Climate type:", str(b.climate_zone) if b.climate_zone else None)}
  {dr("Life cycle assessment period:", f"{b.reference_period} years")}
  {dr("Construction year:", b.construction_year)}
  {dr("Total floor area:", f"{b.total_floor_area} m&#178;")}
  {dr("Conditioned floor area:", cond_area)}
  {dr("Floors below ground:", floors_below)}
  {dr("Certification process:", cert)}
  {dr("BoQ / design drawings:", boq_html)}
</table>

<!-- Section 2 starts immediately after section 1, still on page 2 -->
<p class="section-heading" style="margin-top:24pt;">2. Whole Life Cycle Carbon Footprint Summary</p>

<p class="body-text">The whole life cycle carbon footprint of the building is expressed as a carbon intensity in kgCO<sub>2</sub>eq per square metre of total floor area. It combines two distinct components: embodied carbon (the emissions associated with the manufacture, transport, and installation of building materials) and operational carbon (the emissions arising from energy consumed by building systems over the assessment period). It covers A1&#8211;A3 scope for embodied carbon and B6 for operational carbon.</p>

<div class="callout">Carbon Footprint = Embodied Carbon + Operational Carbon &nbsp;&nbsp; All figures are expressed as kgCO<sub>2</sub>eq/m&#178; over the full assessment period unless stated otherwise.</div>

<!-- ===== PAGE 3: 2.1 + 2.2 ===== -->
<div class="page-break"></div>

<p class="subsection-heading">2.1 &nbsp; Headline Metrics</p>

<table class="metrics-table">
  <tr class="row-bg">
    <td>
      <p class="metric-label">Carbon Footprint</p>
      <p><span class="metric-value">{ctx["total_carbon"]}</span> <span class="metric-unit">kgCO<sub>2</sub>eq/m&#178;</span></p>
    </td>
    <td>
      <p class="metric-label">Total Floor Area</p>
      <p><span class="metric-value">{int(b.total_floor_area):,}</span> <span class="metric-unit">m&#178;</span></p>
    </td>
    <td>
      <p class="metric-label">Assessment Period</p>
      <p><span class="metric-value">{b.reference_period}</span> <span class="metric-unit">years</span></p>
    </td>
  </tr>
  <tr>
    <td>
      <p class="metric-label">Embodied Carbon</p>
      <p><span class="metric-value">{ctx["embodied_carbon"]}</span> <span class="metric-unit">kgCO<sub>2</sub>eq/m&#178;</span></p>
    </td>
    <td>
      <p class="metric-label">Operational Carbon</p>
      <p><span class="metric-value">{ctx["operational_carbon"]}</span> <span class="metric-unit">kgCO<sub>2</sub>eq/m&#178;</span></p>
    </td>
    <td>
      <p class="metric-label">Carbon Savings</p>
      <p><span class="metric-value">{ctx["savings_pct"]}</span> <span class="metric-unit">%</span></p>
    </td>
  </tr>
</table>

<p class="subsection-heading">2.2 &nbsp; Whole Life Cycle Carbon</p>

<p class="body-text">The dashboard below shows the split between embodied and operational carbon as a proportion of the total building carbon footprint, alongside a breakdown of embodied carbon by building assembly (structural elements, facades, finishes, etc.).</p>

{ctx["donut_card"]}
<p class="fig-caption">Figure 1 &#8212; Whole life carbon cycle of the building</p>

<p class="body-text">Operational carbon accounts for <span class="highlight">{ctx["op_pct"]}%</span> of the total carbon footprint (<span class="highlight">{ctx["operational_carbon"]} kgCO<sub>2</sub>eq/m&#178;</span>), reflecting the dominant role of building energy systems over a <span class="highlight">{b.reference_period}-year</span> assessment period. Embodied carbon contributes the remaining <span class="highlight">{ctx["em_pct"]}%</span> (<span class="highlight">{ctx["embodied_carbon"]} kgCO<sub>2</sub>eq/m&#178;</span>) which underscores the importance of reducing embodied carbon, which carries significant weight in overall emissions&#8212;particularly those generated during the construction and renovation phases of a building. It is important to note that, unlike operational carbon, embodied carbon is released upfront, resulting in substantial emissions at the time a building is constructed or renovated.</p>

<!-- ===== PAGE 4: SECTION 3 ===== -->
<div class="page-break"></div>

<p class="section-heading">3. Embodied Carbon</p>

<p class="body-text">Embodied carbon covers the greenhouse gas emissions associated with raw material extraction, manufacturing, transportation, construction, maintenance, and end-of-life disposal of building materials. In BEAT, it is assessed across both building assemblies (structural systems, envelopes, finishes) and constituent materials.</p>

<p class="subsection-heading" style="margin-top:18pt;">3.1 &nbsp; Embodied Carbon by Assembly</p>

<p class="body-text">The chart below disaggregates the total embodied carbon intensity (<span class="highlight">{ctx["embodied_carbon"]} kgCO<sub>2</sub>eq/m&#178;</span>) by building component/assembly. Each bar represents a building component&#8217;s percentage share of the total embodied carbon. Only building components entered in the Bill of Quantities by users are included; the percentage distribution always sums to 100% across entered materials.</p>

{_chart_img(ctx["card_assembly"], "88%")}
<p class="fig-caption">Figure 2 &#8212; Embodied carbon by Assemblies (assembly tab)</p>

<p class="subsection-heading" style="margin-top:18pt;">3.2 &nbsp; Embodied Carbon by Material</p>

<p class="body-text">The chart below disaggregates the total embodied carbon intensity (<span class="highlight">{ctx["embodied_carbon"]} kgCO<sub>2</sub>eq/m&#178;</span>) by material category. Each bar represents a material&#8217;s percentage share of the total embodied carbon. Only materials with quantities entered in the Bill of Quantities are included; the percentage distribution always sums to 100% across entered materials.</p>

{_chart_img(ctx["card_material"], "88%")}
<p class="fig-caption">Figure 3 &#8212; Embodied carbon by material (Materials tab)</p>

<p class="body-text">Rebar and ready-mix concrete together account for over <span class="highlight">81%</span> of total embodied carbon &#8212; a pattern typical of reinforced concrete-frame office buildings. Strategies to reduce this share include specifying low-carbon concrete mixes (<span class="highlight">GGBS</span> or fly ash blends), using <span class="highlight">recycled-content</span> reinforcement, and minimising structural over-design.</p>

<!-- ===== PAGE 5: SECTION 4 — OPERATIONAL CARBON ===== -->
<div class="page-break"></div>

<p class="section-heading">4. Operational Carbon</p>

<p class="body-text">Operational carbon covers the greenhouse gas emissions arising from energy consumed by building systems during its use.</p>

<div class="callout">Formula: Carbon Intensity (kgCO<sub>2</sub>eq/m&#178;/yr) = Energy<sub>appliance</sub> (kWh/yr) &times; Grid<sub>factor</sub> (kgCO<sub>2</sub>eq/kWh) &divide; Floor<sub>area</sub> (m&#178;)</div>

<p class="subsection-heading">4.1 &nbsp; Operational Carbon by Appliances</p>

<p class="body-text">The Energy tab chart below shows operational carbon intensity broken down by building system (cooling, ventilation, lighting, hot water, lifts &amp; escalators). Within each system, individual appliances are shown as sub-bars. Only appliances with energy data entered contribute to the totals; the percentage distribution always sums to 100% across entered appliances.</p>

<p class="fig-caption" style="margin-top:80pt;">Figure 4 &#8212; Operational carbon by system and appliance (Energy tab)</p>

<p class="body-text"><span class="highlight">Cooling</span> is the dominant operational carbon contributor at <span class="highlight">43%</span>, driven primarily by split AC units (<span class="highlight">28%</span> of building total) and VRF systems (<span class="highlight">13%</span>).</p>

<!-- ===== PAGE 6: SECTION 5 — BENCHMARKING ===== -->
<div class="page-break"></div>

<p class="section-heading">5. Benchmarking &amp; Carbon Savings</p>

<p class="body-text">The Savings tab compares the building&#8217;s total carbon footprint against a peer benchmark for similar buildings in the same region, and presents targeted optimisation strategies ranked by potential carbon reduction. Each strategy shows a baseline value, a potential saving, and a brief description of the intervention required.</p>

<p class="subsection-heading">5.1 &nbsp; Project Performance Benchmark</p>

<p class="body-text">The benchmark gauge below shows where this building sits relative to the best-practice and national average figures for comparable buildings. The position of the building marker on the scale indicates performance tier.</p>

{_chart_img(ctx["card_savings"], "70%", "1300pt")}
<p class="fig-caption">Figure 5 &#8212; Project performance benchmark and carbon savings strategies (Savings tab)</p>

<!-- ===== LAST PAGE: 5.2 + 5.3 ===== -->
<div class="page-break"></div>

<p class="subsection-heading" style="margin-top:0;">5.2 &nbsp; Benchmark Summary</p>

<table class="metrics-table" style="margin-bottom:10pt;">
  <tr class="row-bg">
    <td>
      <p class="metric-label">Your building</p>
      <p><span class="metric-value">{ctx["total_carbon"]}</span> <span class="metric-unit">kgCO<sub>2</sub>eq/m&#178;</span></p>
    </td>
    <td>
      <p class="metric-label">Best practice</p>
      <p><span class="metric-value">320</span> <span class="metric-unit">kgCO<sub>2</sub>eq/m&#178;</span></p>
    </td>
    <td>
      <p class="metric-label">National average</p>
      <p><span class="metric-value">640</span> <span class="metric-unit">kgCO<sub>2</sub>eq/m&#178;</span></p>
    </td>
  </tr>
</table>

<div class="callout">This building performs better than 78% of peer projects in Germany (452 residential projects, Baden-W&#252;rttemberg, 2024&#8211;2025). It is rated in the Top 25% tier. Benchmark data is region- and building-type specific.</div>

<p class="subsection-heading">5.3 &nbsp; Optimisation Strategies</p>

<p class="body-text">The following strategies are identified as the highest-impact opportunities for reducing embodied carbon, ordered by percentage of total footprint:</p>

<table class="info-table" style="margin-bottom:16pt;">
  <tr class="odd">
    <td class="label-col" style="font-weight:bold; color:#374151;">Strategy</td>
    <td style="font-weight:bold; color:#374151;">Potential saving / Notes</td>
  </tr>
  <tr>
    <td class="label-col">Ready-mix concrete &amp; cement</td>
    <td>&#8722;40 kgCO<sub>2</sub>eq/m&#178; &nbsp;(30% of total) &nbsp;25% GGBS/Fly Ash blend &#8594; 139 &#8594; 104 kgCO<sub>2</sub>eq/m&#178;</td>
  </tr>
  <tr class="odd">
    <td class="label-col">Steel</td>
    <td>&#8722;20 kgCO<sub>2</sub>eq/m&#178; &nbsp;(15% of total) &nbsp;20% recycled content &#8594; 69 &#8594; 55 kgCO<sub>2</sub>eq/m&#178;</td>
  </tr>
  <tr>
    <td class="label-col">Reinforcement bar (rebar)</td>
    <td>&#8722;35 kgCO<sub>2</sub>eq/m&#178; &nbsp;(15% of total) &nbsp;Low-carbon rebar specification</td>
  </tr>
  <tr class="odd">
    <td class="label-col" style="font-weight:bold;">Total potential embodied saving</td>
    <td style="font-weight:bold;">&#8722;85 kgCO<sub>2</sub>eq/m&#178; &nbsp;(12.5% reduction from baseline)</td>
  </tr>
</table>

<p class="body-text">Operational carbon savings are not yet modelled for this project. Recommended next steps include specifying higher-efficiency cooling equipment, exploring on-site renewable generation, and re-assessing the grid emission factor annually as the national grid decarbonises.</p>

</body>
</html>"""




# ── Word (docx) ───────────────────────────────────────────────────────────────

def _add_b64_image(doc, b64_data_url, width=None, height=None):
    """Embed a base64 data URL image into the doc."""
    from docx.shared import Cm
    if not b64_data_url or ',' not in b64_data_url:
        return
    _, data = b64_data_url.split(',', 1)
    img_bytes = base64.b64decode(data)
    stream = io.BytesIO(img_bytes)
    p = doc.add_paragraph()
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    kwargs = {}
    if width: kwargs['width'] = width
    if height: kwargs['height'] = height
    run.add_picture(stream, **kwargs)


def _add_section_heading(doc, number, title):
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import lxml.etree as etree

    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(18)
    para.paragraph_format.space_after = Pt(10)

    run = para.add_run(f"{number}. {title}")
    run.bold = True
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor(0x0F, 0x27, 0x44)

    # bottom border
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "1D6FA8")
    pBdr.append(bottom)
    pPr.append(pBdr)
    return para


def _add_detail_row(doc, label, value):
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after = Pt(2)

    label_run = para.add_run(f"{label}  ")
    label_run.bold = True
    label_run.font.size = Pt(10)
    label_run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

    val_run = para.add_run(str(value) if value else "—")
    val_run.font.size = Pt(10)
    val_run.font.color.rgb = RGBColor(0x11, 0x18, 0x27)

    # bottom border on paragraph
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "E5E7EB")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _build_docx(ctx):
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    b = ctx["building"]
    loc = ctx["location"]

    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

    # ── Header ──────────────────────────────────────────────────────────────
    header = doc.sections[0].header
    header.is_linked_to_previous = False
    htable = header.add_table(1, 2, width=Inches(6.3))
    htable.autofit = True
    left_cell = htable.cell(0, 0)
    right_cell = htable.cell(0, 1)

    lp = left_cell.paragraphs[0]
    lr = lp.add_run("BEAT Whole Life Carbon Assessment Report")
    lr.font.size = Pt(8)
    lr.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    rp = right_cell.paragraphs[0]
    rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header_text = f"{b.name}\u00b7 {loc}" if loc else b.name
    rr = rp.add_run(header_text)
    rr.font.size = Pt(8)
    rr.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    # border under header table
    tbl = htable._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")
    tblBorders = OxmlElement("w:tblBorders")
    bottom_b = OxmlElement("w:bottom")
    bottom_b.set(qn("w:val"), "single")
    bottom_b.set(qn("w:sz"), "4")
    bottom_b.set(qn("w:color"), "D1D5DB")
    tblBorders.append(bottom_b)
    tblPr.append(tblBorders)

    # ── Footer ──────────────────────────────────────────────────────────────
    footer = doc.sections[0].footer
    footer.is_linked_to_previous = False
    ftable = footer.add_table(1, 2, width=Inches(6.3))
    ftable.autofit = True
    fl_cell = ftable.cell(0, 0)
    fr_cell = ftable.cell(0, 1)

    flp = fl_cell.paragraphs[0]
    flr = flp.add_run("Confidential \u2014 BEAT")
    flr.font.size = Pt(8)
    flr.font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)

    frp = fr_cell.paragraphs[0]
    frp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    frr = frp.add_run("Page ")
    frr.font.size = Pt(8)
    frr.font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)

    # Add page number field
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "begin")
    frr._r.append(fld)
    instrText = OxmlElement("w:instrText")
    instrText.text = " PAGE "
    frr._r.append(instrText)
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    frr._r.append(fld2)

    frr2 = frp.add_run(" of ")
    frr2.font.size = Pt(8)
    frr2.font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)

    fld3 = OxmlElement("w:fldChar")
    fld3.set(qn("w:fldCharType"), "begin")
    frr2._r.append(fld3)
    instrText2 = OxmlElement("w:instrText")
    instrText2.text = " NUMPAGES "
    frr2._r.append(instrText2)
    fld4 = OxmlElement("w:fldChar")
    fld4.set(qn("w:fldCharType"), "end")
    frr2._r.append(fld4)

    # top border on footer
    ftbl = ftable._tbl
    ftblPr = OxmlElement("w:tblPr")
    ftblBorders = OxmlElement("w:tblBorders")
    top_b = OxmlElement("w:top")
    top_b.set(qn("w:val"), "single")
    top_b.set(qn("w:sz"), "4")
    top_b.set(qn("w:color"), "D1D5DB")
    ftblBorders.append(top_b)
    ftblPr.append(ftblBorders)
    ftbl.insert(0, ftblPr)

    # ── Cover page ──────────────────────────────────────────────────────────

    # Dark banner
    banner = doc.add_paragraph()
    banner.paragraph_format.space_before = Pt(0)
    banner.paragraph_format.space_after = Pt(0)
    # shade the paragraph with dark color via paragraph shading
    pPr = banner._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "0F2744")
    pPr.append(shd)
    beat_run = banner.add_run("BEAT")
    beat_run.bold = True
    beat_run.font.size = Pt(28)
    beat_run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    banner2 = doc.add_paragraph()
    pPr2 = banner2._p.get_or_add_pPr()
    shd2 = OxmlElement("w:shd")
    shd2.set(qn("w:val"), "clear")
    shd2.set(qn("w:color"), "auto")
    shd2.set(qn("w:fill"), "0F2744")
    pPr2.append(shd2)
    banner2.paragraph_format.space_after = Pt(24)
    sub_run = banner2.add_run("Building Emissions Assessment Tool")
    sub_run.font.size = Pt(11)
    sub_run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    # Report title
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(24)
    title_p.paragraph_format.space_after = Pt(6)
    title_r = title_p.add_run("Whole Life Carbon Assessment Report")
    title_r.bold = True
    title_r.font.size = Pt(22)
    title_r.font.color.rgb = RGBColor(0x0F, 0x27, 0x44)

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(24)
    sub_r = sub_p.add_run(f"{b.name}  \u00b7  {loc}")
    sub_r.font.size = Pt(12)
    sub_r.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    # Info table
    table = doc.add_table(rows=4, cols=2)
    table.style = "Table Grid"
    rows_data = [
        ("Report date", ctx["report_date"]),
        ("Prepared by", ctx["assessor_name"]),
        ("Organisation", ctx["organisation"]),
        ("Assessment tool", "BEAT"),
    ]
    fill_colors = ["F3F4F6", "FFFFFF", "F3F4F6", "FFFFFF"]
    for i, (label, value) in enumerate(rows_data):
        row = table.rows[i]
        lc = row.cells[0]
        vc = row.cells[1]
        for cell, text, bold in [(lc, label, True), (vc, value, False)]:
            p = cell.paragraphs[0]
            run = p.add_run(text)
            run.bold = bold
            run.font.size = Pt(10)
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), fill_colors[i])
            tcPr.append(shd)

    # Logos block
    doc.add_paragraph()
    dev_p = doc.add_paragraph()
    dev_r = dev_p.add_run("Developer under:")
    dev_r.bold = True
    dev_r.font.size = Pt(9)
    dev_r.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
    dev_p.paragraph_format.space_after = Pt(8)

    logo_p = doc.add_paragraph()
    for logo_key, width_cm in [("alcbt_logo", 5), ("sponsor_logo", 4)]:
        b64 = ctx.get(logo_key, "")
        if b64 and b64.startswith("data:image"):
            header_part, data_part = b64.split(",", 1)
            img_bytes = base64.b64decode(data_part)
            img_stream = io.BytesIO(img_bytes)
            try:
                logo_p.add_run().add_picture(img_stream, width=Cm(width_cm))
                logo_p.add_run("   ")
            except Exception:
                pass

    # ── Page break → Building Details ────────────────────────────────────
    doc.add_page_break()
    _add_section_heading(doc, 1, "Building Details")

    bldg = ctx["building"]
    cat = subcat = ""
    if bldg.category:
        cat = str(bldg.category.category) if bldg.category.category else ""
        subcat = str(bldg.category.subcategory) if bldg.category.subcategory else ""

    cert = "Yes" if bldg.has_certification else "No"
    boq_val = ", ".join(n for n, _ in ctx["boq_links"]) if ctx["boq_links"] else ("Yes" if bldg.has_boq else "No")

    details = [
        ("Building name or Code:", bldg.name),
        ("Address (Zip, Street):", ctx["address"]),
        ("Coordinates:", ctx["coords"]),
        ("Country:", str(bldg.country) if bldg.country else None),
        ("Region or State:", str(bldg.region) if bldg.region else None),
        ("City:", str(bldg.city) if bldg.city else None),
        ("Building type:", cat),
        ("Building sub-type:", subcat),
        ("Climate type:", str(bldg.climate_zone) if bldg.climate_zone else None),
        ("Life cycle assessment period:", f"{bldg.reference_period} years"),
        ("Construction year:", bldg.construction_year),
        ("Total floor area:", f"{bldg.total_floor_area} m²"),
        ("Conditioned floor area:", f"{bldg.cond_floor_area} m²" if bldg.cond_floor_area else None),
        ("Floors below ground:", bldg.floors_below_ground),
        ("Certification process:", cert),
        ("BoQ / design drawings:", boq_val),
    ]
    for label, value in details:
        _add_detail_row(doc, label, value)

    # ── Section 2: Whole Life Cycle Carbon Footprint Summary ─────────────────
    doc.add_page_break()
    _add_section_heading(doc, 2, "Whole Life Cycle Carbon Footprint Summary")

    doc.add_paragraph(
        "The whole life cycle carbon footprint of the building is expressed as a carbon intensity in "
        "kgCO₂eq per square metre of total floor area. It combines two distinct components: embodied carbon "
        "(the emissions associated with the manufacture, transport, and installation of building materials) and "
        "operational carbon (the emissions arising from energy consumed by building systems over the assessment "
        "period). It covers A1–A3 scope for embodied carbon and B6 for operational carbon."
    ).paragraph_format.space_after = Pt(10)

    # Callout box
    callout = doc.add_paragraph()
    callout.paragraph_format.left_indent = Cm(0.5)
    callout.paragraph_format.space_after = Pt(14)
    tcPr = callout._p.get_or_add_pPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "EFF6FF"); tcPr.append(shd)
    cr = callout.add_run("Carbon Footprint = Embodied Carbon + Operational Carbon    All figures are expressed as kgCO₂eq/m² over the full assessment period unless stated otherwise.")
    cr.font.size = Pt(9); cr.font.color.rgb = RGBColor(0x1D, 0x6F, 0xA8)

    # 2.1 Headline Metrics
    _add_section_heading(doc, "2.1", "Headline Metrics")
    metrics = [
        [("Carbon Footprint", f"{ctx['total_carbon']} kgCO₂eq/m²"),
         ("Total Floor Area", f"{int(bldg.total_floor_area):,} m²"),
         ("Assessment Period", f"{bldg.reference_period} years")],
        [("Embodied Carbon", f"{ctx['embodied_carbon']} kgCO₂eq/m²"),
         ("Operational Carbon", f"{ctx['operational_carbon']} kgCO₂eq/m²"),
         ("Carbon Savings", f"{ctx['savings_pct']} %")],
    ]
    mt = doc.add_table(rows=2, cols=3)
    mt.style = "Table Grid"
    fill_rows = ["EFF6FF", "FFFFFF"]
    for ri, row_data in enumerate(metrics):
        for ci, (lbl, val) in enumerate(row_data):
            cell = mt.rows[ri].cells[ci]
            lp = cell.paragraphs[0]
            lr = lp.add_run(lbl + "\n"); lr.font.size = Pt(8); lr.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
            vr = lp.add_run(val); vr.bold = True; vr.font.size = Pt(11)
            tcp = cell._tc.get_or_add_tcPr()
            s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), fill_rows[ri]); tcp.append(s)

    # 2.2 Whole Life Cycle Carbon — chart from captured card
    _add_section_heading(doc, "2.2", "Whole Life Cycle Carbon")
    doc.add_paragraph(
        "The dashboard below shows the split between embodied and operational carbon as a proportion of the "
        "total building carbon footprint, alongside a breakdown of embodied carbon by building assembly "
        "(structural elements, facades, finishes, etc.)."
    ).paragraph_format.space_after = Pt(8)

    # Embed donut card image
    if ctx.get("card_donut"):
        _add_b64_image(doc, ctx["card_donut"], Cm(8))
        cap = doc.add_paragraph("Figure 1 — Whole life carbon cycle of the building")
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.runs[0].font.size = Pt(8); cap.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80); cap.runs[0].font.italic = True

    # Narrative
    narrative = doc.add_paragraph()
    narrative.paragraph_format.space_before = Pt(8)
    for text, highlight in [
        (f"Operational carbon accounts for ", False),
        (f"{ctx['op_pct']}%", True),
        (f" of the total carbon footprint (", False),
        (f"{ctx['operational_carbon']} kgCO₂eq/m²", True),
        (f"), reflecting the dominant role of building energy systems over a ", False),
        (f"{bldg.reference_period}-year", True),
        (f" assessment period. Embodied carbon contributes the remaining ", False),
        (f"{ctx['em_pct']}%", True),
        (f" (", False),
        (f"{ctx['embodied_carbon']} kgCO₂eq/m²", True),
        (f") which underscores the importance of reducing embodied carbon, which carries significant weight in overall emissions—particularly those generated during the construction and renovation phases of a building. It is important to note that, unlike operational carbon, embodied carbon is released upfront, resulting in substantial emissions at the time a building is constructed or renovated.", False),
    ]:
        r = narrative.add_run(text)
        r.font.size = Pt(10)
        if highlight:
            r.font.highlight_color = 7  # yellow

    # ── Section 3: Embodied Carbon ────────────────────────────────────────────
    doc.add_page_break()
    _add_section_heading(doc, 3, "Embodied Carbon")
    doc.add_paragraph(
        "Embodied carbon covers the greenhouse gas emissions associated with raw material extraction, "
        "manufacturing, transportation, construction, maintenance, and end-of-life disposal of building "
        "materials. In BEAT, it is assessed across both building assemblies (structural systems, envelopes, "
        "finishes) and constituent materials."
    ).paragraph_format.space_after = Pt(12)

    # 3.1 by assembly
    _add_section_heading(doc, "3.1", "Embodied Carbon by Assembly")
    p31 = doc.add_paragraph()
    p31.paragraph_format.space_after = Pt(8)
    for text, highlight in [
        ("The chart below disaggregates the total embodied carbon intensity (", False),
        (f"{ctx['embodied_carbon']} kgCO₂eq/m²", True),
        (") by building component/assembly. Each bar represents a building component’s percentage share of the total embodied carbon. Only building components entered in the Bill of Quantities by users are included; the percentage distribution always sums to 100% across entered materials.", False),
    ]:
        r = p31.add_run(text); r.font.size = Pt(10)
        if highlight: r.font.highlight_color = 7

    if ctx.get("card_assembly"):
        _add_b64_image(doc, ctx["card_assembly"], Cm(11))
        cap = doc.add_paragraph("Figure 2 — Embodied carbon by Assemblies (assembly tab)")
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.runs[0].font.size = Pt(8); cap.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80); cap.runs[0].font.italic = True

    # 3.2 by material
    _add_section_heading(doc, "3.2", "Embodied Carbon by Material")
    p32 = doc.add_paragraph()
    p32.paragraph_format.space_after = Pt(8)
    for text, highlight in [
        ("The chart below disaggregates the total embodied carbon intensity (", False),
        (f"{ctx['embodied_carbon']} kgCO₂eq/m²", True),
        (") by material category. Each bar represents a material’s percentage share of the total embodied carbon. Only materials with quantities entered in the Bill of Quantities are included; the percentage distribution always sums to 100% across entered materials.", False),
    ]:
        r = p32.add_run(text); r.font.size = Pt(10)
        if highlight: r.font.highlight_color = 7

    if ctx.get("card_material"):
        _add_b64_image(doc, ctx["card_material"], Cm(11))
        cap = doc.add_paragraph("Figure 3 — Embodied carbon by material (Materials tab)")
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.runs[0].font.size = Pt(8); cap.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80); cap.runs[0].font.italic = True

    # Closing paragraph for section 3
    p3close = doc.add_paragraph()
    p3close.paragraph_format.space_before = Pt(10)
    p3close.paragraph_format.space_after = Pt(12)
    for text, highlight in [
        ("Rebar and ready-mix concrete together account for over ", False),
        ("81%", True),
        (" of total embodied carbon — a pattern typical of reinforced concrete-frame office buildings. "
         "Strategies to reduce this share include specifying low-carbon concrete mixes (", False),
        ("GGBS", True),
        (" or fly ash blends), using ", False),
        ("recycled-content", True),
        (" reinforcement, and minimising structural over-design.", False),
    ]:
        r = p3close.add_run(text); r.font.size = Pt(10)
        if highlight: r.font.highlight_color = 7

    # ── Section 4: Operational Carbon ────────────────────────────────────────
    doc.add_page_break()
    _add_section_heading(doc, 4, "Operational Carbon")
    doc.add_paragraph(
        "Operational carbon covers the greenhouse gas emissions arising from energy consumed by "
        "building systems during its use."
    ).paragraph_format.space_after = Pt(10)

    # Callout formula
    callout4 = doc.add_paragraph()
    callout4.paragraph_format.left_indent = Cm(0.5)
    callout4.paragraph_format.space_after = Pt(14)
    pPr4 = callout4._p.get_or_add_pPr()
    shd4 = OxmlElement("w:shd"); shd4.set(qn("w:val"), "clear"); shd4.set(qn("w:color"), "auto"); shd4.set(qn("w:fill"), "EFF6FF"); pPr4.append(shd4)
    cr4 = callout4.add_run("Formula: Carbon Intensity (kgCO₂eq/m²/yr) = Energyₐₚₚₗᴵₐₙ⁣ₑ (kWh/yr) × Gridₑₐ⁣ₜₒᴿ (kgCO₂eq/kWh) ÷ Floorₐᴿₑₐ (m²)")
    cr4.font.size = Pt(9); cr4.font.color.rgb = RGBColor(0x1D, 0x6F, 0xA8)

    _add_section_heading(doc, "4.1", "Operational Carbon by Appliances")
    doc.add_paragraph(
        "The Energy tab chart below shows operational carbon intensity broken down by building system "
        "(cooling, ventilation, lighting, hot water, lifts & escalators). Within each system, individual "
        "appliances are shown as sub-bars. Only appliances with energy data entered contribute to the totals; "
        "the percentage distribution always sums to 100% across entered appliances."
    ).paragraph_format.space_after = Pt(60)

    cap4 = doc.add_paragraph("Figure 4 — Operational carbon by system and appliance (Energy tab)")
    cap4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap4.runs[0].font.size = Pt(8); cap4.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80); cap4.runs[0].font.italic = True

    p41 = doc.add_paragraph()
    p41.paragraph_format.space_before = Pt(10)
    for text, highlight in [
        ("Cooling", True),
        (" is the dominant operational carbon contributor at ", False),
        ("43%", True),
        (", driven primarily by split AC units (", False),
        ("28%", True),
        (" of building total) and VRF systems (", False),
        ("13%", True),
        (").", False),
    ]:
        r = p41.add_run(text); r.font.size = Pt(10)
        if highlight: r.font.highlight_color = 7

    # ── Section 5: Benchmarking & Carbon Savings ──────────────────────────────
    doc.add_page_break()
    _add_section_heading(doc, 5, "Benchmarking & Carbon Savings")
    doc.add_paragraph(
        "The Savings tab compares the building's total carbon footprint against a peer benchmark for similar "
        "buildings in the same region, and presents targeted optimisation strategies ranked by potential "
        "carbon reduction. Each strategy shows a baseline value, a potential saving, and a brief description "
        "of the intervention required."
    ).paragraph_format.space_after = Pt(10)

    _add_section_heading(doc, "5.1", "Project Performance Benchmark")
    doc.add_paragraph(
        "The benchmark gauge below shows where this building sits relative to the best-practice and national "
        "average figures for comparable buildings. The position of the building marker on the scale indicates "
        "performance tier."
    ).paragraph_format.space_after = Pt(8)

    if ctx.get("card_savings"):
        _add_b64_image(doc, ctx["card_savings"], height=Cm(26))
        cap5 = doc.add_paragraph("Figure 5 — Project performance benchmark and carbon savings strategies (Savings tab)")
        cap5.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap5.runs[0].font.size = Pt(8); cap5.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80); cap5.runs[0].font.italic = True

    doc.add_page_break()
    _add_section_heading(doc, "5.2", "Benchmark Summary")

    # Benchmark metrics table
    bmt = doc.add_table(rows=1, cols=3)
    bmt.style = "Table Grid"
    bench_data = [
        ("Your building", f"{ctx['total_carbon']} kgCO₂eq/m²"),
        ("Best practice", "320 kgCO₂eq/m²"),
        ("National average", "640 kgCO₂eq/m²"),
    ]
    for ci, (lbl, val) in enumerate(bench_data):
        cell = bmt.rows[0].cells[ci]
        lp = cell.paragraphs[0]
        lr = lp.add_run(lbl + "\n"); lr.font.size = Pt(8); lr.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
        vr = lp.add_run(val); vr.bold = True; vr.font.size = Pt(11)
        tcp = cell._tc.get_or_add_tcPr()
        s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), "F3F4F6"); tcp.append(s)

    callout5 = doc.add_paragraph()
    callout5.paragraph_format.left_indent = Cm(0.5)
    callout5.paragraph_format.space_before = Pt(12)
    callout5.paragraph_format.space_after = Pt(14)
    pPr5 = callout5._p.get_or_add_pPr()
    shd5 = OxmlElement("w:shd"); shd5.set(qn("w:val"), "clear"); shd5.set(qn("w:color"), "auto"); shd5.set(qn("w:fill"), "EFF6FF"); pPr5.append(shd5)
    cr5 = callout5.add_run(
        "This building performs better than 78% of peer projects in Germany (452 residential projects, "
        "Baden-Württemberg, 2024–2025). It is rated in the Top 25% tier. Benchmark data is "
        "region- and building-type specific."
    )
    cr5.font.size = Pt(9); cr5.font.color.rgb = RGBColor(0x1D, 0x6F, 0xA8)

    # ── Section 5.3: Optimisation Strategies ─────────────────────────────────
    _add_section_heading(doc, "5.3", "Optimisation Strategies")
    doc.add_paragraph(
        "The following strategies are identified as the highest-impact opportunities for reducing embodied "
        "carbon, ordered by percentage of total footprint:"
    ).paragraph_format.space_after = Pt(8)

    opt_rows = [
        ("Strategy", "Potential saving / Notes", True),
        ("Ready-mix concrete & cement",
         "−40 kgCO₂eq/m²  (30% of total)  25% GGBS/Fly Ash blend → 139 → 104 kgCO₂eq/m²", False),
        ("Steel",
         "−20 kgCO₂eq/m²  (15% of total)  20% recycled content → 69 → 55 kgCO₂eq/m²", False),
        ("Reinforcement bar (rebar)",
         "−35 kgCO₂eq/m²  (15% of total)  Low-carbon rebar specification", False),
        ("Total potential embodied saving",
         "−85 kgCO₂eq/m²  (12.5% reduction from baseline)", True),
    ]
    opt_table = doc.add_table(rows=len(opt_rows), cols=2)
    opt_table.style = "Table Grid"
    fill_opt = ["F3F4F6", "FFFFFF", "F3F4F6", "FFFFFF", "F3F4F6"]
    for ri, (label, value, bold) in enumerate(opt_rows):
        row = opt_table.rows[ri]
        for ci, text in enumerate([label, value]):
            cell = row.cells[ci]
            p = cell.paragraphs[0]
            run = p.add_run(text)
            run.bold = bold
            run.font.size = Pt(10)
            tcp = cell._tc.get_or_add_tcPr()
            s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), fill_opt[ri]); tcp.append(s)

    closing = doc.add_paragraph()
    closing.paragraph_format.space_before = Pt(12)
    cr_close = closing.add_run(
        "Operational carbon savings are not yet modelled for this project. Recommended next steps include "
        "specifying higher-efficiency cooling equipment, exploring on-site renewable generation, and "
        "re-assessing the grid emission factor annually as the national grid decarbonises."
    )
    cr_close.font.size = Pt(10)
    cr_close.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    cr_close.font.italic = True

    return doc


@login_required
@require_http_methods(["POST"])
def export_building(request, building_id):
    building = get_object_or_404(Building, pk=building_id, created_by=request.user)
    fmt = request.POST.get("format", "pdf")
    ctx = _build_context(
        building, request,
        card_donut=request.POST.get("card_donut", ""),
        card_assembly=request.POST.get("card_assembly", ""),
        card_material=request.POST.get("card_material", ""),
        card_savings=request.POST.get("card_savings", ""),
    )
    filename_base = building.name.replace(" ", "_")

    if fmt == "word":
        doc = _build_docx(ctx)
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response["Content-Disposition"] = f'attachment; filename="BEAT_Report_{filename_base}.docx"'
        return response

    from xhtml2pdf import pisa
    html_content = _pdf_html(ctx)
    buffer = io.BytesIO()
    pisa.CreatePDF(html_content, dest=buffer, encoding="utf-8")
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="BEAT_Report_{filename_base}.pdf"'
    return response
