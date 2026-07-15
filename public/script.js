// For local testing, leave this blank. For a Smart 1 Sites embed on another domain,
// set this to your Render service URL, for example: https://smart1rv.onrender.com
const API_BASE = window.SMART1RV_API_BASE || '';

// All weather triggers are assumed. The dealer no longer picks these — Smart 1 recommends
// the best set for their market. The full list is sent so the AI can prioritize.
const ALL_WEATHER_TRIGGERS = [
  'First 50°–60° forecast', '60°+ forecast', '70°+ weekend', 'Sunny weekend', 'Holiday weekend forecast',
  'Heavy rain', 'Thunderstorms', 'High wind', 'Severe storm watch',
  '85°+ forecast', '90°+ heat', 'Heat advisory', 'Heat index 100°+',
  'First frost', 'Freeze warning', 'Snow forecast', 'Cold snap under 45°',
  'Tropical storm or hurricane watch', 'Snowbird season'
];

const form = document.getElementById('rvDemandForm');
const steps = document.querySelectorAll('.srv-step');
const progressBar = document.getElementById('srvProgressBar');
const buildButton = document.getElementById('buildOpportunityBtn');
const submitStatus = document.getElementById('submitStatus');
const proposalRecipient = document.getElementById('proposalRecipient');
const alternateEmail = document.getElementById('alternateEmail');

let currentStep = 1;
let estimateData = null;
let submitCompleted = false;

function showStep(step) {
  steps.forEach(section => {
    section.classList.toggle('active', Number(section.dataset.step) === step);
  });
  currentStep = step;
  progressBar.style.width = `${Math.min((step / steps.length) * 100, 100)}%`;
}

function validateCurrentStep() {
  const activeStep = document.querySelector(`.srv-step[data-step="${currentStep}"]`);
  const requiredFields = activeStep.querySelectorAll('[required]');

  for (const field of requiredFields) {
    if (!field.value) {
      field.reportValidity();
      return false;
    }
  }
  return true;
}

