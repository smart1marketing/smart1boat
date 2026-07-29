# Smart1Suite (Go High Level) — Field Map to Create an Opportunity

When a dealer submits the boat form, the app posts a JSON webhook to your `SMART1_WEBHOOK_URL`.
Below is every field it sends, and how to map it in Smart1Suite to create a Contact + Opportunity and send the proposal.

## How it flows
1. Dealer submits the form → app generates the report → app POSTs the webhook to Smart1Suite.
2. In Smart1Suite, an **Inbound Webhook** workflow trigger captures these fields.
3. Workflow actions: **Create/Update Contact** → **Create/Update Opportunity** → **Send Email** (with the report link).

---

## 1. Contact fields (standard — already exist in Smart1Suite)

| Webhook field | Map to Smart1Suite | Notes |
|---|---|---|
| `contact_first_name` | Contact › First Name | Split from the name they entered |
| `contact_last_name` | Contact › Last Name | Split from the name they entered |
| `contact_name` | (full name, backup) | Use if you prefer a single name field |
| `contact_email` | Contact › Email | Required on the form |
| `contact_phone` | Contact › Phone | Optional on the form (may be blank) |

## 2. Contact custom fields (create these in Smart1Suite → Settings → Custom Fields)

| Webhook field | Suggested custom field name | Field type |
|---|---|---|
| `dealer_name` | Dealership Name | Single line |
| `website` | Dealer Website | Single line / URL |
| `dealer_zip` | Dealer ZIP | Single line |
| `target_radius` | Target Radius | Single line |
| `boat_types` | Boat Types | Multi line |
| `new_used` | Inventory Mix | Single line |
| `campaign_objective` | Campaign Objectives | Multi line |
| `notes` | Dealer Notes | Multi line |
| `market_type` | Market Type | Single line |
| `estimated_boat_owner_households_base` | Estimated Boat-Owner Households | Number |
| `recommended_package` | Recommended Package | Single line |
| `recommended_monthly_investment` | Recommended Monthly Investment | Single line / Monetary |
| `market_summary` | Boat Market Summary | Multi line |
| `report_url` | **Proposal Report Link** | Single line / URL |
| `report_json` | Boat Report JSON (optional) | Large text — full report data, backup |
| `report_status` | Boat Report Status | Single line (`completed` / `failed`) |
| `source` | Lead Source | Single line (`Smart 1 Boat Dealer Market Intelligence`) |

## 3. Opportunity fields

| Webhook field | Map to Opportunity | Notes |
|---|---|---|
| `opportunity_name` | Opportunity Name | Pre-built as "{Dealership} — Weather Marketing Proposal" |
| `recommended_monthly_investment` | Opportunity Value | e.g. `$5,000/month` (strip `$`/`/month` if a numeric field) |
| `source` | Source | `Smart 1 Boat Dealer Market Intelligence` |
| — | Pipeline | Choose your boat/dealer pipeline |
| — | Stage | e.g. "New Proposal" |
| — | Status | `Open` |

## 4. Sending the PDF / report

Two links are sent:

- **`report_pdf_url`** — a real PDF, generated server-side and stored in Cloudinary
  (`boat-reports/<dealer-slug>-boat-report-<id>.pdf`). Use this to attach/send the PDF.
- **`report_url`** — the interactive HTML report link (`https://your-app.onrender.com/?r=...`).

Setup in Smart1Suite:
- Map `report_pdf_url` to a **Proposal PDF** custom field and `report_url` to a **Proposal Report Link** field.
- In your email template, add a button `Download Your Weather Marketing Proposal (PDF)` → `{{contact.proposal_pdf}}`,
  and optionally a `View online` link → `{{contact.proposal_report_link}}`.
- `report_json` is also sent as a backup of the full report data.

> Note: the report link is served by the app. For long-term durability of old links, set a `PUBLIC_BASE_URL`
> environment variable (your public app URL) and, ideally, add a Render persistent disk — otherwise links are
> cleared on redeploys. The link works immediately after submission, which covers same-day sends.

## 5. Opportunity summary note

Add an **"Add Note"** action after Create/Update Opportunity. The note attaches to the
contact and shows on the opportunity's activity feed. Paste this (uses the inbound-webhook
merge syntax; if you added the note step after mapping custom fields, you can instead use
`{{ contact.<field_key> }}`):

```
📋 Smart 1 Boat Dealer Report — {{inboundWebhookRequest.dealer_name}}

CONTACT
Name:  {{inboundWebhookRequest.contact_name}}
Email: {{inboundWebhookRequest.contact_email}}
Phone: {{inboundWebhookRequest.contact_phone}}
Website: {{inboundWebhookRequest.website}}

MARKET
Type: {{inboundWebhookRequest.market_type}}
Dealer ZIP: {{inboundWebhookRequest.dealer_zip}}  |  Target radius: {{inboundWebhookRequest.target_radius}}
Boat types: {{inboundWebhookRequest.boat_types}}
Inventory mix: {{inboundWebhookRequest.new_used}}
Objectives: {{inboundWebhookRequest.campaign_objective}}
Est. boat-owner households: {{inboundWebhookRequest.estimated_boat_owner_households_base}}

RECOMMENDATION
Package: {{inboundWebhookRequest.recommended_package}} — {{inboundWebhookRequest.recommended_monthly_investment}}
Summary: {{inboundWebhookRequest.market_summary}}

LINKS
Proposal report: {{inboundWebhookRequest.report_url}}
Report status: {{inboundWebhookRequest.report_status}}

Dealer notes: {{inboundWebhookRequest.notes}}
Source: {{inboundWebhookRequest.source}}
```

## 6. Smart1Suite workflow setup (quick steps)
1. Automation → Workflows → **Create Workflow** → Trigger: **Inbound Webhook**.
2. Submit the boat form once so Smart1Suite captures a sample payload (auto-maps the fields above).
3. Action **Create/Update Contact** → map fields from sections 1–2.
4. Action **Create/Update Opportunity** → map fields from section 3.
5. Action **Add Note** → paste the summary note from section 5.
6. Action **Send Email** → include the `report_url` button from section 4.
7. (Optional) Add an internal notification to the assigned rep.

## Full list of webhook field keys (for reference)
`dealer_name, website, dealer_zip, target_radius, boat_types, new_used, campaign_objective, notes,
contact_name, contact_first_name, contact_last_name, contact_email, contact_phone,
source, report_status, opportunity_name, market_type, estimated_boat_owner_households_base,
recommended_package, recommended_monthly_investment, market_summary, report_url, report_pdf_url, report_json`
