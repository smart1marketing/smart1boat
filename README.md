# Smart 1 Boat Dealer Market Intelligence

A multi-step Smart 1 Marketing lead tool for boat dealers. It creates an AI planning report with:

- Ranked boating-access and conquest geofences
- Marinas, launches, storage/service, marine retail, event venues, and competitors
- Estimated target-area population and households
- Low/base/high estimate of likely boat-owner households
- Waterway and lake-community overview
- Priority ZIP/community targets
- Audience segments and media-budget allocation
- Weather-trigger budget plan
- Smart 1 Suite webhook payload
- Print-to-PDF report

## Important limitation

This version intentionally uses AI planning estimates instead of paid maps, geocoding, census, or state registration APIs. It does not claim live verification. Before media activation, a strategist should verify each physical location and build the final polygons in the advertising platform.

## Project structure

```
smart1boat/
├── app.py               # Flask backend + OpenAI report generation + webhook
├── templates/
│   └── index.html       # Self-contained multi-step form (CSS + JS inlined)
├── requirements.txt
├── Procfile
├── render.yaml
├── .env.example
└── .gitignore
```

`index.html` lives in `templates/` because the backend serves it with Flask's
`render_template("index.html")`. The page is intentionally self-contained: all
CSS and JavaScript are inlined, so there are no separate `styles.css` or `app.js`
files to keep in sync. This keeps the form reliable when embedded in Smart 1 Suite.

> Do not commit compiled artifacts (`__pycache__/`, `*.pyc`). They are ignored in
> `.gitignore`. Edit and deploy `app.py`, not any compiled `.pyc`.

## Deploy to GitHub

1. Create a new GitHub repository named `smart1boat`.
2. Upload every file and folder in this project. Keep the folder structure intact (especially `templates/`).
3. Do not upload a real `.env` file or API key.

## Deploy to Render

1. In Render, choose **New + > Blueprint**.
2. Connect the `smart1boat` GitHub repository.
3. Render will read `render.yaml`.
4. Add the secret environment variable `OPENAI_API_KEY`.
5. Add `GHL_WEBHOOK_URL` for the Go High Level (Smart1Suite) inbound webhook.
6. Add `CLOUDINARY_URL` (from your Cloudinary dashboard) so generated PDF reports are stored there.
7. Add `PUBLIC_BASE_URL` = your public app URL (e.g. `https://smart1boat.onrender.com`) so report links are absolute.
8. Keep `OPENAI_MODEL` at the default or change it to a model available in your OpenAI account.
9. Confirm the Start Command includes `--timeout 300` (report generation runs long).
10. Deploy and test `/health`, then test the full form.

### Environment variables (Render)

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | OpenAI key that generates the report |
| `OPENAI_MODEL` | no (default `gpt-4.1-mini`) | model used |
| `GHL_WEBHOOK_URL` | yes | Go High Level inbound webhook the lead + report is posted to |
| `CLOUDINARY_URL` | yes (for PDF storage) | Cloudinary credentials; generated PDFs are uploaded here |
| `PUBLIC_BASE_URL` | recommended | public app URL used to build report links |

On each submission the app generates a branded **PDF** of the report, uploads it to Cloudinary
under `boat-reports/<dealer-slug>-boat-report-<id>.pdf`, and includes both `report_url`
(interactive) and `report_pdf_url` (the Cloudinary PDF) in the webhook payload.

## Smart 1 Suite fields

Recommended custom fields:

- Dealer Name
- Dealer Website
- Dealer ZIP
- Target Radius
- Target Markets
- Boat Types
- Inventory Mix
- Campaign Objective
- Monthly Budget
- Seasonality
- Known Waterways
- Known Competitors
- Notes
- Estimated Boat Owner Households
- Boat Market Summary
- Boat Report Status
- Boat Report JSON (large text field, optional)

The webhook sends human-readable fields plus `report_json`. If the Suite webhook ignores nested or large data, map the summary and estimated-owner fields first and store the full report externally or in a large-text custom field.

## Embed on Smart 1 Suite

The easiest reliable method is an iframe pointing to the Render URL:

```html
<iframe
  src="https://YOUR-RENDER-URL.onrender.com/"
  style="width:100%;min-height:1200px;border:0;border-radius:12px;"
  loading="lazy"
  title="Boat Dealer Market Intelligence">
</iframe>
```

Using an iframe keeps the JavaScript and API request on the same Render domain and avoids cross-origin and code-block restrictions inside Smart 1 Suite.

## Test locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://localhost:5000`.

## Weather-trigger targeting

The form supports three weather modes: no weather triggers, weather-enhanced pacing, and weather-trigger-only activation. Reports include suggested conditions, activation or suppression actions, lead time, applicable non-social tactics, and a budget-efficiency explanation. Social advertising is intentionally excluded from recommendations.