function getFormPayload() {
  const data = new FormData(form);
  const payload = Object.fromEntries(data.entries());

  // Assume all weather triggers.
  payload.weather_triggers = ALL_WEATHER_TRIGGERS.slice();

  payload.proposal_recipient_email =
    payload.proposal_recipient === 'other' && payload.alternate_email
      ? payload.alternate_email
      : payload.email;

  return payload;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function money(value) {
  return '$' + Number(value || 0).toLocaleString('en-US');
}

// Fixed Smart RV Demand package levels (Climate Safeguard Fund tiers).
const PACKAGE_TIERS = [
  {
    key: 'Starter',
    amount: 3500,
    tagline: 'Best for smaller or single-location markets testing weather-triggered demand.',
    includes: ['Core CTV, Streaming Radio & Targeted Display', 'Primary weather triggers for your region', 'Campground & state-park geotargeting']
  },
  {
    key: 'Growth',
    amount: 5000,
    tagline: 'Our most popular level — the full weather-triggered stack with strong peak-season weight.',
    includes: ['Everything in Starter', 'Podcasts + Location Look-Back Retargeting', 'Broader weather-trigger coverage', 'Higher share of voice in peak weeks']
  },
  {
    key: 'Premium',
    amount: 7500,
    tagline: 'Best for larger or multi-location dealers and competitive markets.',
    includes: ['Everything in Growth', 'Digital Out-of-Home (DOOH) at local bars, restaurants, gas & shopping', 'Maximum trigger coverage', 'Highest peak-season media weight']
  }
];

function packageBaseAmount(estimate) {
  if (Number(estimate.base_monthly_budget) > 0) return Number(estimate.base_monthly_budget);
  const m = String(estimate.recommended_package || '').replace(/,/g, '').match(/\$?\s*(\d{3,6})/);
  return m ? Number(m[1]) : 5000;
}

// Collapsible "See package details" panel for the recommended package.
function buildPackageDetails(estimate) {
  const rec = packageBaseAmount(estimate);
  const channels = Array.isArray(estimate.recommended_channels) ? estimate.recommended_channels : [];

  const channelList = channels.length
    ? `<ul class="srv-detail-list">${channels.map(c => `<li>${escapeHtml(c)}</li>`).join('')}</ul>`
    : '';

  const tiers = PACKAGE_TIERS.map(t => {
    const isRec = t.amount === rec;
    return `
      <div class="srv-tier${isRec ? ' srv-tier-rec' : ''}">
        <div class="srv-tier-head">
          <span class="srv-tier-name">${escapeHtml(t.key)}</span>
          ${isRec ? '<span class="srv-tier-badge">Recommended</span>' : ''}
        </div>
        <div class="srv-tier-price">${money(t.amount)}<span>/month</span></div>
        <p class="srv-tier-tagline">${escapeHtml(t.tagline)}</p>
        <ul class="srv-detail-list">${t.includes.map(i => `<li>${escapeHtml(i)}</li>`).join('')}</ul>
      </div>`;
  }).join('');

  return `
    <button type="button" class="srv-details-toggle" id="srvPkgDetailsToggle" aria-expanded="false" aria-controls="srvPkgDetails">See package details</button>
    <div class="srv-details" id="srvPkgDetails" hidden>
      <h4>What’s included in your Climate Safeguard Fund</h4>
      <p>Your monthly fund runs weather-triggered advertising across the channels we recommend for your market:</p>
      ${channelList}
      <ul class="srv-detail-list">
        <li><strong>Weather-triggered activation</strong> — ads turn on when your selected weather conditions hit and pause when they don’t.</li>
        <li><strong>Campaign management &amp; optimization</strong> — Smart 1 builds, runs, and tunes the campaigns for you.</li>
        <li><strong>Reporting</strong> — track delivery and performance throughout the campaign.</li>
        <li><strong>Rollover protection</strong> — unused media from poor-weather windows rolls into the next month.</li>
        <li><strong>Off-season off-ramp</strong> — leftover peak-season budget can shift to winterization, spring prep, A/C or generator service campaigns, or carry 100% forward as credit.</li>
      </ul>
      <h4>Package levels</h4>
      <div class="srv-tier-grid">${tiers}</div>
      <p class="srv-detail-fineprint">All levels are month-to-month Climate Safeguard Fund subscriptions. Your recommended level is based on your market size and estimated opportunity — you can move up or down after a strategy review.</p>
    </div>`;
}

function wirePackageDetails() {
  const toggle = document.getElementById('srvPkgDetailsToggle');
  const details = document.getElementById('srvPkgDetails');
  if (!toggle || !details) return;
  toggle.addEventListener('click', () => {
    const isHidden = details.hasAttribute('hidden');
    if (isHidden) {
      details.removeAttribute('hidden');
      toggle.setAttribute('aria-expanded', 'true');
      toggle.textContent = 'Hide package details';
    } else {
      details.setAttribute('hidden', '');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.textContent = 'See package details';
    }
  });
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function chips(list) {
  if (!Array.isArray(list) || list.length === 0) return '';
  return `<div class="srv-chips">${list.map(item => `<span class="srv-chip">${escapeHtml(item)}</span>`).join('')}</div>`;
}

// Builds the full on-screen report shown before the proposal step.
function buildReportHtml(estimate) {
  const dealership = (getFormPayload().dealership_name || 'your dealership').trim();

  const region = estimate.market_climate_region
    ? `
      <div class="srv-report-section srv-region">
        <span class="srv-region-badge">${escapeHtml(estimate.market_climate_region)}</span>
        ${estimate.market_region_reason ? `<p>${escapeHtml(estimate.market_region_reason)}</p>` : ''}
      </div>`
    : '';

  const stats = `
    <div class="srv-stat-grid">
      <div class="srv-stat">
        <span class="opportunity-number">${formatNumber(estimate.campground_count_low)}–${formatNumber(estimate.campground_count_high)}</span>
        <span class="srv-stat-label">campgrounds &amp; RV parks</span>
      </div>
      <div class="srv-stat">
        <span class="opportunity-number">${formatNumber(estimate.estimated_site_count_low)}–${formatNumber(estimate.estimated_site_count_high)}</span>
        <span class="srv-stat-label">estimated RV / camping sites</span>
      </div>
      <div class="srv-stat">
        <span class="opportunity-number">${formatNumber(estimate.estimated_peak_season_reach_low)}–${formatNumber(estimate.estimated_peak_season_reach_high)}</span>
        <span class="srv-stat-label">estimated peak-season camper reach</span>
      </div>
    </div>`;

  const summary = estimate.dealer_summary
    ? `<div class="srv-report-section"><h3>Your Market Opportunity</h3><p>${escapeHtml(estimate.dealer_summary)}</p></div>`
    : '';

  const pkg = estimate.recommended_package
    ? `
      <div class="srv-report-section srv-package">
        <h3>Recommended Package</h3>
        <p class="srv-package-name">${escapeHtml(estimate.recommended_package)}</p>
        ${estimate.recommended_package_reason ? `<p>${escapeHtml(estimate.recommended_package_reason)}</p>` : ''}
        ${buildPackageDetails(estimate)}
      </div>`
    : '';

  const channels = (Array.isArray(estimate.recommended_channels) && estimate.recommended_channels.length)
    ? `<div class="srv-report-section"><h3>Recommended Media Channels</h3>${chips(estimate.recommended_channels)}</div>`
    : '';

  const triggers = (Array.isArray(estimate.best_weather_triggers) && estimate.best_weather_triggers.length)
    ? `<div class="srv-report-section"><h3>Recommended Weather Triggers for Your Market</h3>${chips(estimate.best_weather_triggers)}</div>`
    : '';

  const budget = estimate.base_monthly_budget_text
    ? `
      <div class="srv-report-section srv-budget">
        <h3>Suggested Media Budget</h3>
        <div class="srv-budget-grid">
          <div class="srv-budget-tile">
            <span class="srv-budget-amount">${escapeHtml(estimate.base_monthly_budget_text)}/mo</span>
            <span class="srv-stat-label">at peak demand</span>
          </div>
          <div class="srv-budget-tile">
            <span class="srv-budget-amount">${escapeHtml(estimate.average_monthly_budget_text || '')}/mo</span>
            <span class="srv-stat-label">blended average</span>
          </div>
          <div class="srv-budget-tile">
            <span class="srv-budget-amount">${escapeHtml(estimate.suggested_budget_total_text || '')}</span>
            <span class="srv-stat-label">plan total (${escapeHtml(String(estimate.suggested_budget_months || ''))} months)</span>
          </div>
        </div>
        ${estimate.budget_note ? `<p class="srv-budget-note">${escapeHtml(estimate.budget_note)}</p>` : ''}
      </div>`
    : '';

  let plan = '';
  if (Array.isArray(estimate.month_by_month_plan) && estimate.month_by_month_plan.length) {
    const rows = estimate.month_by_month_plan.map(row => `
      <tr>
        <td class="srv-plan-month">${escapeHtml(row.month)}${row.season ? `<div class="srv-plan-season srv-season-${escapeHtml(String(row.season).toLowerCase().replace(/[^a-z]/g, ''))}">${escapeHtml(row.season)}</div>` : ''}</td>
        <td>
          <strong>${escapeHtml(row.campaign_focus)}</strong>
          <div class="srv-plan-message">${escapeHtml(row.recommended_message)}</div>
          ${chips(row.weather_triggers)}
        </td>
        <td class="srv-plan-budget">${escapeHtml(row.suggested_budget_text || '')}</td>
      </tr>`).join('');
    plan = `
      <div class="srv-report-section">
        <h3>Month-by-Month Campaign Plan &amp; Budget</h3>
        <table class="srv-plan-table">
          <thead><tr><th>Month</th><th>Focus &amp; Triggers</th><th>Budget</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  const disclaimer = estimate.estimate_disclaimer
    ? `<p class="disclaimer">${escapeHtml(estimate.estimate_disclaimer)}</p>`
    : '';

  return `
    <p class="srv-report-intro">Based on ${escapeHtml(dealership)}’s location, selected buyer radius, and regional campground density, here’s your weather-triggered RV demand opportunity:</p>
    ${region}
    ${stats}
    ${summary}
    ${pkg}
    ${channels}
    ${triggers}
    ${budget}
    ${plan}
    ${disclaimer}
  `;
}

function renderEstimate(estimate) {
  const box = document.getElementById('marketOpportunityResult');
  box.innerHTML = buildReportHtml(estimate);
  wirePackageDetails();
}

async function estimateAndSubmit() {
  const payload = getFormPayload();
  const response = await fetch(`${API_BASE}/api/rv-demand/estimate-and-submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const result = await response.json();
  if (!response.ok || !result.ok) {
    throw new Error(result.detail || result.error || 'Submission failed');
  }

  return result;
}

document.querySelectorAll('.next-btn').forEach(button => {
  button.addEventListener('click', () => {
    if (!validateCurrentStep()) return;
    showStep(currentStep + 1);
  });
});

document.querySelectorAll('.prev-btn').forEach(button => {
  button.addEventListener('click', () => {
    showStep(Math.max(currentStep - 1, 1));
  });
});

proposalRecipient.addEventListener('change', () => {
  const showAlt = proposalRecipient.value === 'other';
  alternateEmail.style.display = showAlt ? 'block' : 'none';
  alternateEmail.required = showAlt;
});

buildButton.addEventListener('click', async () => {
  if (!validateCurrentStep()) return;

  // Advance to the results step (all triggers/goals are assumed — nothing to pick).
  showStep(4);
  buildButton.disabled = true;

  document.getElementById('marketOpportunityResult').innerHTML = '<p>Calculating Marketing Conditions.</p>';

  try {
    const result = await estimateAndSubmit();
    estimateData = result.estimate;
    submitCompleted = true;
    renderEstimate(estimateData);
  } catch (error) {
    document.getElementById('marketOpportunityResult').innerHTML = `
      <p>We could not complete the automated estimate right now.</p>
      <p>Your team can still review the form details manually. Error: ${escapeHtml(error.message)}</p>
    `;
    console.error(error);
  } finally {
    buildButton.disabled = false;
  }
});

form.addEventListener('submit', async event => {
  event.preventDefault();

  if (!validateCurrentStep()) return;

  // The lead has already been submitted when the estimate was built.
  // This final step confirms to the prospect that Smart 1 Suite will handle the proposal workflow.
  if (submitCompleted) {
    submitStatus.textContent = 'Your request has been submitted. Smart 1 Suite will handle the proposal document and follow-up email.';
    form.querySelector('button[type="submit"]').disabled = true;
    return;
  }

  try {
    submitStatus.textContent = 'Submitting your request...';
    const result = await estimateAndSubmit();
    estimateData = result.estimate;
    submitCompleted = true;
    submitStatus.textContent = 'Your request has been submitted. Smart 1 Suite will handle the proposal document and follow-up email.';
  } catch (error) {
    submitStatus.textContent = `Submission failed: ${error.message}`;
  }
});
