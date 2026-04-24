/* ====================================================================
   MediGuide AI — Phase 1 Frontend Logic
   ==================================================================== */

// ---------------------------------------------------------------------------
// Session management
// ---------------------------------------------------------------------------

const SESSION_KEY = "mediguide_session_id";
const CONSENT_KEY = "mediguide_consented";

function getOrCreateSessionId() {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

const SESSION_ID = getOrCreateSessionId();

// Show truncated session ID in header
const sessionBadge = document.getElementById("sessionBadge");
if (sessionBadge) {
  sessionBadge.textContent = "Session: " + SESSION_ID.slice(0, 8) + "…";
  sessionBadge.title = "Your anonymous session ID: " + SESSION_ID;
}

// ---------------------------------------------------------------------------
// Disclaimer / Consent modal
// ---------------------------------------------------------------------------

const overlay       = document.getElementById("disclaimerOverlay");
const acceptBtn     = document.getElementById("acceptBtn");
const consentCheck  = document.getElementById("consentCheck");
const disclaimerEl  = document.getElementById("disclaimerText");
const appContainer  = document.getElementById("appContainer");

async function loadDisclaimer() {
  try {
    const res  = await fetch("/api/disclaimer");
    const data = await res.json();
    if (disclaimerEl && data.text) {
      disclaimerEl.textContent = data.text;
    }
  } catch {
    if (disclaimerEl) {
      disclaimerEl.textContent =
        "MediGuide AI is an EDUCATIONAL TOOL ONLY.\n" +
        "It does NOT diagnose, prescribe, or replace professional medical advice.\n" +
        "Always consult a licensed healthcare professional.";
    }
  }
}

if (consentCheck) {
  consentCheck.addEventListener("change", () => {
    acceptBtn.disabled = !consentCheck.checked;
  });
}

if (acceptBtn) {
  acceptBtn.addEventListener("click", async () => {
    acceptBtn.disabled = true;
    acceptBtn.innerHTML = '<span class="spinner"></span>Recording consent…';

    try {
      await fetch("/api/disclaimer/accept", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: SESSION_ID,
          disclaimer_version: "1.0",
        }),
      });
    } catch {
      // Non-critical — continue even if logging fails
    }

    localStorage.setItem(CONSENT_KEY, "1");
    overlay.style.display = "none";
    appContainer.classList.remove("app-hidden");
  });
}

// On load: skip modal if already consented this session
async function initApp() {
  await loadDisclaimer();

  if (localStorage.getItem(CONSENT_KEY) === "1") {
    // Verify server-side consent too
    try {
      const res  = await fetch("/api/consent/status", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: SESSION_ID }),
      });
      const data = await res.json();
      if (data.has_consent) {
        overlay.style.display = "none";
        appContainer.classList.remove("app-hidden");
        return;
      }
    } catch { /* show modal anyway */ }
  }
  // Show modal
  overlay.style.display = "flex";
}

initApp();

// ---------------------------------------------------------------------------
// Symptom form — submission
// ---------------------------------------------------------------------------

const symptomForm    = document.getElementById("symptomForm");
const submitBtn      = document.getElementById("submitBtn");
const resultsSection = document.getElementById("resultsSection");
const emergencyAlert = document.getElementById("emergencyAlert");

symptomForm && symptomForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span>Analysing…';

  const form = new FormData(symptomForm);

  // Build core model feature vector (binary 0/1)
  const features = {
    fever:       form.get("fever")       ? 1 : 0,
    cough:       form.get("cough")       ? 1 : 0,
    throat_pain: form.get("throat_pain") ? 1 : 0,
    skin_issue:  form.get("skin_issue")  ? 1 : 0,
  };

  // Collect red-flag symptom keys
  const redFlagSymptoms = [];
  document.querySelectorAll("[data-rf]").forEach((el) => {
    if (el.checked) redFlagSymptoms.push(el.dataset.rf);
  });

  const severity = form.get("severity") || null;
  const duration = form.get("duration") || null;
  const context  = (form.get("context") || "").trim() || null;

  try {
    // 1. Store symptoms
    await fetch("/api/symptoms", {
      method:  "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": SESSION_ID,
      },
      body: JSON.stringify({
        session_id: SESSION_ID,
        symptoms:   features,
        severity,
        duration,
        context,
      }),
    });

    // 2. Red-flag check (always run, even without consent gate)
    const rfRes  = await fetch("/api/red-flag-check", {
      method:  "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": SESSION_ID,
      },
      body: JSON.stringify({
        session_id: SESSION_ID,
        symptoms:   redFlagSymptoms,
      }),
    });
    const rfData = await rfRes.json();
    renderEmergencyAlert(rfData);

    // 3. Educational risk assessment
    const raRes  = await fetch("/api/risk-assessment", {
      method:  "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": SESSION_ID,
      },
      body: JSON.stringify({
        session_id: SESSION_ID,
        features,
      }),
    });
    const raData = await raRes.json();

    if (raData.error) {
      alert("Assessment error: " + raData.error);
    } else {
      renderRiskResults(raData.risk_assessment);
      resultsSection.classList.remove("results-hidden");
      resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (err) {
    alert("An error occurred. Please try again.\n" + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "🔍 Analyse Symptoms";
  }
});

