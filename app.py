import datetime
import json
import os
import re
import tempfile
import uuid
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

try:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(secure=True)  # reads CLOUDINARY_URL from the environment
    CLOUDINARY_READY = bool(os.getenv("CLOUDINARY_URL", "").strip())
except Exception:  # pragma: no cover
    cloudinary = None
    CLOUDINARY_READY = False

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    from fpdf.fonts import FontFace
    FPDF_READY = True
except Exception:  # pragma: no cover
    FPDF_READY = False

load_dotenv()

app = Flask(__name__)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
# Standardized on GHL_WEBHOOK_URL (falls back to the old SMART1_WEBHOOK_URL if present).
WEBHOOK_URL = (os.getenv("GHL_WEBHOOK_URL", "") or os.getenv("SMART1_WEBHOOK_URL", "")).strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")

REPORTS_DIR = os.path.join(tempfile.gettempdir(), "smart1boat_reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return s or "dealership"


def _pdf_text(s: Any) -> str:
    """Sanitize text for the core-font PDF (latin-1)."""
    s = "" if s is None else str(s)
    for a, b in {"—": "-", "–": "-", "‘": "'", "’": "'",
                 "“": '"', "”": '"', "…": "...", "•": "-",
                 " ": " ", "→": ">"}.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def save_report(report: Any, dealer_name: str) -> str:
    rid = uuid.uuid4().hex[:12]
    with open(os.path.join(REPORTS_DIR, f"{rid}.json"), "w") as f:
        json.dump({"report": report, "dealer_name": dealer_name}, f)
    return rid


def base_url() -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    base = request.url_root.rstrip("/")
    if base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return base


NAVY = (10, 34, 64)
BLUE = (0, 158, 210)
GREY = (92, 107, 126)


def build_pdf(report: Any, dealer_name: str) -> str:
    """Render the report into a branded PDF and return the local file path."""
    r = report or {}
    m = r.get("market_profile", {}) or {}
    pkg = r.get("recommended_package", {}) or {}
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin

    def fmt(n):
        try:
            return f"{int(n):,}"
        except Exception:
            return str(n)

    def h3(txt):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*NAVY)
        pdf.multi_cell(W, 7, _pdf_text(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y = pdf.get_y() + 1
        pdf.set_draw_color(*BLUE)
        pdf.set_line_width(0.6)
        pdf.line(pdf.l_margin, y, pdf.l_margin + 20, y)
        pdf.ln(3)

    def body(txt):
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_text_color(45, 50, 60)
        pdf.multi_cell(W, 5.6, _pdf_text(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def bullets(items):
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_text_color(45, 50, 60)
        for it in (items or []):
            pdf.multi_cell(W, 5.6, _pdf_text("- " + str(it)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Header
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(W, 10, _pdf_text(dealer_name or "Boat Dealer"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*BLUE)
    pdf.multi_cell(W, 7, "Weather Marketing Proposal", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(W, 5, _pdf_text("Prepared by Smart 1 Marketing  -  " + datetime.date.today().strftime("%B %d, %Y")),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    if r.get("market_type"):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(*NAVY)
        pdf.cell(0, 8, _pdf_text("  " + r.get("market_type", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        pdf.ln(1)
    if r.get("market_type_description"):
        body(r.get("market_type_description"))
    if r.get("market_summary"):
        pdf.ln(1)
        body(r.get("market_summary"))

    # Stat cards
    h3("Market Estimate")
    stats = [
        (f"{fmt(m.get('estimated_population_low'))}-{fmt(m.get('estimated_population_high'))}", "Estimated population"),
        (f"{fmt(m.get('estimated_households_low'))}-{fmt(m.get('estimated_households_high'))}", "Estimated households"),
        (f"{fmt(m.get('estimated_boat_owner_households_low'))}-{fmt(m.get('estimated_boat_owner_households_high'))}", "Likely boat-owner households"),
    ]
    cw = W / 3
    pdf.set_fill_color(244, 249, 251)
    y0 = pdf.get_y()
    for i, (big, lbl) in enumerate(stats):
        x = pdf.l_margin + i * cw
        pdf.set_xy(x, y0)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*NAVY)
        pdf.cell(cw - 3, 9, _pdf_text(big), border=0, align="C", fill=True)
    pdf.ln(9)
    for i, (big, lbl) in enumerate(stats):
        x = pdf.l_margin + i * cw
        pdf.set_xy(x, pdf.get_y())
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(cw - 3, 4, _pdf_text(lbl), align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(9)

    if r.get("market_opportunity"):
        h3("Your Market Opportunity")
        body(r.get("market_opportunity"))

    h3("Recommended Package")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(W, 6, _pdf_text(f"{pkg.get('monthly_investment','')} {pkg.get('package_name','')}"),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if pkg.get("description"):
        body(pkg.get("description"))
    body("Budget paces with your season: full package at peak, ~35% in shoulder months, 20% in the off-season.")

    if r.get("media_channels"):
        h3("Recommended Media Channels")
        bullets(r.get("media_channels"))
    if r.get("streaming_audio_note"):
        h3("Streaming Audio - Water-Access Daypart")
        body(r.get("streaming_audio_note"))
    if r.get("weather_triggers"):
        h3("Recommended Weather Triggers")
        body(", ".join(str(x) for x in r.get("weather_triggers", [])))

    # Month-by-month
    mp = r.get("monthly_plan") or []
    if mp:
        h3("Month-by-Month Campaign Plan")
        head = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=NAVY)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(45, 50, 60)
        pdf.set_draw_color(215, 230, 239)
        with pdf.table(headings_style=head, col_widths=(16, 60, 24), text_align="LEFT", first_row_as_headings=True) as t:
            t.row(["Month", "Focus & Message", "Budget"])
            for row in mp:
                focus = _pdf_text(str(row.get("focus", "")))
                msg = _pdf_text(str(row.get("message", "")))
                t.row([_pdf_text(row.get("month", "")), focus + ("\n" + msg if msg else ""), _pdf_text(row.get("pacing", ""))])

    # Geofences
    geo = sorted(r.get("geofence_locations") or [], key=lambda x: x.get("priority", 3))
    if geo:
        h3("Recommended Geofence Locations")
        head = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=NAVY)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(45, 50, 60)
        pdf.set_draw_color(215, 230, 239)
        with pdf.table(headings_style=head, col_widths=(8, 40, 26, 22, 12), text_align="LEFT", first_row_as_headings=True) as t:
            t.row(["P", "Location", "Category", "Method", "Radius"])
            for x in geo:
                t.row([
                    _pdf_text("P" + str(x.get("priority", ""))),
                    _pdf_text(f"{x.get('name','')}\n{x.get('city_state','')}"),
                    _pdf_text(x.get("category", "")),
                    _pdf_text(str(x.get("recommended_method", "")).replace("_", " ")),
                    _pdf_text(f"{x.get('recommended_radius_miles','')} mi"),
                ])

    if r.get("disclaimer"):
        pdf.ln(3)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(W, 4.5, _pdf_text(r.get("disclaimer")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    path = os.path.join(tempfile.gettempdir(), f"boat-report-{uuid.uuid4().hex[:10]}.pdf")
    pdf.output(path)
    return path


def upload_report_pdf(path: str, dealer_name: str, rid: str) -> str:
    """Upload the PDF to Cloudinary and return its secure delivery URL."""
    if not (cloudinary and CLOUDINARY_READY):
        return ""
    public_id = f"boat-reports/{slugify(dealer_name)}-boat-report-{rid}"
    res = cloudinary.uploader.upload(
        path,
        public_id=public_id,
        resource_type="auto",
        overwrite=True,
        use_filename=False,
        unique_filename=False,
    )
    return res.get("secure_url", "")


SYSTEM_PROMPT = """
You are the Smart 1 Marketing Boat Dealer Market Intelligence Architect.
Create a practical, sales-oriented market and geofencing report for a boat dealership.

IMPORTANT ACCURACY RULES
- You do not have live access to maps, state boat-registration databases, or exact census tables unless supplied in the request.
- Use geographic knowledge and conservative planning assumptions. Never claim a location or statistic was live-verified.
- Clearly label all population, household, boat-owner, and registration figures as AI planning estimates.
- Give ranges, confidence levels, and a short explanation of the assumptions.
- Do not invent precise street addresses. Use recognizable place names plus city/state. An address field may be null.
- Prefer real, well-known waterways and boating facilities you are reasonably confident exist. If uncertain, lower confidence.
- Avoid duplicate locations and avoid recommending open water polygons that cannot be practically geofenced. Favor access points and businesses.

TARGET TYPES TO CONSIDER
1. Public boat ramps and launch facilities
2. Marinas and yacht clubs
3. Major lakes, reservoirs, navigable rivers, bays, and coastal access zones
4. Boat storage, dry-stack storage, winterization, repair, fuel docks, and marine-service facilities
5. Fishing tackle, watersports, marine-supply, and boating-event locations
6. Competing boat dealers and boat-show venues for conquesting
7. Affluent/high-homeownership ZIP clusters close to boating access
8. Seasonal tourism corridors and lake communities

BOAT-OWNER ESTIMATION METHOD
Estimate the adult population and households in the requested market, then estimate likely boat-owning households using a market-sensitive ownership rate. Use lower rates for dense urban inland areas, moderate rates for lake/river markets, and higher rates for coastal or lake-heavy markets. Adjust for income, homeownership, vehicle/trailer storage capacity, nearby navigable water, fishing culture, seasonality, and requested boat categories.
Return low/base/high ownership estimates. Do not present the estimate as registered-vessel data.

GEOFENCE GUIDANCE
- Recommend a practical radius or polygon approach for each location.
- Typical point-of-interest radii: 0.10-0.25 mile for compact ramps/dealers, 0.25-0.50 mile for marinas/storage, and polygons for larger venues.
- Separate "location lookback" sites from "real-time/proximity" sites.
- Rank locations Priority 1, 2, or 3.

MEDIA AND WEATHER-TRIGGER RULES
- The entire campaign is weather-triggered. Build the plan around boating-friendly weather signals.
- ALLOWED channels ONLY: geofencing, location look-back retargeting, programmatic / data-driven targeted display, CTV/OTT, streaming audio, YouTube/online video, and website retargeting.
- NEVER recommend social media or social advertising (Facebook, Instagram, TikTok, LinkedIn, Snapchat, Pinterest, X, or any other social channel).
- NEVER recommend paid search, email, or SMS. Do not mention them anywhere in the report.
- Build practical triggers around boating-friendly weather, such as temperature thresholds, rain probability, severe weather, wind, consecutive warm days, holiday/weekend forecasts, first-warm-weekend and end-of-season opportunities, first frost, and freeze/winterization warnings.
- Keep weather-trigger labels short and punchy (e.g. "70°+ weekend", "Sunny weekend", "First frost", "Freeze warning", "Holiday weekend forecast").
- Do not imply that weather guarantees demand. Treat it as a budget-pacing and timing signal.

OUTPUT
Return only valid JSON matching the requested schema. Do not use markdown fences.
"""

REPORT_SCHEMA = {
    "name": "boat_dealer_report",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "market_summary": {"type": "string"},
            "market_type": {"type": "string"},
            "market_type_description": {"type": "string"},
            "market_opportunity": {"type": "string"},
            "market_profile": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "estimated_population_low": {"type": "integer"},
                    "estimated_population_base": {"type": "integer"},
                    "estimated_population_high": {"type": "integer"},
                    "estimated_households_low": {"type": "integer"},
                    "estimated_households_base": {"type": "integer"},
                    "estimated_households_high": {"type": "integer"},
                    "estimated_boat_owner_households_low": {"type": "integer"},
                    "estimated_boat_owner_households_base": {"type": "integer"},
                    "estimated_boat_owner_households_high": {"type": "integer"},
                    "estimated_ownership_rate_low": {"type": "number"},
                    "estimated_ownership_rate_base": {"type": "number"},
                    "estimated_ownership_rate_high": {"type": "number"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "estimated_population_low",
                    "estimated_population_base",
                    "estimated_population_high",
                    "estimated_households_low",
                    "estimated_households_base",
                    "estimated_households_high",
                    "estimated_boat_owner_households_low",
                    "estimated_boat_owner_households_base",
                    "estimated_boat_owner_households_high",
                    "estimated_ownership_rate_low",
                    "estimated_ownership_rate_base",
                    "estimated_ownership_rate_high",
                    "confidence",
                    "assumptions",
                ],
            },
            "recommended_package": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "package_name": {"type": "string"},
                    "monthly_investment": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["package_name", "monthly_investment", "description"],
            },
            "media_channels": {"type": "array", "items": {"type": "string"}},
            "streaming_audio_note": {"type": "string"},
            "weather_triggers": {"type": "array", "items": {"type": "string"}},
            "monthly_plan": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "month": {"type": "string"},
                        "focus": {"type": "string"},
                        "message": {"type": "string"},
                        "triggers": {"type": "array", "items": {"type": "string"}},
                        "pacing": {"type": "string"},
                    },
                    "required": ["month", "focus", "message", "triggers", "pacing"],
                },
            },
            "geofence_locations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "city_state": {"type": "string"},
                        "address": {"type": ["string", "null"]},
                        "category": {"type": "string"},
                        "waterway_or_market": {"type": "string"},
                        "priority": {"type": "integer", "enum": [1, 2, 3]},
                        "recommended_method": {
                            "type": "string",
                            "enum": ["location_lookback", "real_time_proximity", "both"],
                        },
                        "recommended_radius_miles": {"type": "number"},
                        "audience_reason": {"type": "string"},
                        "best_message": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": [
                        "name",
                        "city_state",
                        "address",
                        "category",
                        "waterway_or_market",
                        "priority",
                        "recommended_method",
                        "recommended_radius_miles",
                        "audience_reason",
                        "best_message",
                        "confidence",
                    ],
                },
            },
            "disclaimer": {"type": "string"},
        },
        "required": [
            "market_summary",
            "market_type",
            "market_type_description",
            "market_opportunity",
            "market_profile",
            "recommended_package",
            "media_channels",
            "streaming_audio_note",
            "weather_triggers",
            "monthly_plan",
            "geofence_locations",
            "disclaimer",
        ],
    },
    "strict": True,
}


def clean_payload(data: dict) -> dict:
    fields = [
        "dealer_name",
        "website",
        "dealer_zip",
        "target_radius",
        "boat_types",
        "new_used",
        "campaign_objective",
        "contact_name",
        "contact_email",
        "contact_phone",
        "notes",
    ]
    cleaned = {k: str(data.get(k, "")).strip()[:1500] for k in fields}
    if not re.fullmatch(r"\d{5}(-\d{4})?", cleaned["dealer_zip"]):
        raise ValueError("A valid U.S. ZIP code is required.")
    return cleaned


def generate_report(payload: dict) -> Any:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    client = OpenAI(api_key=api_key)
    user_prompt = (
        "\nBuild a weather-triggered Boat Dealer Demand & Geofencing Report from these inputs:\n"
        f"{json.dumps(payload, indent=2)}"
        "\n\nThe dealer did NOT provide a boating season, a media budget, weather preferences, or "
        "lists of local waterways and competitors. You must supply all of these yourself:\n"
        "- Assume the boating season and its length from the dealer's ZIP code and region.\n"
        "- Identify the local lakes, rivers, reservoirs, bays, public ramps, marinas, storage/service "
        "facilities, marine retailers, boat shows, and competing boat dealers yourself from geographic "
        "knowledge of the market, and include the best of them in geofence_locations.\n\n"
        "Populate every field of the schema:\n"
        "- market_summary: one or two sentences framing the weather-triggered boating demand opportunity "
        "for this dealer and market (reference the dealer name and area).\n"
        "- market_type: a short badge label for the market, e.g. 'Northern / Seasonal Inland Lake Market' "
        "or 'Coastal / Year-Round Saltwater Market'. market_type_description: one sentence on the seasonal pattern.\n"
        "- market_profile: low/base/high estimates for population, households, and likely boat-owner households, "
        "plus ownership rate (as a percentage decimal such as 7.5, not 0.075), confidence, and assumptions.\n"
        "- market_opportunity: keep this SIMPLE — one short, plain sentence on the dealer's opportunity in this market.\n"
        "- recommended_package: choose the best-fit package for this market from the Smart 1 package menu below. "
        "Use its exact NAME and monthly price as monthly_investment (e.g. '$5,000/month'), and write a short description of what that level buys. "
        "Pick the tier based on market size, competition, and season length.\n"
        "  SMART 1 PACKAGE MENU (use these, do not invent prices):\n"
        "    * $2,500/month — Harbor Starter\n"
        "    * $5,000/month — SmartForecast Ads\n"
        "    * $7,500/month — Season Surge Plan\n"
        "    * $10,000/month — Full Fleet Dominance\n"
        "- media_channels: ALLOWED channels/data only. ALWAYS include 'In-Market Boat Buyer Audience Data' as one of the "
        "chips (we layer third-party in-market boat-shopper data across the plan). Then choose from: geofencing "
        "marinas/ramps & state parks, location look-back retargeting, data-driven / programmatic targeted display, connected "
        "TV (CTV/OTT), streaming audio, YouTube/online video, website retargeting. Return 4-7 chips total. NEVER include paid "
        "search, email, SMS, or any social channel.\n"
        "- streaming_audio_note: a short recommendation to geotarget streaming audio (streaming radio) around "
        "water-access areas (marinas, boat ramps, lakes, launch points) because boaters stream audio on the water. "
        "Specify a sunrise-to-sunset daypart running on boating-favorable days/weekends.\n"
        "- weather_triggers: 5-8 short trigger labels for this market (e.g. '70°+ weekend', 'Sunny weekend', "
        "'First frost', 'Freeze warning', 'Holiday weekend forecast').\n"
        "- monthly_plan: all 12 months (January through December). Each month has a focus title, a short customer-facing "
        "message, 1-2 relevant weather trigger labels drawn from weather_triggers, and a 'pacing' string. Match focus to the "
        "season (spring/summer = sales & boating demand, fall = end-of-season & winterization, winter = storage/service & "
        "early-order/boat-show).\n"
        "  BUDGET PACING RULE for the 'pacing' field: the recommended_package monthly_investment is the PEAK / in-season "
        "monthly budget (100%). In shoulder-season months spend 35% of the package; in off-season months spend 20% of the "
        "package. Classify each month as Peak, Shoulder, or Off-season based on this market's boating season, and set pacing "
        "to a short string with the tier, percent, and computed dollar amount — e.g. 'Peak — 100% ($5,000)', "
        "'Shoulder — 35% ($1,750)', 'Off-season — 20% ($1,000)'. Compute the dollars from the chosen package price.\n"
        "- geofence_locations: 12-18 locations (boating access, marinas, storage/service, competitors, marine retail, "
        "event venues). Prioritize locations inside the target radius; lower confidence for uncertain ones. Keep text concise.\n"
        "- disclaimer: a short note that figures are AI planning estimates for the market, not exact counts.\n"
    )
    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text={"format": {"type": "json_schema", **REPORT_SCHEMA}},
        temperature=0.25,
        max_output_tokens=8000,
    )
    text = (response.output_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def send_webhook(payload: dict, report: Any, status: str, report_url: str = "", report_pdf_url: str = "") -> None:
    if not WEBHOOK_URL:
        return
    rep = report or {}
    pkg = rep.get("recommended_package", {}) or {}
    full_name = (payload.get("contact_name") or "").strip()
    first_name, _, last_name = full_name.partition(" ")
    market_type = (rep.get("market_type") or "").strip()
    package_name = (pkg.get("package_name") or "").strip()
    body = {
        **payload,
        "contact_first_name": first_name,
        "contact_last_name": last_name,
        "source": "Smart 1 Boat Dealer Market Intelligence",
        "report_status": status,
        "opportunity_name": f"{payload.get('dealer_name', '').strip()} — Weather Marketing Proposal".strip(" —"),
        "market_type": market_type,
        # Ready-to-use CRM tags for auto-segmentation (map these to GHL "Add Tag" actions):
        "market_tag": (f"Boat - {market_type}" if market_type else "Boat - Lead"),
        "package_tag": (f"Boat - {package_name}" if package_name else ""),
        "estimated_boat_owner_households_base": rep.get("market_profile", {}).get(
            "estimated_boat_owner_households_base"
        ),
        "recommended_package": package_name,
        "recommended_monthly_investment": pkg.get("monthly_investment", ""),
        "market_summary": rep.get("market_summary", ""),
        "report_url": report_url or "",
        "report_pdf_url": report_pdf_url or "",
        "report_json": json.dumps(rep, separators=(",", ":"))[:60000],
    }
    try:
        requests.post(WEBHOOK_URL, json=body, timeout=12)
    except requests.RequestException:
        app.logger.exception("Webhook delivery failed")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/report/<rid>")
def get_report(rid: str):
    if not re.fullmatch(r"[a-f0-9]{12}", rid or ""):
        return jsonify({"ok": False, "error": "Not found"}), 404
    path = os.path.join(REPORTS_DIR, f"{rid}.json")
    if not os.path.exists(path):
        return jsonify({"ok": False, "error": "This report link is no longer available."}), 404
    with open(path) as f:
        data = json.load(f)
    return jsonify({"ok": True, "report": data["report"], "dealer_name": data.get("dealer_name", "")})


@app.post("/api/analyze")
def analyze():
    try:
        data = request.get_json(silent=True) or {}
        # Honeypot: real users never fill this hidden field; bots do. Block silently.
        if (data.get("company_website") or "").strip():
            return jsonify({"ok": False, "error": "Submission could not be processed."}), 400
        payload = clean_payload(data)
        report = generate_report(payload)
        rid = save_report(report, payload.get("dealer_name", ""))
        report_url = f"{base_url()}/?r={rid}"
        report_pdf_url = ""
        if FPDF_READY:
            try:
                pdf_path = build_pdf(report, payload.get("dealer_name", ""))
                report_pdf_url = upload_report_pdf(pdf_path, payload.get("dealer_name", ""), rid)
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass
            except Exception:
                app.logger.exception("PDF generation/upload failed")
        send_webhook(payload, report, "completed", report_url, report_pdf_url)
        return jsonify({"ok": True, "report": report, "report_url": report_url, "report_pdf_url": report_pdf_url})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Analysis failed")
        try:
            send_webhook(clean_payload(request.get_json(silent=True) or {}), None, "failed")
        except Exception:
            pass
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Sorry — we couldn't generate your report just now. Please try again in a moment.",
                }
            ),
            500,
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
