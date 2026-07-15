# smart1rv

Smart RV Demand Package estimator for Smart 1 Marketing.

This project creates a multi-step embedded form for RV dealers. The form collects dealer information, creates an AI-generated campground market estimate, and sends the full lead payload into Smart 1 Suite through a webhook.

## What this version does

- Collects RV dealer contact details
- Collects dealer address and website URL
- Collects buyer and service travel radius
- Collects campaign goals and weather-trigger selections
- Uses OpenAI to estimate:
  - Campgrounds/RV parks in the market
  - Estimated RV/camping sites
  - Estimated peak-season camper reach
  - Recommended package
  - Recommended weather triggers
  - Month-by-month campaign plan
- Sends all form data and AI-estimated fields to Smart 1 Suite via webhook
- Lets Smart 1 Suite handle document generation and email follow-up

## Important estimate disclaimer

This version does not use Google Maps, Google Places, OpenStreetMap, or paid ZIP-radius APIs. The campground count and camper reach are AI-generated planning estimates based on the dealership location, ZIP code, state, radius, and standard market assumptions. They should not be presented as audited counts.

---

## Project structure

```txt
smart1rv/
  server.js              # Express backend
  package.json           # Node dependencies and scripts
  render.yaml            # Optional Render Blueprint config
  .env.example           # Environment variable template
  public/
    index.html           # Full working form page
    styles.css           # Form styling
    script.js            # Form behavior and API calls
```

---

## Local setup

1. Install dependencies:

```bash
npm install
```

2. Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

3. Add your environment variables:

```env
OPENAI_API_KEY=sk-your-openai-key
SMART1_SUITE_WEBHOOK_URL=https://your-smart-1-suite-webhook-url
OPENAI_MODEL=gpt-4o-mini
ALLOWED_ORIGINS=http://localhost:3000
NODE_ENV=development
```

4. Start the server:

```bash
npm start
```

5. Open the local form:

```txt
http://localhost:3000
```

6. Test the health endpoint:

```txt
http://localhost:3000/health
```

---

# Render deployment instructions

## Option A: Deploy from GitHub manually

### 1. Create GitHub repository

Create a new GitHub repository named:

```txt
smart1rv
```

Push these project files to that repository.

### 2. Create a new Render Web Service

In Render:

1. Click **New +**
2. Choose **Web Service**
3. Connect your GitHub account if needed
4. Select the `smart1rv` repository
5. Use these settings:

```txt
Name: smart1rv
Runtime: Node
Branch: main
Root Directory: leave blank
Build Command: npm install
Start Command: npm start
Instance Type: Starter or higher
```

### 3. Add environment variables in Render

Go to the Render service → **Environment** and add:

```txt
OPENAI_API_KEY=your OpenAI API key
SMART1_SUITE_WEBHOOK_URL=your Smart 1 Suite webhook URL
OPENAI_MODEL=gpt-4o-mini
NODE_ENV=production
ALLOWED_ORIGINS=https://your-smart1-site-domain.com,https://www.your-smart1-site-domain.com
```

For initial testing, you can temporarily leave `ALLOWED_ORIGINS` blank. Blank allows requests from any origin. After testing, lock it down to the Smart 1 Sites domain where the form is embedded.

### 4. Deploy

Click **Create Web Service**. Render will install dependencies and start the app.

### 5. Confirm deployment

After deploy, open:

```txt
https://smart1rv.onrender.com/health
```

You should see:

```json
{
  "ok": true,
  "service": "smart1rv",
  "timestamp": "..."
}
```

### 6. Test the hosted form

Open:

```txt
https://smart1rv.onrender.com
```

Fill out the form and confirm the lead arrives in Smart 1 Suite.

---

## Option B: Deploy with render.yaml Blueprint

This repo includes `render.yaml`.

In Render:

1. Click **New +**
2. Choose **Blueprint**
3. Connect the `smart1rv` repository
4. Render will read `render.yaml`
5. Add the required secret values when prompted:
   - `OPENAI_API_KEY`
   - `SMART1_SUITE_WEBHOOK_URL`
   - `ALLOWED_ORIGINS`
6. Deploy

---

# Embedding in Smart 1 Sites

You have two options.

## Option 1: Embed with iframe

This is the easiest version.

```html
<iframe
  src="https://smart1rv.onrender.com"
  style="width:100%; min-height:1050px; border:0;"
  loading="lazy">
</iframe>
```

Pros:

