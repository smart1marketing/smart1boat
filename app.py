import json
import os
import re
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
WEBHOOK_URL = os.getenv("SMART1_WEBHOOK_URL", "").strip()

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
        "    * $5,000/month — Climate Safeguard Fund\n"
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


def send_webhook(payload: dict, report: Any, status: str) -> None:
    if not WEBHOOK_URL:
        return
    body = {
        **payload,
        "source": "Smart 1 Boat Dealer Market Intelligence",
        "report_status": status,
        "estimated_boat_owner_households_base": (report or {})
        .get("market_profile", {})
        .get("estimated_boat_owner_households_base"),
        "market_summary": (report or {}).get("market_summary", ""),
        "report_json": json.dumps(report or {}, separators=(",", ":"))[:60000],
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


@app.post("/api/analyze")
def analyze():
    try:
        payload = clean_payload(request.get_json(silent=True) or {})
        report = generate_report(payload)
        send_webhook(payload, report, "completed")
        return jsonify({"ok": True, "report": report})
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
                    "error": "The report could not be generated. Check the server configuration and try again.",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            ),
            500,
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
