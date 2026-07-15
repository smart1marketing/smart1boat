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
- Never recommend social media or social advertising. Do not include Facebook, Instagram, TikTok, LinkedIn, Snapchat, Pinterest, X, or any other social channel.
- Allowed tactics include paid search, programmatic display, geofencing, location lookback, CTV/OTT, streaming audio, YouTube, site retargeting, email, SMS, and dealer CRM follow-up.
- Respect the requested weather-trigger mode. If the user selects a weather-trigger-only campaign, recommend triggerable media remain paused outside qualifying windows and explain which limited tactics, if any, should remain always-on.
- Build practical triggers around boating-friendly weather, such as temperature, rain probability, severe weather, wind, consecutive warm days, holiday/weekend forecasts, and seasonal first-warm-weekend opportunities.
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
            "methodology_note": {"type": "string"},
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
            "water_access_overview": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "waterway": {"type": "string"},
                        "type": {"type": "string"},
                        "communities_served": {"type": "array", "items": {"type": "string"}},
                        "boating_fit": {"type": "string"},
                        "seasonality": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": [
                        "waterway",
                        "type",
                        "communities_served",
                        "boating_fit",
                        "seasonality",
                        "confidence",
                    ],
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
            "zip_and_community_targets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "community": {"type": "string"},
                        "state": {"type": "string"},
                        "zip_codes": {"type": "array", "items": {"type": "string"}},
                        "priority": {"type": "integer", "enum": [1, 2, 3]},
                        "reason": {"type": "string"},
                        "recommended_audiences": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "community",
                        "state",
                        "zip_codes",
                        "priority",
                        "reason",
                        "recommended_audiences",
                    ],
                },
            },
            "audience_segments": {"type": "array", "items": {"type": "string"}},
            "recommended_budget": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "monthly_budget_range": {"type": "string"},
                    "recommended_starting_budget": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": [
                    "monthly_budget_range",
                    "recommended_starting_budget",
                    "rationale",
                ],
            },
            "weather_trigger_plan": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "strategy_summary": {"type": "string"},
                    "activation_mode": {"type": "string"},
                    "budget_efficiency_note": {"type": "string"},
                    "always_on_recommendation": {"type": "string"},
                    "triggers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "trigger_name": {"type": "string"},
                                "condition": {"type": "string"},
                                "action": {"type": "string"},
                                "lead_time": {"type": "string"},
                                "applicable_tactics": {"type": "array", "items": {"type": "string"}},
                                "reason": {"type": "string"},
                            },
                            "required": [
                                "trigger_name",
                                "condition",
                                "action",
                                "lead_time",
                                "applicable_tactics",
                                "reason",
                            ],
                        },
                    },
                },
                "required": [
                    "strategy_summary",
                    "activation_mode",
                    "budget_efficiency_note",
                    "always_on_recommendation",
                    "triggers",
                ],
            },
            "campaign_plan": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "tactic": {"type": "string"},
                        "budget_percent": {"type": "integer"},
                        "purpose": {"type": "string"},
                        "targeting": {"type": "string"},
                    },
                    "required": ["tactic", "budget_percent", "purpose", "targeting"],
                },
            },
            "sales_opportunities": {"type": "array", "items": {"type": "string"}},
            "disclaimer": {"type": "string"},
        },
        "required": [
            "market_summary",
            "methodology_note",
            "market_profile",
            "water_access_overview",
            "geofence_locations",
            "zip_and_community_targets",
            "audience_segments",
            "recommended_budget",
            "weather_trigger_plan",
            "campaign_plan",
            "sales_opportunities",
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
        "target_markets",
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
        "\nBuild a Boat Dealer Market Intelligence & Geofencing Report from these inputs:\n"
        f"{json.dumps(payload, indent=2)}"
        "\n\nThe dealer did NOT provide a boating season, a media budget, weather preferences, a "
        "trigger lead time, or lists of local waterways and competitors. You must supply all of "
        "these yourself:\n"
        "- Assume the boating season and its length from the dealer's ZIP code and region. Do not ask.\n"
        "- The dealer did not give a budget. In recommended_budget, suggest an appropriate monthly "
        "media budget range and a specific recommended starting budget for this market, and explain "
        "your reasoning based on market size, competition, season length, and the number of high-value "
        "geofences.\n"
        "- Always build a weather-triggered media strategy (weather-enhanced pacing that shifts more "
        "budget into favorable boating weekends and pulls back during severe weather). Treat weather "
        "triggers as enabled and populate weather_trigger_plan with real triggers.\n"
        "- Assume the best trigger lead time for each tactic.\n"
        "- Identify the local lakes, rivers, reservoirs, bays, public ramps, marinas, storage/service "
        "facilities, marine retailers, boat shows, and competing boat dealers yourself from geographic "
        "knowledge of the market, and include them in water_access_overview and geofence_locations.\n\n"
        "Return 18-30 geofence locations when the market size reasonably supports it. "
        "Include a mix of boating access, marinas, storage/service, competitors, marine retail, "
        "and event venues. Prioritize locations inside the target radius and clearly lower "
        "confidence for uncertain locations.\n"
        "The ownership rates must be decimals expressed as percentages, such as 7.5 for 7.5 "
        "percent—not 0.075.\n"
        "Campaign budget percentages must total 100.\n"
        "Do not include social media or social advertising in the campaign plan or any recommendation.\n"
    )
    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text={"format": {"type": "json_schema", **REPORT_SCHEMA}},
        temperature=0.25,
        max_output_tokens=11000,
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