// ---------------------------------------------------------------------------
// Render emergency alert
// ---------------------------------------------------------------------------

function renderEmergencyAlert(data) {
  if (!data.is_emergency) {
    emergencyAlert.classList.add("emergency-hidden");
    return;
  }

  emergencyAlert.classList.remove("emergency-hidden");

  const rulesContainer = document.getElementById("emergencyRules");
  if (!rulesContainer) return;

  rulesContainer.innerHTML = "";
  data.triggered_rules.forEach((rule) => {
    const div = document.createElement("div");
    div.className = "emergency-rule-item";
    div.innerHTML =
      `<strong>⚠️ ${escapeHtml(rule.message)}</strong>` +
      `<p class="action">${escapeHtml(rule.action)}</p>`;
    rulesContainer.appendChild(div);
  });

  emergencyAlert.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------------------------------------------------------------------------
// Render risk assessment results
// ---------------------------------------------------------------------------

function renderRiskResults(assessment) {
  if (!assessment) return;

  const { risk_tier, confidence, description, feature_contributions, next_steps } = assessment;

  // Risk badge
  const badge = document.getElementById("riskBadge");
  if (badge) {
    const icons = { low: "🟢", medium: "🟡", high: "🔴" };
    const labels = { low: "Low Risk Tier", medium: "Medium Risk Tier", high: "High Risk Tier" };
    badge.className = `risk-badge ${risk_tier || "low"}`;
    badge.textContent = `${icons[risk_tier] || ""} ${labels[risk_tier] || risk_tier}`;
  }

  // Description
  const desc = document.getElementById("riskDescription");
  if (desc) desc.textContent = description || "";

  // Confidence bar
  const pct = Math.round((confidence || 0) * 100);
  const bar  = document.getElementById("confidenceBar");
  const val  = document.getElementById("confidenceValue");
  if (bar) bar.style.width = pct + "%";
  if (val) val.textContent = pct + "%";

  // Feature contributions
  const list = document.getElementById("featuresList");
  if (list && feature_contributions) {
    list.innerHTML = "";
    feature_contributions.forEach((fc) => {
      const imp = (fc.importance || 0) * 100;
      const badgeCls =
        fc.contribution_label === "primary factor"   ? "primary"
        : fc.contribution_label === "secondary factor" ? "secondary"
        : "minor";

      const item = document.createElement("div");
      item.className = "feature-item";
      item.innerHTML =
        `<span class="feature-name">${escapeHtml(fc.feature)}</span>` +
        `<div class="feature-bar-wrap">` +
        `  <div class="feature-bar" style="width:${imp.toFixed(1)}%"></div>` +
        `</div>` +
        `<span class="feature-badge ${badgeCls}">${escapeHtml(fc.contribution_label)}</span>`;
      list.appendChild(item);
    });
  }

  // Next steps
  const stepsList = document.getElementById("nextStepsList");
  if (stepsList && next_steps) {
    stepsList.innerHTML = "";
    next_steps.forEach((step) => {
      const li = document.createElement("li");
      li.textContent = step;
      stepsList.appendChild(li);
    });
  }
}

// ---------------------------------------------------------------------------
// Privacy dashboard
// ---------------------------------------------------------------------------

const privacyBtn   = document.getElementById("privacyBtn");
const privacyPanel = document.getElementById("privacyPanel");
const closePrivacy = document.getElementById("closePrivacy");
const exportBtn    = document.getElementById("exportDataBtn");
const deleteBtn    = document.getElementById("deleteDataBtn");
const privacyOut   = document.getElementById("privacyOutput");

document.getElementById("privacySessionId") &&
  (document.getElementById("privacySessionId").textContent = SESSION_ID);

privacyBtn && privacyBtn.addEventListener("click", () => {
  privacyPanel.classList.remove("privacy-hidden");
  if (privacyOut) privacyOut.style.display = "none";
});

closePrivacy && closePrivacy.addEventListener("click", () => {
  privacyPanel.classList.add("privacy-hidden");
});

exportBtn && exportBtn.addEventListener("click", async () => {
  try {
    const res  = await fetch(`/api/privacy/my-data?session_id=${SESSION_ID}`);
    const data = await res.json();
    if (privacyOut) {
      privacyOut.textContent = JSON.stringify(data, null, 2);
      privacyOut.style.display = "block";
    }
  } catch (err) {
    alert("Export failed: " + err.message);
  }
});

deleteBtn && deleteBtn.addEventListener("click", async () => {
  if (!confirm(
    "This will permanently delete all session data including consent records " +
    "and symptom submissions.\n\nAre you sure?"
  )) return;

  try {
    const res  = await fetch(
      `/api/privacy/delete-all?session_id=${SESSION_ID}`,
      { method: "DELETE" }
    );
    const data = await res.json();
    if (data.deleted) {
      localStorage.removeItem(CONSENT_KEY);
      localStorage.removeItem(SESSION_KEY);
      if (privacyOut) {
        privacyOut.textContent = "✅ All data deleted. Reloading…";
        privacyOut.style.display = "block";
      }
      setTimeout(() => location.reload(), 1500);
    }
  } catch (err) {
    alert("Deletion failed: " + err.message);
  }
});

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