- Fastest setup
- No CORS issues
- Keeps all form assets hosted on Render

Cons:

- Styling is inside iframe
- Height may need adjustment

## Option 2: Embed directly in a Smart 1 Sites code block

Use the HTML from `public/index.html`, CSS from `public/styles.css`, and JS from `public/script.js`.

Before the script, set your Render API base:

```html
<script>
  window.SMART1RV_API_BASE = "https://smart1rv.onrender.com";
</script>
<script src="https://smart1rv.onrender.com/script.js"></script>
```

Make sure `ALLOWED_ORIGINS` in Render includes the Smart 1 Sites domain.

---

# Smart 1 Suite webhook payload

The webhook receives a JSON payload similar to this:

```json
{
  "source": "Smart RV Demand Estimate Form",
  "lead_type": "Smart RV Demand Package",
  "lead_status": "New RV Demand Lead",
  "submitted_at": "2026-07-08T00:00:00.000Z",
  "dealership_name": "Example RV Dealer",
  "contact_name": "Jane Smith",
  "email": "jane@example.com",
  "phone": "555-555-5555",
  "proposal_recipient_email": "jane@example.com",
  "address": "123 Main St",
  "city": "Columbus",
  "state": "OH",
  "zip": "43215",
  "website_url": "https://exampledealer.com",
  "sales_radius_miles": "75",
  "service_radius_miles": "40",
  "multiple_locations": "No",
  "primary_goal": "All of the above",
  "main_service_opportunity": "Winterization",
  "package_level": "$5,000/month Climate Safeguard Fund",
  "preferred_start": "Next month",
  "weather_triggers": ["70+ weekend", "Heavy rain", "Freeze warning"],
  "selected_weather_triggers": ["70+ weekend", "Heavy rain", "Freeze warning"],
  "estimate_type": "AI-generated planning estimate",
  "campground_count_low": 35,
  "campground_count_high": 50,
  "estimated_site_count_low": 2800,
  "estimated_site_count_high": 4250,
  "estimated_peak_season_reach_low": 52000,
  "estimated_peak_season_reach_high": 79000,
  "recommended_package": "$5,000/month Climate Safeguard Fund",
  "recommended_channels": ["Connected TV", "Digital Audio", "Programmatic Display"],
  "best_weather_triggers": ["60°+ forecast", "70°+ weekend", "Heavy rain"],
  "dealer_summary": "...",
  "month_by_month_plan": []
}
```

---

# Recommended Smart 1 Suite workflow

When the webhook fires:

1. Create or update contact by email
2. Create opportunity in the RV Demand pipeline
3. Store estimate fields as custom fields
4. Generate proposal document using custom values
5. Email proposal to `proposal_recipient_email`
6. Notify the assigned Smart 1 salesperson
7. Start follow-up automation if no appointment is booked

---

# Recommended Suite custom fields

Create custom fields for:

```txt
Dealership Name
Dealer Website URL
Dealer Address
Sales Radius Miles
Service Radius Miles
Primary Goal
Main Service Opportunity
Preferred Package Level
Selected Weather Triggers
Estimate Type
Campground Count Low
Campground Count High
Estimated Site Count Low
Estimated Site Count High
Estimated Peak Season Reach Low
Estimated Peak Season Reach High
Seasonal Share Assumption
Transient Share Assumption
Recommended Package
Recommended Channels
Best Weather Triggers
Dealer Summary
Month By Month Plan
Proposal Recipient Email
Review Request
Notes
```

For `month_by_month_plan`, store the full JSON or convert it to a long text field.

---

# Notes for production

- Keep the OpenAI API key only in Render environment variables.
- Never put API keys in Smart 1 Sites code blocks.
- Keep the Smart 1 Suite webhook URL only in Render environment variables.
- Use `ALLOWED_ORIGINS` after testing to reduce unwanted external submissions.
- Add captcha or honeypot protection if spam becomes an issue.
- Add server-side rate limiting if the page is publicly promoted.

## Bulk create Smart 1 Suite custom fields

This repo now includes an optional one-time field creation utility for Smart 1 Suite / HighLevel.

Files:

```text
scripts/createSuiteFields.js
fields/smart1rv-custom-fields.json
SUITE_FIELD_SETUP_RENDER.md
```

Dry run:

```bash
npm run suite:fields:dry
```

Create fields:

```bash
npm run suite:fields:create
```

Read `SUITE_FIELD_SETUP_RENDER.md` before running this in Render.
