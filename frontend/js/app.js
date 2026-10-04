const API = resolveApiBase();
// ---------------------------------------------------------------------------
// Risk Inference Engine: factor definitions
// The order of RISK_FACTOR_GROUPS is the order the sections appear in the UI.
// Each field's `key` is the evidence name sent to POST /predict, `desc` is the
// help text shown under its label, and each option is [value, label]. A factor
// the user leaves unset is simply omitted (unknown).
// ---------------------------------------------------------------------------
const LMH = [["low", "Low"], ["moderate", "Moderate"], ["high", "High"]];

const RISK_FACTOR_GROUPS = [
  {
    id: "epidemiological", title: "Epidemiological", desc: "Current dengue burden",
    icon: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    fields: [
      { key: "historical_dengue_cases", label: "Historical Dengue Cases",
        desc: "Previous-week dengue case level for the selected district: Below, Alert, or Epidemic.",
        help: {
          en: {
            title: "What does this mean?",
            closeLabel: "Close explanation",
            description: "This is about how many dengue cases were recorded in your selected district last week. It gives the app a starting point for understanding the area's recent dengue situation.",
            purpose: "The app looks at this together with the other details you enter, like weather and surroundings, to estimate dengue risk.",
            levels: [
              { label: "Below", tone: "below", description: "The case count falls in the lower range used by this project for your district." },
              { label: "Alert", tone: "alert", description: "The case count falls in the middle range used by this project for your district." },
              { label: "Epidemic", tone: "epidemic", description: "The case count falls in the higher range used by this project for your district." }
            ],
            guidanceLabel: "Which one should I pick?",
            guidance: "Use the category that matches your district's case data and the project's ranges. Not sure which one fits? You can leave it blank; the app will treat it as unknown. To undo a choice, just click the same option again.",
            note: "These labels are used for this research project. Choosing \"Epidemic\" here doesn't mean an outbreak has been officially declared."
          },
          tl: {
            title: "Ano ang ibig sabihin nito?",
            closeLabel: "Isara ang paliwanag",
            description: "Ito ang bilang ng mga kaso ng dengue na naitala noong nakaraang linggo sa distrito na pinili mo. Nakakatulong ito para makita ng app ang sitwasyon ng dengue sa lugar ninyo.",
            purpose: "Ginagamit ito ng app kasama ng iba pang detalye na ilalagay mo, gaya ng panahon at kapaligiran, para matantiya ang dengue risk.",
            levels: [
              { label: "Below", tone: "below", description: "Nasa mababang range ng project ang bilang ng mga kaso sa distrito mo." },
              { label: "Alert", tone: "alert", description: "Nasa gitnang range ng project ang bilang ng mga kaso sa distrito mo." },
              { label: "Epidemic", tone: "epidemic", description: "Nasa mataas na range ng project ang bilang ng mga kaso sa distrito mo." }
            ],
            guidanceLabel: "Alin ang pipiliin ko?",
            guidance: "Piliin ang kategoryang tugma sa data ng dengue sa distrito mo at sa ranges ng project. Kung hindi ka sigurado, puwede mo itong iwanang walang napili; ituturing ito ng app na hindi pa alam. Para alisin ang napili mo, i-click lang ulit ang parehong option.",
            note: "Para sa research project ang mga label na ito. Kapag pinili mo ang \"Epidemic\" dito, hindi ibig sabihin na may opisyal nang deklarasyon ng outbreak."
          }
        },
        options: [["below", "Below"], ["alert", "Alert"], ["epidemic", "Epidemic"]] }
    ]
  },
  {
    id: "meteorological", title: "Meteorological", desc: "Weather that drives mosquito breeding and survival",
    icon: '<path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9"/><path d="M16 14v6"/><path d="M8 14v6"/><path d="M12 16v6"/>',
    fields: [
      { key: "min_temperature", label: "Minimum Temperature",
        desc: "Coolest daily temperature. Warmer nights speed up mosquito development and virus incubation.", options: LMH },
      { key: "max_temperature", label: "Maximum Temperature",
        desc: "Hottest daily temperature. Moderate heat boosts breeding and biting; extreme heat shortens mosquito lifespan.", options: LMH },
      { key: "humidity", label: "Humidity",
        desc: "Moisture in the air. Higher humidity improves mosquito survival and activity.", options: LMH },
      { key: "rainfall", label: "Rainfall",
        desc: "Weekly rainfall. Rain fills containers and puddles where Aedes mosquitoes lay eggs.",
        options: [["very_light", "Very Light"], ["light", "Light"], ["moderate", "Moderate"], ["heavy", "Heavy"]] },
      { key: "wind_temperature", label: "Wind Temperature",
        desc: "Temperature of the moving air near the surface. Affects mosquito activity and flight.", options: LMH },
      { key: "wind_speed", label: "Wind Speed",
        desc: "How fast air is moving. Strong wind disrupts mosquito flight and biting; calm air favors them.", options: LMH },
      { key: "mean_diurnal_range", label: "Mean Diurnal Range",
        desc: "Average gap between daily high and low temperatures. Large swings can slow mosquito development.", options: LMH },
      { key: "isothermality", label: "Isothermality",
        desc: "Day-to-night temperature range as a share of the yearly range. Higher means steadier temperatures all year.", options: LMH }
    ]
  },
  {
    id: "environmental", title: "Environmental", desc: "Air, water, vegetation, flooding and drought",
    icon: '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
    fields: [
      { key: "air_quality", label: "Air Quality",
        desc: "Air Quality Index category, from Good to Emergency. Poor air reflects congestion and urban pollution.",
        options: [["good", "Good"], ["fair", "Fair"], ["unhealthy", "Unhealthy"], ["very_unhealthy", "Very Unhealthy"], ["acutely_unhealthy", "Acutely Unhealthy"], ["emergency", "Emergency"]] },
      { key: "water_ph", label: "Water Quality (pH)",
        desc: "Acidity of nearby standing or surface water. Influences how suitable it is for larvae to develop.",
        options: [["acidic", "Acidic"], ["alkaline", "Alkaline"]] },
      { key: "water_turbidity", label: "Water Quality (Turbidity)",
        desc: "How cloudy or murky the water is. Murky, nutrient-rich water can support larval food supply.", options: LMH },
      { key: "ndvi", label: "NDVI",
        desc: "Normalized Difference Vegetation Index: how green and dense the vegetation is. More greenery means more shaded, humid resting spots.", options: LMH },
      { key: "flood_incidence", label: "Flood Incidence",
        desc: "How often the area floods. Floodwater leaves stagnant pools where mosquitoes breed.",
        options: [["none", "None"], ["moderate", "Moderate"], ["high", "High"]] },
      { key: "pdsi", label: "Palmer Drought Severity Index",
        desc: "How severe drought is compared with normal. Dry spells push households to store water in open containers.", options: LMH }
    ]
  },
  {
    id: "infrastructure", title: "Infrastructure", desc: "Built-environment activity",
    icon: '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>',
    fields: [
      { key: "nighttime_light_intensity", label: "Nighttime Light Intensity",
        desc: "How bright the area appears from space at night. A proxy for urbanization and human activity.", options: LMH }
    ]
  },
  {
    id: "demographic", title: "Demographic", desc: "Who lives in the target area",
    icon: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    fields: [
      { key: "age", label: "Age",
        desc: "The age group that makes up most of the population. Young children and older adults are more prone to severe dengue.",
        options: [["child", "Child (0\u201314)"], ["youth", "Youth (15\u201324)"], ["adult", "Adult (25\u201359)"], ["senior", "Senior (60+)"]] },
      { key: "gender", label: "Gender",
        desc: "The gender that makes up most of the population. Exposure and care-seeking habits can differ between groups.",
        options: [["male", "Male"], ["female", "Female"]] }
    ]
  },
  {
    id: "sociodemographic", title: "Sociodemographic", desc: "Population size and settlement pattern",
    icon: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    fields: [
      { key: "population_density", label: "Population Density",
        desc: "People per unit of land area. Crowded areas let mosquitoes find hosts easily and spread infection faster.", options: LMH },
      { key: "number_of_households", label: "Number of Households",
        desc: "How many households live in the area. More homes mean more containers and yards where mosquitoes can breed.", options: LMH }
    ]
  },
  {
    id: "socioeconomic", title: "Socioeconomic", desc: "Livelihood, income, education and health spending",
    icon: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    fields: [
      { key: "poverty_incidence", label: "Poverty Incidence",
        desc: "Share of residents living below the poverty line. Poorer areas often have weaker water, drainage and housing.", options: LMH },
      { key: "income", label: "Income",
        desc: "Typical household income. Higher income usually means better housing, screens and access to care.", options: LMH },
      { key: "occupation", label: "Occupation",
        desc: "Where most residents work. Outdoor work means more daytime exposure to Aedes bites.",
        options: [["indoor", "Indoor"], ["outdoor", "Outdoor"]] },
      { key: "employment_status", label: "Employment Status",
        desc: "Level of employment among residents. Job stability shapes income and the ability to afford prevention.", options: LMH },
      { key: "health_expenditure", label: "Health Expenditure",
        desc: "Spending on health care in the area. More spending means better access to testing, treatment and prevention.", options: LMH },
      { key: "educational_attainment", label: "Educational Attainment",
        desc: "Highest level of schooling most residents completed. Education shapes awareness of prevention such as clearing standing water.",
        options: [["none", "None"], ["elementary", "Elementary"], ["high_school", "High School"], ["senior_high_school", "Senior High School"], ["college_and_above", "College & Above"]] },
      { key: "literacy_rate", label: "Literacy Rate",
        desc: "Share of residents who can read and write. Higher literacy helps health messages and campaigns land.", options: LMH }
    ]
  },
  {
    id: "intervention", title: "Intervention", desc: "Vector control and waste management",
    icon: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    fields: [
      { key: "fogging", label: "Fogging",
        desc: "Level of insecticide fogging carried out. Fogging knocks down adult mosquitoes for a short time.",
        options: [["none", "None"], ["moderate", "Moderate"], ["high", "High"]] },
      { key: "solid_waste_generation", label: "Solid Waste Generation",
        desc: "How much garbage the area produces. Discarded cans, tires and plastics collect rainwater and become breeding sites.", options: LMH },
      { key: "solid_waste_collection", label: "Solid Waste Collection",
        desc: "How reliably garbage is collected. Uncollected waste piles up and holds stagnant water.", options: LMH }
    ]
  }
];
const RISK_FACTOR_TOTAL = RISK_FACTOR_GROUPS.reduce((sum, g) => sum + g.fields.length, 0);

// Risk-level display names shown to users. The underlying keys ("low"/"medium"/"high")
// stay the same everywhere else (CSS classes, data matching, sample data) — only the
// user-facing label text changes here.
const RISK_DISPLAY_LABELS = { low: "BELOW", medium: "ALERT", high: "EPIDEMIC" };
function riskLabel(level) {
  if (!level) return "";
  return RISK_DISPLAY_LABELS[String(level).toLowerCase()] || String(level).toUpperCase();
}

document.addEventListener("DOMContentLoaded", initApp);

function resolveApiBase() {
  if (window.location.protocol === "file:") return "http://localhost:5000";
  if (!window.location.origin || window.location.origin === "null") return "http://localhost:5000";
  return window.location.origin;
}

function escapeHtml(value) {
  const text = String(value ?? "");
  const replacements = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return text.replace(/[&<>"']/g, (char) => replacements[char]);
}

function initApp() {
  bindNavigation();
  bindForecastControls();
  bindFilterControls();
  setCurrentDateDisplay();
  loadDashboardData();
  loadLSTMAreas();
  initRiskFactorPanel();
  updateHistoryCountBadge();
  bindProfileControls();
  showPage("dashboard");
}

function bindNavigation() {
  const navButtons = document.querySelectorAll(".nav-item[data-page], .mobile-bottom-nav-item[data-page]");
  navButtons.forEach((button) => { button.addEventListener("click", () => showPage(button.dataset.page)); });

  // Dashboard Map Interaction
  document.querySelectorAll(".d-rect").forEach(rect => {
    const handler = () => {
      showPage("districts");
      setTimeout(() => window.showDistrictDetail(rect.dataset.dist), 100);
    };
    rect.addEventListener("click", handler);
    rect.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handler(); } });
  });
}

function revealForecastKpi() {
  window.__forecastRevealed = true;

  const kpiForecast = document.getElementById("kpi-total-forecast");
  if (kpiForecast && kpiForecast.dataset.pendingValue !== undefined) {
    kpiForecast.textContent = kpiForecast.dataset.pendingValue;
    const trendEl = kpiForecast.parentElement.querySelector(".kpi-trend");
    if (trendEl) {
      trendEl.textContent = kpiForecast.dataset.pendingTrendText;
      trendEl.className = `kpi-trend ${kpiForecast.dataset.pendingTrendClass}`;
    }
  }

  const kpiCases = document.getElementById("kpi-sample-cases");
  if (kpiCases && kpiCases.dataset.pendingValue !== undefined) {
    kpiCases.textContent = kpiCases.dataset.pendingValue;
    const trendEl = kpiCases.parentElement.querySelector(".kpi-trend");
    if (trendEl) {
      trendEl.textContent = kpiCases.dataset.pendingTrendText;
      trendEl.className = `kpi-trend ${kpiCases.dataset.pendingTrendClass}`;
    }
  }

  document.querySelectorAll(".district-card-metric[data-cases]").forEach(el => {
    el.textContent = `${el.dataset.cases} cases`;
  });

  // Detailed District Summary table
  document.querySelectorAll(".summary-cases[data-value]").forEach(el => {
    el.textContent = el.dataset.value;
  });
  document.querySelectorAll(".summary-forecast[data-value]").forEach(el => {
    el.textContent = el.dataset.value;
  });
  document.querySelectorAll(".summary-risk[data-risk]").forEach(el => {
    const risk = el.dataset.risk;
    el.innerHTML = `<span class="risk-pill ${risk}">${riskLabel(risk)}</span>`;
  });
  document.querySelectorAll(".district-indicator[data-risk]").forEach(el => {
    el.className = `district-indicator ${el.dataset.risk}`;
  });

  // District Risk Overview mini-cards (Dashboard)
  document.querySelectorAll(".dashboard-district-card[data-risk-card]").forEach(el => {
    el.className = `dashboard-district-card ${el.dataset.riskCard}`;
  });
  document.querySelectorAll(".card-risk-pill[data-risk]").forEach(el => {
    const risk = el.dataset.risk;
    el.className = `risk-pill card-risk-pill ${risk}`;
    el.textContent = riskLabel(risk);
  });

  renderHealthAlerts();
  renderDistrictDetailSituation();
}

function bindForecastControls() {
  const toggleForecastBtn = document.getElementById("toggle-forecast-btn");
  const dashboardSplit = document.getElementById("dashboard-split");
  if (toggleForecastBtn && dashboardSplit) {
    toggleForecastBtn.addEventListener("click", () => {
      const isOpen = dashboardSplit.classList.toggle("forecast-open");
      toggleForecastBtn.classList.toggle("forecast-active", isOpen);
      toggleForecastBtn.querySelector(".forecast-btn-label").textContent = isOpen ? "Hide Forecast Panel" : "Run a Forecast";
      if (isOpen) {
        setTimeout(() => dashboardSplit.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
      }
    });
  }

  const runButton = document.getElementById("run-btn");
  const resetButton = document.getElementById("reset-btn");
  if (runButton) runButton.addEventListener("click", runInference);
  if (resetButton) resetButton.addEventListener("click", resetForm);

  const lstmModeToggle = document.getElementById("lstm-mode-toggle");
  if (lstmModeToggle) lstmModeToggle.addEventListener("change", toggleLstmMode);

  const getForecastBtn = document.getElementById("get-forecast-btn");
  if (getForecastBtn) {
    getForecastBtn.addEventListener("click", async () => {
      const lstmToggle = document.getElementById("lstm-mode-toggle");
      if (lstmToggle && lstmToggle.checked) {
        runLSTMForecast(); // manages its own button/loading state
        return;
      }

      // Combined mode: short-term projection + risk inference run together
      // from this one button, sharing one disabled/loading state.
      const loading = document.getElementById("lstm-loading");
      const originalLabel = getForecastBtn.textContent;
      getForecastBtn.disabled = true;
      getForecastBtn.textContent = "Forecasting...";
      if (loading) loading.classList.add("active");

      try {
        const districtSelect = document.getElementById("forecast-district");
        await Promise.all([
          loadShortTermForecast(districtSelect ? districtSelect.value : "I"),
          runInference()
        ]);
      } finally {
        getForecastBtn.disabled = false;
        getForecastBtn.textContent = originalLabel || "Forecast";
        if (loading) loading.classList.remove("active");
      }
    });
  }
}

function toggleLstmMode() {
  const isLstm = document.getElementById("lstm-mode-toggle")?.checked;

  const shortTermFields = document.getElementById("short-term-fields-group");
  const lstmFields = document.getElementById("lstm-fields-group");
  const combinedResults = document.getElementById("combined-results-group");
  const lstmResult = document.getElementById("lstm-result");

  if (shortTermFields) shortTermFields.hidden = !!isLstm;
  if (lstmFields) lstmFields.hidden = !isLstm;
  if (combinedResults) combinedResults.hidden = !!isLstm;
  if (lstmResult) lstmResult.hidden = !isLstm;
}

function bindFilterControls() {
  const histDist = document.getElementById("hist-filter-district");
  const clearBtn = document.getElementById("clear-history-btn");
  if (histDist) histDist.addEventListener("change", renderHistoricalTable);
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if (confirm("Clear all logged forecasts? This can't be undone.")) {
        saveForecastHistory([]);
        renderHistoricalTable();
      }
    });
  }
}

function showPage(pageName) {
  const pages = document.querySelectorAll(".page");
  pages.forEach((page) => page.classList.toggle("active", page.id === `page-${pageName}`));

  const navItems = document.querySelectorAll(".nav-item[data-page], .mobile-bottom-nav-item[data-page]");
  navItems.forEach((item) => {
    const isActive = item.dataset.page === pageName;
    item.classList.toggle("active", isActive);
    if (isActive) {
      item.setAttribute("aria-current", "page");
    } else {
      item.removeAttribute("aria-current");
    }
  });

  if (pageName === "history") loadHistoricalData();
  if (pageName === "districts") loadDistrictsData();
  if (pageName === "facilities") initFacilitiesPage();
  if (pageName === "profile") renderProfilePage();

  window.scrollTo(0, 0);
}

/* ============================================================
   Profile Page
   ============================================================ */

const PROFILE_STORAGE_KEY = "denguesenseqc_profile_v1";
let profileEditing = false;
let profileDraft = null;

function defaultProfile() {
  return {
    name: "Guest User",
    title: "Public User",
    email: "",
    organization: "",
    location: "Quezon City, Philippines",
    username: "guest_user",
    password: "",
    avatar: null,
    access: "Public User",
    memberSince: new Date().toISOString()
  };
}

function getCurrentUser() {
  if (typeof home_getCurrentUser === "function") return home_getCurrentUser();
  try {
    const raw = localStorage.getItem("denguesense_current_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function loadProfile() {
  const currentUser = getCurrentUser();
  if (currentUser && currentUser.id) {
    try {
      fetch(`${API}/api/profile/${currentUser.id}`)
        .then(res => res.json())
        .then(data => {
          if (data && data.profile) {
            const dbProf = data.profile;
            const mapped = {
              name: dbProf.name || currentUser.email.split("@")[0],
              title: dbProf.title || "Public User",
              email: dbProf.email || currentUser.email,
              organization: dbProf.organization || "",
              location: dbProf.location || "Quezon City, Philippines",
              username: currentUser.email.split("@")[0],
              avatar: dbProf.avatar || null,
              access: dbProf.role === "admin" ? "Administrator" : "Public User",
              memberSince: dbProf.created_at || new Date().toISOString()
            };
            localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(mapped));
          }
        })
        .catch(err => console.warn("Could not sync profile from DB:", err));
    } catch {
      // ignore network errors on load
    }
  }

  try {
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) {
      const fresh = defaultProfile();
      if (currentUser) {
        fresh.name = currentUser.email.split("@")[0];
        fresh.email = currentUser.email;
        fresh.access = currentUser.role === "admin" ? "Administrator" : "Public User";
      }
      localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(fresh));
      return fresh;
    }
    const parsed = JSON.parse(raw);
    return { ...defaultProfile(), ...parsed };
  } catch {
    return defaultProfile();
  }
}

function saveProfile(profile) {
  try {
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
    const currentUser = getCurrentUser();
    if (currentUser && currentUser.id) {
      fetch(`${API}/api/profile/${currentUser.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: profile.name,
          title: profile.title,
          organization: profile.organization,
          location: profile.location,
          avatar: profile.avatar,
          password: profile.password
        })
      }).catch(err => console.warn("Could not save profile to DB:", err));
    }
  } catch (err) {
    console.warn("Could not save profile:", err);
  }
}

function profileInitials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function formatMemberSince(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function setProfileFieldValue(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function setProfileInputValue(id, value) {
  const el = document.getElementById(id);
  if (el) el.value = value ?? "";
}

function renderProfileAvatar(profile) {
  const img = document.getElementById("profile-avatar-img");
  const fallback = document.getElementById("profile-avatar-fallback");
  if (!img || !fallback) return;
  if (profile.avatar) {
    img.src = profile.avatar;
    img.hidden = false;
    fallback.hidden = true;
  } else {
    img.hidden = true;
    fallback.hidden = false;
    fallback.textContent = profileInitials(profile.name);
  }
}

function renderProfilePage() {
  const profile = loadProfile();

  renderProfileAvatar(profile);

  setProfileFieldValue("profile-name-display", profile.name || "Unnamed User");
  setProfileFieldValue("profile-title-display", profile.title || "Public User");
  setProfileFieldValue("profile-email-display", profile.email || "No email set");
  setProfileFieldValue("profile-org-display", profile.organization || "No organization set");
  setProfileFieldValue("profile-location-display", profile.location || "No location set");

  setProfileFieldValue("profile-username-display", profile.username || "--");
  setProfileFieldValue("profile-access-display", profile.access || "Public User");
  setProfileFieldValue("profile-password-display", profile.password ? "•".repeat(10) : "Not set");
  setProfileFieldValue("profile-membersince-display", formatMemberSince(profile.memberSince));

  setProfileInputValue("profile-name-input", profile.name);
  setProfileInputValue("profile-title-input", profile.title);
  setProfileInputValue("profile-email-input", profile.email);
  setProfileInputValue("profile-org-input", profile.organization);
  setProfileInputValue("profile-location-input", profile.location);
  setProfileInputValue("profile-username-input", profile.username);
  setProfileInputValue("profile-password-input", "");
}

function enterProfileEditMode() {
  profileEditing = true;
  profileDraft = loadProfile();

  document.getElementById("page-profile")?.classList.add("is-editing");
  document.getElementById("profile-banner-card")?.classList.add("is-editing");
  document.getElementById("page-profile")?.querySelector(".profile-account-card")?.classList.add("is-editing");

  const editBtn = document.getElementById("profile-edit-btn");
  const saveBtn = document.getElementById("profile-save-btn");
  const cancelBtn = document.getElementById("profile-cancel-btn");
  if (editBtn) editBtn.hidden = true;
  if (saveBtn) saveBtn.hidden = false;
  if (cancelBtn) cancelBtn.hidden = false;

  document.getElementById("profile-name-input")?.focus();
}

function exitProfileEditMode() {
  profileEditing = false;
  document.getElementById("page-profile")?.classList.remove("is-editing");
  document.getElementById("profile-banner-card")?.classList.remove("is-editing");
  document.getElementById("page-profile")?.querySelector(".profile-account-card")?.classList.remove("is-editing");

  const editBtn = document.getElementById("profile-edit-btn");
  const saveBtn = document.getElementById("profile-save-btn");
  const cancelBtn = document.getElementById("profile-cancel-btn");
  if (editBtn) editBtn.hidden = false;
  if (saveBtn) saveBtn.hidden = true;
  if (cancelBtn) cancelBtn.hidden = true;
}

function saveProfileEdits() {
  const profile = loadProfile();

  const name = document.getElementById("profile-name-input")?.value.trim();
  const title = document.getElementById("profile-title-input")?.value.trim();
  const email = document.getElementById("profile-email-input")?.value.trim();
  const organization = document.getElementById("profile-org-input")?.value.trim();
  const location = document.getElementById("profile-location-input")?.value.trim();
  const username = document.getElementById("profile-username-input")?.value.trim();
  const newPassword = document.getElementById("profile-password-input")?.value;

  if (!username) {
    alert("Username can't be empty.");
    return;
  }

  profile.name = name || profile.name;
  profile.title = title;
  profile.email = email;
  profile.organization = organization;
  profile.location = location;
  profile.username = username;
  if (newPassword) profile.password = newPassword;
  // access and memberSince are system-managed and are never edited here.

  saveProfile(profile);
  exitProfileEditMode();
  renderProfilePage();
}

function cancelProfileEdits() {
  exitProfileEditMode();
  renderProfilePage();
}

function handleProfileAvatarFile(file) {
  if (!file || !file.type.startsWith("image/")) return;
  const reader = new FileReader();
  reader.onload = () => {
    const profile = loadProfile();
    profile.avatar = reader.result;
    saveProfile(profile);
    renderProfileAvatar(profile);
  };
  reader.readAsDataURL(file);
}

function logoutProfile() {
  const confirmed = confirm("Log out of DengueSense QC?");
  if (!confirmed) return;
  try {
    localStorage.removeItem(PROFILE_STORAGE_KEY);
    localStorage.removeItem("denguesense_current_user");
  } catch {
    /* ignore */
  }
  if (typeof home_clearCurrentUser === "function") home_clearCurrentUser();
  exitProfileEditMode();
  showPage("dashboard");
  if (typeof home_showLanding === "function") home_showLanding();
}

function bindProfileControls() {
  document.getElementById("profile-edit-btn")?.addEventListener("click", enterProfileEditMode);
  document.getElementById("profile-save-btn")?.addEventListener("click", saveProfileEdits);
  document.getElementById("profile-cancel-btn")?.addEventListener("click", cancelProfileEdits);
  document.getElementById("profile-logout-btn")?.addEventListener("click", logoutProfile);

  const avatarBtn = document.getElementById("profile-avatar-btn");
  const avatarInput = document.getElementById("profile-avatar-input");
  avatarBtn?.addEventListener("click", () => avatarInput?.click());
  avatarInput?.addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    handleProfileAvatarFile(file);
    e.target.value = "";
  });
}

function toggleAdvancedMode() {
  const advancedToggle = document.getElementById("advanced-toggle");
  const advancedFields = document.getElementById("advanced-fields");
  if (!advancedToggle || !advancedFields) return;
  advancedFields.classList.toggle("active", advancedToggle.checked);
}

// Data Fetching Helpers
async function fetchPrototype(endpoint, fallbackValue) {
  try {
    const response = await fetch(`${API}${endpoint}`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const data = await response.json();
    updateMetadata(data);
    return { data, isFallback: false };
  } catch (err) {
    console.warn(`Fallback for ${endpoint}:`, err.message);
    return { data: fallbackValue, isFallback: true };
  }
}

function setCurrentDateDisplay() {
  // Always show today's actual date (client-side), refreshed every time the
  // site is opened — not a data-provided "last updated" timestamp. Called
  // unconditionally at startup, independent of whether the live API is reachable.
  const dateStr = new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
  document.querySelectorAll(".sample-date-display").forEach(el => { el.textContent = dateStr; });
}

function updateMetadata(data) {
  const referenceYear = data.data_provenance?.authoritative_reference?.reference_year
    || data.reference_year
    || window.CPDD_REFERENCE_2020?.reference_year
    || 2020;
  document.querySelectorAll(".cpdd-year-display").forEach(el => { el.textContent = referenceYear; });
}

// Page: Dashboard
async function loadDashboardData() {
  const { data, isFallback } = await fetchPrototype("/prototype/dashboard", {
    ...window.OFFLINE_METADATA,
    alerts: window.SAMPLE_ALERTS,
    districts: window.SAMPLE_DISTRICT_SUMMARY
  });
  renderDashboard(data, isFallback);
}

function renderHealthAlerts() {
  const alertContainer = document.getElementById("sample-alerts-container");
  if (!alertContainer) return;

  if (!window.__forecastRevealed) {
    alertContainer.innerHTML = '<div class="history-state empty" style="padding:20px">Run a forecast to see active health alerts.</div>';
    return;
  }

  const healthAlerts = window.__pendingHealthAlerts || [];
  alertContainer.innerHTML = healthAlerts.length === 0
    ? '<div class="history-state empty" style="padding:20px">No active health alerts.</div>'
    : healthAlerts.map(a => `
      <div class="risk-alert ${a.level}">
        <div class="alert-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <path d="M12 9v4"/>
            <path d="M12 17h.01"/>
          </svg>
        </div>
        <div class="risk-alert-copy">
          <div class="risk-alert-title">${escapeHtml(a.title)}</div>
          <div class="risk-alert-desc">${escapeHtml(a.description)}</div>
          <div class="risk-alert-time">${escapeHtml(a.time)}</div>
        </div>
      </div>`).join("");
}

function calculateTrend(current, previous) {
  if (previous === undefined || previous === null || previous === 0) return { text: "N/A", class: "neutral" };
  const diff = ((current - previous) / previous) * 100;
  const sign = diff > 0 ? "+" : "";
  const cls = diff > 0 ? "up" : (diff < 0 ? "down" : "neutral");
  return { text: `${sign}${diff.toFixed(1)}%`, class: cls };
}

function renderDashboard(data, isFallback) {
  const alertContainer = document.getElementById("sample-alerts-container");
  const summaryContainer = document.getElementById("sample-summary-container");
  const gridContainer = document.getElementById("dashboard-district-grid");
  // Note: the "Offline Mode" / "CPDD/PSA 2020 Reference" / "Latest Epidemiological Data" /
  // "Active Forecast Period" badges that used to be built here and injected into
  // #dynamic-header-badges have been removed per request. The static "Last updated"
  // badge already in index.html is left as-is and is populated separately by updateMetadata().

  // Update KPIs
  if (data.districts) {
    const totalCases = data.districts.reduce((sum, d) => sum + (d.sampleCases || 0), 0);
    const prevTotalCases = data.districts.reduce((sum, d) => sum + (d.prevCases || 0), 0);
    const totalForecast = data.districts.reduce((sum, d) => sum + (d.forecast || 0), 0);
    const highRiskCount = data.districts.filter(d => d.risk === "high").length;

    const kpiCases = document.getElementById("kpi-sample-cases");
    const kpiForecast = document.getElementById("kpi-total-forecast");
    const kpiHighRisk = document.getElementById("kpi-high-risk");
    const kpiMonitored = document.getElementById("kpi-districts");

    if (kpiCases) {
      // Don't reveal current case counts until the user has actually run a forecast.
      const trend = calculateTrend(totalCases, prevTotalCases);
      kpiCases.dataset.pendingValue = totalCases;
      kpiCases.dataset.pendingTrendText = trend.text;
      kpiCases.dataset.pendingTrendClass = trend.class;
      if (window.__forecastRevealed) {
        kpiCases.textContent = totalCases;
        const trendEl = kpiCases.parentElement.querySelector(".kpi-trend");
        if (trendEl) { trendEl.textContent = trend.text; trendEl.className = `kpi-trend ${trend.class}`; }
      } else {
        kpiCases.textContent = "--";
      }
    }
    if (kpiForecast) {
      // Don't reveal the predicted total until the user has actually opened/run a forecast.
      // Stash the computed value + its trend for later instead of showing it up front.
      const trend = calculateTrend(totalForecast, totalCases);
      kpiForecast.dataset.pendingValue = totalForecast;
      kpiForecast.dataset.pendingTrendText = trend.text;
      kpiForecast.dataset.pendingTrendClass = trend.class;
      if (window.__forecastRevealed) {
        revealForecastKpi();
      }
    }
    if (kpiHighRisk) kpiHighRisk.textContent = highRiskCount;
    if (kpiMonitored) kpiMonitored.textContent = data.districts.length;
  }

  // Render Risk Cards Grid
  if (gridContainer && data.districts) {
    const revealed = !!window.__forecastRevealed;
    gridContainer.innerHTML = data.districts.map(d => {
      const id = d.district.split(" ")[1];
      const riskClass = d.risk.toLowerCase();

      // Simulate Environmental Tags for presentation
      let tags = "";
      if (id === "II") tags = '<span class="simulation-tag tag-waste">High Waste</span><span class="simulation-tag tag-flood">Flood Prone</span>';
      if (id === "V") tags = '<span class="simulation-tag tag-water">Nearby Creek</span>';
      if (id === "IV") tags = '<span class="simulation-tag tag-waste">Dense Area</span>';

      return `
        <div class="dashboard-district-card ${revealed ? riskClass : 'neutral'}" data-risk-card="${riskClass}" onclick="showPage('districts'); setTimeout(() => window.showDistrictDetail('${id}'), 100)">
          <div class="district-card-name">${escapeHtml(d.district)}</div>
          <div class="risk-pill card-risk-pill ${revealed ? riskClass : 'neutral'}" data-risk="${riskClass}">${revealed ? riskLabel(d.risk) : '--'}</div>
          <div class="district-card-metric" data-cases="${d.sampleCases}">${revealed ? d.sampleCases : '--'} cases</div>
          <div class="district-card-reference">${Number(d.population_2020).toLocaleString("en-US")} people</div>
          <div class="district-card-tags">${tags}</div>
        </div>`;
    }).join("");
  }

  if (alertContainer && data.alerts) {
    // Only show health alerts here — weather/other alert types are excluded.
    // Falls back to matching the title if an alert has no explicit "type"
    // (e.g. from a live API that doesn't send one).
    const healthAlerts = data.alerts.filter(a =>
      a.type ? a.type === "health" : /health/i.test(a.title || "")
    );
    // Alerts are derived from current case data, so don't reveal them until
    // the user has actually run a forecast — same rule as the rest of the dashboard.
    window.__pendingHealthAlerts = healthAlerts;
    renderHealthAlerts();
  }

  if (summaryContainer && data.districts) {
    const revealed = !!window.__forecastRevealed;
    const rows = data.districts.map(d => {
      const risk = d.risk.toLowerCase();
      return `
      <tr>
        <td>
          <div class="district-cell">
            <span class="district-indicator ${revealed ? risk : 'neutral'}" data-risk="${risk}"></span>
            ${escapeHtml(d.district)}
          </div>
        </td>
        <td>${Number(d.population_2020).toLocaleString("en-US")}</td>
        <td>${escapeHtml(d.barangay_count)}</td>
        <td class="summary-cases" data-value="${escapeHtml(d.sampleCases)}">${revealed ? escapeHtml(d.sampleCases) : '--'}</td>
        <td class="forecast-cell summary-forecast" data-value="${escapeHtml(d.forecast)}">${revealed ? escapeHtml(d.forecast) : '--'}</td>
        <td class="summary-risk" data-risk="${risk}">${revealed
          ? `<span class="risk-pill ${risk}">${escapeHtml(riskLabel(d.risk))}</span>`
          : `<span class="risk-pill neutral">--</span>`}</td>
      </tr>`;
    }).join("");
    summaryContainer.innerHTML = `
      <div class="table-wrap">
        <div class="table-provenance"><strong>CPDD/PSA 2020:</strong> population and barangay count · <strong>Research:</strong> cases, forecast, and risk</div>
        <table class="data-table">
          <thead>
            <tr><th>District</th><th>Population 2020</th><th>Barangays</th><th>Weekly Cases</th><th>Forecast</th><th>Risk Level</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }
}

// Page: Forecast
async function loadShortTermForecast(districtId, selectedBarangays) {
  const container = document.getElementById("short-term-forecast-container");
  if (!container) return;

  selectedBarangays = selectedBarangays || [];
  container.innerHTML = '<div class="history-state loading">Loading forecast...</div>';

  const { data, isFallback } = await fetchPrototype("/prototype/forecast", {
    ...window.OFFLINE_METADATA,
    forecasts: window.SAMPLE_FORECASTS
  });

  const f = data.forecasts[districtId];
  if (!f) return;

  const districtData = window.CPDD_REFERENCE_2020?.districts?.[districtId];
  const districtName = districtData?.name || f.district || `District ${districtId}`;
  const totalBarangays = districtData?.barangays?.length || 0;

  let contextHtml;
  if (selectedBarangays.length === 0) {
    contextHtml = `<div class="forecast-scope">Scope: <strong>${escapeHtml(districtName)}</strong> — all ${totalBarangays} barangays</div>`;
  } else {
    contextHtml = `
      <div class="forecast-scope">
        Scope: <strong>${escapeHtml(districtName)}</strong> — ${selectedBarangays.length} barangay${selectedBarangays.length !== 1 ? 's' : ''} selected
        <div class="forecast-scope-list">${selectedBarangays.map(escapeHtml).join(", ")}</div>
        <div class="forecast-scope-note">Note: projections are modeled at the district level; barangay selection sets the context shown here, not a separate per-barangay calculation.</div>
      </div>`;
  }

    const riskKey = String(f.risk_level || "").toLowerCase();
  const now = new Date();
  const forecastTime =
    now.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }) +
    " at " +
    now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

  const riskIconSvg = riskKey === "low"
    ? '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"/><path d="m8 12.5 3 3 5-6" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    : '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/><path d="M12 17h.01" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/></svg>';

  container.innerHTML = `
    <div class="short-term-forecast">
      ${contextHtml}
      <div class="forecast-week">
        <span class="fw-label">District</span>
        <strong class="fw-val">${escapeHtml(districtName)}</strong>
      </div>
      <div class="forecast-week">
        <span class="fw-label">Predicted Cases</span>
        <strong class="fw-val" style="color:var(--blue-600)">${f.next_week_forecast} cases</strong>
      </div>
      <div class="risk-box compact ${riskKey}" style="margin-top:16px">
        <div class="risk-icon-badge">${riskIconSvg}</div>
        <div class="risk-label">Risk Assessment</div>
        <div class="risk-title">${riskLabel(f.risk_level)}</div>
        <div class="risk-time">Forecast Time: ${forecastTime}</div>
      </div>
    </div>`;

  updateForecastKpi(districtName, f.next_week_forecast, selectedBarangays);
  updateRiskKpi(f.risk_level, f.trend);
  revealForecastKpi();

  logForecastEntry({
    method: "short_term",
    districtName: districtName,
    barangays: selectedBarangays,
    riskLevel: f.risk_level,
    trend: f.trend,
    stat1: { label: "Next week", value: `${f.next_week_forecast} cases` },
    summary: `Next week: ${f.next_week_forecast} cases · Risk: ${riskLabel(f.risk_level)} · Trend: ${f.trend}`
  });
}

function updateForecastKpi(districtName, cases, barangays) {
  const casesEl = document.getElementById("kpi-forecast-cases");
  const distEl = document.getElementById("kpi-forecast-district");
  const brgyEl = document.getElementById("kpi-forecast-barangay");
  if (!casesEl || !distEl || !brgyEl) return;

  casesEl.textContent = Math.round(cases);
  distEl.textContent = districtName;

  const b = barangays || [];
  brgyEl.textContent = b.length === 0 ? "All barangays"
    : b.length <= 2 ? b.join(", ")
    : `${b.slice(0, 2).join(", ")} +${b.length - 2} more`;
}

function updateRiskKpi(riskLevel, trend) {
  const riskEl = document.getElementById("kpi-risk-level");
  const trendEl = document.getElementById("kpi-risk-trend");
  if (!riskEl) return;

  const risk = String(riskLevel || "").toLowerCase();
  riskEl.dataset.risk = risk || "neutral";
  riskEl.textContent = risk ? riskLabel(risk) : "--";

  if (trendEl) {
    trendEl.textContent = trend ? trend.charAt(0).toUpperCase() + trend.slice(1) : "--";
    trendEl.className = "kpi-trend " + (trend === "increasing" ? "down" : trend === "decreasing" ? "up" : "neutral");
  }
}

async function runInference() {
  // Note: no longer manages its own button/loading state — it's called
  // alongside loadShortTermForecast() from a single shared "Forecast" button,
  // whose disable/enable + loading bar is handled by that click handler.
  const panel = document.getElementById("result-panel");
  if (!panel) return;

  try {
    const response = await fetch(`${API}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        district: document.getElementById("forecast-district").value,
        evidence: collectEvidence()
      })
    });
    const data = await response.json();
    if (!response.ok) {
      const error = data.error || { message: "Inference failed" };
      panel.innerHTML = `
          <div class="history-state error">
            <div style="font-weight:800; margin-bottom:8px">${escapeHtml(error.code || 'ERROR')}</div>
            <p>${escapeHtml(error.message)}</p>
            ${error.action ? `<p style="margin-top:8px; font-size:11px; opacity:0.8">${escapeHtml(error.action)}</p>` : ''}
          </div>`;
      return;
    }
    renderBNResult(data);
  } catch (err) {
    panel.innerHTML = `<div class="history-state error"><p>Unable to connect to prediction server. Ensure the backend is running at ${API}.</p></div>`;
  }
}

function renderBNResult(data) {
  const panel = document.getElementById("result-panel");
  if (!panel) return;
  revealForecastKpi();
  const cls = data.map_label.toLowerCase();
  const probVal = (data.probabilities[data.map_label] * 100).toFixed(0);

  const districtId = document.getElementById("forecast-district")?.value || "";
  const districtName = window.CPDD_REFERENCE_2020?.districts?.[districtId]?.name || "";
  logForecastEntry({
    method: "bn_inference",
    districtName: districtName,
    barangays: [],
    riskLevel: data.map_label,
    stat1: { label: "Confidence", value: `${probVal}%` },
    stat2: { label: "Evidence used", value: `${data.evidence_count}/${data.feature_count}` },
    summary: `Risk: ${riskLabel(data.map_label)} (${probVal}% confidence) · Evidence used: ${data.evidence_count}/${data.feature_count}`
  });

  const barColor = cls === 'high' ? 'var(--red)' : (cls === 'medium' ? 'var(--amber)' : 'var(--green)');

  const limitationsHtml = data.limitations && data.limitations.length > 0
    ? `<div class="unresolved-box" style="margin-top:20px; padding:14px; font-size:11px">
         <h4 style="font-size:10px; margin-bottom:8px">Data Quality Notes</h4>
         <ul style="margin:0 0 0 18px; line-height:1.5">${data.limitations.map(l => `<li>${escapeHtml(l)}</li>`).join("")}</ul>
       </div>`
    : "";

  panel.innerHTML = `
    <div class="risk-box ${cls}">
      <div class="risk-icon" style="margin-bottom:20px">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" fill="currentColor"/>
          <path d="M12 9v4" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M12 17h.01" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
      </div>
      <div class="risk-title">${riskLabel(data.map_label)}</div>
      <div class="confidence-container">
        <div class="confidence-label">
          <span>Model Confidence</span>
          <span>${probVal}%</span>
        </div>
        <div class="confidence-bar-bg">
          <div class="confidence-bar-fill" style="width: ${probVal}%; background: ${barColor}"></div>
        </div>
      </div>
    </div>

    <div class="summary-section">
      <h4>Model Analysis Output</h4>
      <div class="model-output-grid">
        <div class="output-item">
          <label><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> Status</label>
          <p style="text-transform:capitalize">${escapeHtml(data.model_status)}</p>
        </div>
        <div class="output-item">
          <label><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg> Scope</label>
          <p>${escapeHtml(data.prediction_scope)}</p>
        </div>
        <div class="output-item">
          <label><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> Type</label>
          <p>${escapeHtml(data.model_type || 'BN')}</p>
        </div>
        <div class="output-item">
          <label><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg> Evidence</label>
          <p>${data.evidence_count} / ${data.feature_count}</p>
        </div>
      </div>
      ${limitationsHtml}
    </div>`;
}

// Builds the evidence object from whatever the user has set. Unset factors are
// omitted so the model treats them as unknown.
function collectEvidence() {
  const ev = {};
  document.querySelectorAll('#risk-factor-groups .ri-opt[aria-pressed="true"]').forEach((btn) => {
    ev[btn.parentElement.dataset.field] = btn.dataset.value;
  });
  return ev;
}

function renderRiskFactorHelp(field) {
  if (!field.help) return "";
  const defaultHelp = field.help.en;
  return `
        <section class="ri-field-help" id="ri-help-${field.key}" aria-labelledby="ri-help-title-${field.key}" hidden>
          <div class="ri-help-header">
            <h4 id="ri-help-title-${field.key}" lang="en">${escapeHtml(defaultHelp.title)}</h4>
            <button type="button" class="ri-help-close" lang="en" aria-label="${escapeHtml(defaultHelp.closeLabel)}" data-help-close="ri-help-${field.key}">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 6 12 12M6 18 18 6"/></svg>
            </button>
          </div>
          <div class="ri-help-languages" role="group" aria-label="Explanation language">
            <button type="button" class="ri-help-language" lang="en" aria-pressed="true" aria-controls="ri-help-${field.key}-en">English</button>
            <button type="button" class="ri-help-language" lang="tl" aria-pressed="false" aria-controls="ri-help-${field.key}-tl">Tagalog</button>
          </div>
          ${Object.entries(field.help).map(([language, help]) => `
          <div class="ri-help-content" id="ri-help-${field.key}-${language}" lang="${language}" data-help-title="${escapeHtml(help.title)}" data-help-close-label="${escapeHtml(help.closeLabel)}"${language === "en" ? "" : " hidden"}>
            <p>${escapeHtml(help.description)}</p>
            <p>${escapeHtml(help.purpose)}</p>
            <dl class="ri-help-levels">
              ${help.levels.map((level) => `<div class="ri-help-level ri-help-level-${level.tone}"><dt>${escapeHtml(level.label)}</dt><dd>${escapeHtml(level.description)}</dd></div>`).join("")}
            </dl>
            <p class="ri-help-guidance"><strong>${escapeHtml(help.guidanceLabel)}</strong> ${escapeHtml(help.guidance)}</p>
            <p class="ri-help-note">${escapeHtml(help.note)}</p>
          </div>`).join("")}
        </section>`;
}

function renderRiskGroup(group, index) {
  const fields = group.fields.map((f) => `
      <div class="ri-field">
        <div class="ri-field-info">
          <div class="ri-field-title">
            <div class="ri-field-label" id="ri-label-${f.key}">${escapeHtml(f.label)}</div>
            ${f.help ? `<button type="button" class="ri-info-button" aria-label="About ${escapeHtml(f.label)}" aria-expanded="false" aria-controls="ri-help-${f.key}">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>
            </button>` : ""}
          </div>
          <p class="ri-field-desc" id="ri-desc-${f.key}">${escapeHtml(f.desc)}</p>
        </div>
        <div class="ri-options" role="group" aria-labelledby="ri-label-${f.key}" aria-describedby="ri-desc-${f.key}" data-field="${f.key}" data-count="${f.options.length}">
          ${f.options.map(([value, label]) => `<button type="button" class="ri-opt" data-value="${value}" aria-pressed="false">${escapeHtml(label)}</button>`).join("")}
        </div>
        ${renderRiskFactorHelp(f)}
      </div>`).join("");

  return `
    <details class="ri-group ri-tone-${group.id}" data-group="${group.id}"${index === 0 ? " open" : ""}>
      <summary>
        <span class="ri-group-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${group.icon}</svg>
        </span>
        <span class="ri-group-text"><strong>${escapeHtml(group.title)}</strong><small>${escapeHtml(group.desc)}</small></span>
        <span class="ri-group-count" data-count-for="${group.id}">0/${group.fields.length}</span>
        <svg class="ri-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
      </summary>
      <div class="ri-fields">${fields}</div>
    </details>`;
}

function initRiskFactorPanel() {
  const root = document.getElementById("risk-factor-groups");
  if (!root) return;
  root.innerHTML = RISK_FACTOR_GROUPS.map(renderRiskGroup).join("");

  root.addEventListener("click", (event) => {
    const infoButton = event.target.closest(".ri-info-button");
    if (infoButton) {
      setRiskFactorHelpOpen(infoButton, infoButton.getAttribute("aria-expanded") !== "true");
      return;
    }
    const languageButton = event.target.closest(".ri-help-language");
    if (languageButton) {
      setRiskFactorHelpLanguage(languageButton);
      return;
    }
    const closeButton = event.target.closest(".ri-help-close");
    if (closeButton) {
      const trigger = root.querySelector(`[aria-controls="${closeButton.dataset.helpClose}"]`);
      setRiskFactorHelpOpen(trigger, false);
      trigger?.focus();
      return;
    }
    // Click an option to select it; click the selected option again to unset it.
    const btn = event.target.closest(".ri-opt");
    if (!btn) return;
    const wasSelected = btn.getAttribute("aria-pressed") === "true";
    btn.parentElement.querySelectorAll(".ri-opt").forEach((b) => b.setAttribute("aria-pressed", "false"));
    if (!wasSelected) btn.setAttribute("aria-pressed", "true");
    updateRiskFactorProgress();
  });

  root.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const trigger = event.target.closest(".ri-field")?.querySelector('.ri-info-button[aria-expanded="true"]');
    if (!trigger) return;
    event.preventDefault();
    setRiskFactorHelpOpen(trigger, false);
    trigger.focus();
  });

  document.getElementById("ri-expand-all")?.addEventListener("click", () => setAllRiskGroupsOpen(true));
  document.getElementById("ri-collapse-all")?.addEventListener("click", () => setAllRiskGroupsOpen(false));
  document.getElementById("ri-clear-all")?.addEventListener("click", clearRiskFactors);

  updateRiskFactorProgress();
}

function setRiskFactorHelpOpen(button, open) {
  if (!button) return;
  const panel = document.getElementById(button.getAttribute("aria-controls"));
  if (!panel) return;
  button.setAttribute("aria-expanded", String(open));
  panel.hidden = !open;
}

function setRiskFactorHelpLanguage(button) {
  const panel = button.closest(".ri-field-help");
  const content = document.getElementById(button.getAttribute("aria-controls"));
  if (!panel || !content) return;
  panel.querySelectorAll(".ri-help-language").forEach((option) => option.setAttribute("aria-pressed", String(option === button)));
  panel.querySelectorAll(".ri-help-content").forEach((version) => { version.hidden = version !== content; });
  const title = panel.querySelector(".ri-help-header h4");
  title.textContent = content.dataset.helpTitle;
  title.lang = content.lang;
  const closeButton = panel.querySelector(".ri-help-close");
  closeButton.setAttribute("aria-label", content.dataset.helpCloseLabel);
  closeButton.lang = content.lang;
}

function setAllRiskGroupsOpen(open) {
  document.querySelectorAll("#risk-factor-groups .ri-group").forEach((d) => { d.open = open; });
}

function updateRiskFactorProgress() {
  let setCount = 0;
  RISK_FACTOR_GROUPS.forEach((group) => {
    const el = document.querySelector(`#risk-factor-groups .ri-group[data-group="${group.id}"]`);
    if (!el) return;
    const n = el.querySelectorAll('.ri-opt[aria-pressed="true"]').length;
    setCount += n;
    el.classList.toggle("has-value", n > 0);
    el.classList.toggle("is-complete", n === group.fields.length);
    const badge = el.querySelector(".ri-group-count");
    if (badge) badge.textContent = `${n}/${group.fields.length}`;
  });

  const fill = document.getElementById("ri-progress-fill");
  const text = document.getElementById("ri-progress-text");
  if (fill) fill.style.width = `${(setCount / RISK_FACTOR_TOTAL) * 100}%`;
  if (text) text.textContent = `${setCount} of ${RISK_FACTOR_TOTAL} factors set`;
}

function clearRiskFactors() {
  document.querySelectorAll('#risk-factor-groups .ri-opt[aria-pressed="true"]').forEach((b) => b.setAttribute("aria-pressed", "false"));
  updateRiskFactorProgress();
}

function resetForm() {
  clearRiskFactors();
  const panel = document.getElementById("result-panel");
  if (panel) panel.innerHTML = '<div class="no-result"><p>Select options and click "Forecast."</p></div>';
}

async function runLSTMForecast() {
  const btn = document.getElementById("get-forecast-btn");
  const loading = document.getElementById("lstm-loading");
  const result = document.getElementById("lstm-result");
  const originalBtnLabel = btn ? btn.textContent : "Get Forecast";

  if (btn) { btn.disabled = true; btn.textContent = "Preparing model..."; }
  if (loading) loading.classList.add("active");

  try {
    const response = await fetch(`${API}/lstm/forecast`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        area: document.getElementById("lstm-area").value,
        weeks: document.getElementById("lstm-weeks").value
      })
    });
    const data = await response.json();
    if (!response.ok) {
      const error = data.error || { message: "Forecast failed" };
      result.innerHTML = `
          <div class="history-state error" style="min-height:100px; padding:20px">
            <div style="font-weight:800; font-size:12px">${escapeHtml(error.code || 'ERROR')}</div>
            <p style="font-size:11px">${escapeHtml(error.message)}</p>
          </div>`;
      return;
    }
    renderLSTMResult(data);
  } catch (err) {
    result.innerHTML = '<div class="history-state error" style="min-height:100px; padding:20px"><p style="font-size:11px">Connection failed</p></div>';
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = originalBtnLabel || "Get Forecast"; }
    if (loading) loading.classList.remove("active");
  }
}

function renderLSTMResult(data) {
  const result = document.getElementById("lstm-result");
  revealForecastKpi();

  const lstmAreaSelect = document.getElementById("lstm-area");
  const areaLabel = lstmAreaSelect?.options[lstmAreaSelect.selectedIndex]?.textContent || data.prediction_scope || "Quezon City (All)";
  const lastWeekIdx = data.predictions.length - 1;
  logForecastEntry({
    method: "lstm",
    districtName: areaLabel,
    barangays: [],
    stat1: { label: "Next week", value: `${data.predictions[0].predicted_cases.toFixed(1)} cases` },
    stat2: { label: `Week ${data.predictions.length}`, value: `${data.predictions[lastWeekIdx].predicted_cases.toFixed(1)} cases` },
    summary: `W1: ${data.predictions[0].predicted_cases.toFixed(1)} cases · W${data.predictions.length}: ${data.predictions[lastWeekIdx].predicted_cases.toFixed(1)} cases`
  });

  const assumptionsHtml = data.assumptions && data.assumptions.length > 0
    ? `<div style="margin-top:10px; font-size:10px; color:var(--muted); line-height:1.4">Assumptions: ${data.assumptions.join(", ")}</div>`
    : "";

  result.innerHTML = `
    <h4>Model Analysis Output</h4>
    <div class="summary-row"><span class="sk">Scope</span><span class="sv">${escapeHtml(data.prediction_scope)}</span></div>
    <div class="summary-row">
      <span class="sk">Next Week Projection</span>
      <strong class="sv" style="color:var(--blue-600); font-size:16px">${data.predictions[0].predicted_cases.toFixed(1)} cases</strong>
    </div>
    <div class="summary-row" style="border-bottom:0">
      <span class="sk">W${data.predictions.length} Projection</span>
      <span class="sv">${data.predictions[data.predictions.length - 1].predicted_cases.toFixed(1)} cases</span>
    </div>
    <div class="confidence-container" style="margin-top:15px">
      <div class="confidence-label"><span>Model Stability</span><span>Stable</span></div>
      <div class="confidence-bar-bg"><div class="confidence-bar-fill" style="width: 85%; background: var(--blue-600)"></div></div>
    </div>
    ${assumptionsHtml}
  `;
}

async function loadLSTMAreas() {
  const select = document.getElementById("lstm-area");
  if (!select) return;
  try {
    const response = await fetch(`${API}/lstm/areas`);
    if (!response.ok) return;
    const { areas } = await response.json();
    if (areas && areas.length > 0) {
      select.innerHTML = areas.map(a => `<option value="${escapeHtml(a.toLowerCase())}">${escapeHtml(a)}</option>`).join("");
    }
  } catch (err) {
    console.warn("Failed to load LSTM areas:", err.message);
  }
}

// Page: Districts
async function loadDistrictsData() {
  const grid = document.getElementById("districts-grid");
  if (!grid) return;

  grid.innerHTML = '<div class="history-state loading">Loading districts...</div>';

  const { data, isFallback } = await fetchPrototype("/prototype/districts", {
    ...window.OFFLINE_METADATA,
    districts: window.SAMPLE_DISTRICTS_DETAIL
  });

  if (!data.districts) {
    grid.innerHTML = '<div class="history-state error">Unable to load district data.</div>';
    return;
  }

  // Normalize data: Handle both Array (real data) and Object (legacy sample)
  const districtsArray = Array.isArray(data.districts)
    ? data.districts
    : Object.entries(data.districts).map(([id, d]) => ({ ...d, id }));

  grid.innerHTML = districtsArray.map(d => {
    const name = d.name || d.district || "Unknown District";
    const id = d.id || name.split(" ")[1] || "?";
    const popCount = Number(d.population_2020 || 0).toLocaleString("en-US");
    const bgyCount = d.barangay_count || 0;

    return `
      <div class="dist-card" data-id="${id}" tabindex="0" role="button" aria-label="View details for ${escapeHtml(name)}">
        <div class="dist-card-header">
          <div class="dist-name">District ${id}</div>
        </div>

        <div class="metric-section population-section">
          <div class="metric-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
          </div>
          <div class="metric-content">
            <div class="metric-row">
              <div class="metric-group">
                <div class="metric-label">Population</div>
                <div class="metric-value">${popCount}</div>
              </div>
              <div class="metric-group align-right">
                <div class="metric-subvalue">${bgyCount}</div>
                <div class="metric-label">barangays</div>
              </div>
            </div>
          </div>
        </div>

        <div class="dist-card-footer">
          Sources: CPDD 2020
        </div>
      </div>`;
  }).join("");

  grid.querySelectorAll(".dist-card").forEach(c => {
    const handler = () => showDistrictDetail(c.dataset.id);
    c.addEventListener("click", handler);
    c.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handler(); } });
  });
}

function renderDistrictDetailSituation() {
  const info = window.__lastDistrictDetail;
  const banner = document.getElementById("det-situation-banner");
  const casesEl = document.getElementById("det-cases");
  const pillEl = document.getElementById("det-pill");
  if (!info || !banner || !casesEl || !pillEl) return;

  if (!window.__forecastRevealed) {
    banner.className = "situation-banner neutral-risk";
    casesEl.textContent = "--";
    pillEl.textContent = "--";
    pillEl.className = "risk-pill-large neutral";
    return;
  }

  banner.className = `situation-banner ${info.risk}-risk`;
  casesEl.textContent = info.cases;
  pillEl.textContent = `${riskLabel(info.risk)} (${info.statusLabel})`;
  pillEl.className = `risk-pill-large ${info.risk}`;
}

window.showDistrictDetail = async function (id) {
  const detailCard = document.getElementById("district-detail-card");
  detailCard.hidden = false;

  const { data, isFallback } = await fetchPrototype(`/prototype/districts/${id}`, {
    ...window.OFFLINE_METADATA,
    district: window.SAMPLE_DISTRICTS_DETAIL[id]
  });

  const d = data.district;
  const name = d.name || d.district || `District ${id}`;

  document.getElementById("det-breadcrumb-name").textContent = name;
  document.getElementById("det-name").textContent = name;
  document.getElementById("det-bgy-count-header").textContent = d.barangay_count || 0;

  // Dengue Situation Banner — case count and risk status are gated behind
  // the same "no result until forecast" rule as the rest of the app.
  const risk = d.risk ? d.risk.toLowerCase() : "low";
  const cases = d.sampleCases || d.recent_cases || 0;
  const statusLabel = d.status || (risk === "high" ? "Warning" : (risk === "medium" ? "Monitoring" : "Stable"));
  window.__lastDistrictDetail = { risk, cases, statusLabel };
  renderDistrictDetailSituation();

  // Profile Tiles
  document.getElementById("det-population").textContent = Number(d.population_2020 || 0).toLocaleString("en-US");
  document.getElementById("det-area").textContent = d.land_area_sq_km ? `${Number(d.land_area_sq_km).toFixed(2)} km²` : "-";
  document.getElementById("det-density").textContent = d.population_density_per_ha ? `${Number(d.population_density_per_ha).toLocaleString("en-US")} persons/ha` : "-";
  document.getElementById("det-barangay-count").textContent = d.barangay_count || 0;

  // Accordion
  document.getElementById("det-accordion-title").textContent = `Barangays in ${name}`;
  document.getElementById("det-coverage").textContent = (d.barangays || []).join(", ") || d.coverage || "No coverage info";

  document.querySelectorAll(".dist-card").forEach(c => {
    c.classList.toggle("active", c.dataset.id === id);
  });

  detailCard.scrollIntoView({ behavior: 'smooth' });
};

// Page: Historical — now a log of the user's own forecast runs (starts empty)
const FORECAST_HISTORY_KEY = "denguesense_qc_forecast_history";
let currentHistoricalData = [];

function getForecastHistory() {
  try {
    const raw = localStorage.getItem(FORECAST_HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    console.warn("Could not read forecast history:", err.message);
    return [];
  }
}

function saveForecastHistory(list) {
  try {
    localStorage.setItem(FORECAST_HISTORY_KEY, JSON.stringify(list));
  } catch (err) {
    console.warn("Could not save forecast history:", err.message);
  }
}

function logForecastEntry(entry) {
  const history = getForecastHistory();
  history.unshift({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: new Date().toISOString(),
    ...entry
  });
  // Keep the log from growing unbounded
  saveForecastHistory(history.slice(0, 300));

  // If the Historical page is currently visible, refresh it live
  const historyPage = document.getElementById("page-history");
  if (historyPage && historyPage.classList.contains("active")) {
    renderHistoricalTable();
  }
  updateHistoryCountBadge();
}

function updateHistoryCountBadge() {
  const badge = document.getElementById("history-count-badge");
  if (!badge) return;
  const count = getForecastHistory().length;
  badge.textContent = count === 0 ? "0 forecasts logged" : `${count} forecast${count !== 1 ? 's' : ''} logged`;
}

function formatHistoryTimestamp(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

const METHOD_LABELS = {
  short_term: "Short-term Forecast",
  bn_inference: "Risk Inference",
  lstm: "LSTM Forecast"
};

async function loadHistoricalData() {
  const content = document.getElementById("history-content");
  if (!content) return;
  try {
    const res = await fetch(`${API}/api/forecast/history`);
    if (res.ok) {
      const data = await res.json();
      if (data && Array.isArray(data.forecasts)) {
        currentHistoricalData = data.forecasts.map(f => ({
          id: f.id,
          timestamp: f.created_at,
          method: f.prediction_method === "Bayesian Network" ? "bn_inference" : "short_term",
          districtName: f.district,
          barangays: f.selected_barangays || [],
          predictedCases: f.predicted_cases,
          riskLevel: f.risk_level,
          confidence: f.confidence
        }));
        renderHistoricalTable();
        return;
      }
    }
  } catch (err) {
    console.warn("Could not fetch remote forecast history, using local cache:", err);
  }
  renderHistoricalTable();
}

function renderHistoricalTable() {
  const content = document.getElementById("history-content");
  if (!content) return;

  currentHistoricalData = getForecastHistory();
  updateHistoryCountBadge();

  if (currentHistoricalData.length === 0) {
    content.innerHTML = `
      <div class="history-state empty">
        <p>No forecasts yet.</p>
        <p style="margin-top:6px; font-size:12.5px; color:var(--muted)">
          Go to the Dashboard, click <strong>"Run a Forecast"</strong>, and try Get Forecast, Run Inference, or the LSTM tool — every forecast you run will show up here.
        </p>
        <button type="button" class="btn-primary" style="margin-top:14px" onclick="showPage('dashboard')">Go to Dashboard</button>
      </div>`;
    return;
  }

  const distFilter = getVal("hist-filter-district");

  const filtered = currentHistoricalData.filter(d => {
    return (!distFilter || d.districtName === distFilter);
  });

  if (filtered.length === 0) {
    content.innerHTML = '<div class="history-state empty">No logged forecasts match these filters.</div>';
    return;
  }

  const rows = filtered.map(d => `
    <tr>
      <td class="hist-datetime">${escapeHtml(formatHistoryTimestamp(d.timestamp))}</td>
      <td><span class="hist-method-pill">${escapeHtml(METHOD_LABELS[d.method] || d.method)}</span></td>
      <td class="hist-district">${escapeHtml(d.districtName || "—")}</td>
      <td>${formatBarangayCell(d.barangays)}</td>
      <td>${formatResultCell(d)}</td>
    </tr>`).join("");

  content.innerHTML = `
    <div class="table-wrap">
      <table class="hist-table">
        <thead><tr><th>Date &amp; Time</th><th>Method</th><th>District</th><th>Barangay(s)</th><th>Result</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function formatBarangayCell(barangays) {
  if (!barangays || barangays.length === 0) {
    return '<span class="hist-all-barangays">All barangays</span>';
  }
  if (barangays.length <= 3) {
    return `<span class="hist-barangay-inline">${escapeHtml(barangays.join(", "))}</span>`;
  }
  const preview = barangays.slice(0, 3).map(escapeHtml).join(", ");
  return `
    <details class="hist-barangay-details">
      <summary>${preview} <span class="hist-more-count">+${barangays.length - 3} more</span></summary>
      <div class="hist-barangay-full">${escapeHtml(barangays.join(", "))}</div>
    </details>`;
}

const TREND_ICONS = {
  increasing: { arrow: "M3 17l6-6 4 4 8-8 M15 7h6v6", color: "var(--red)" },
  decreasing: { arrow: "M3 7l6 6 4-4 8 8 M15 17h6v-6", color: "var(--green)" },
  stable: { arrow: "M4 12h16", color: "var(--muted)" }
};

function formatResultCell(d) {
  // Structured, badge-based result. Falls back to the plain summary string
  // for entries logged before this format existed (already in localStorage).
  const hasStructured = d.riskLevel || d.stat1 || d.stat2 || d.trend;
  if (!hasStructured) {
    return `<span class="hist-legacy-summary">${escapeHtml(d.summary || "—")}</span>`;
  }

  const parts = [];

  if (d.riskLevel) {
    const risk = String(d.riskLevel).toLowerCase();
    parts.push(`<span class="risk-pill hist-result-pill ${risk}">${escapeHtml(riskLabel(risk))}</span>`);
  }

  if (d.stat1) {
    parts.push(`<span class="hist-stat"><strong>${escapeHtml(d.stat1.value)}</strong><span class="hist-stat-label">${escapeHtml(d.stat1.label)}</span></span>`);
  }
  if (d.stat2) {
    parts.push(`<span class="hist-stat"><strong>${escapeHtml(d.stat2.value)}</strong><span class="hist-stat-label">${escapeHtml(d.stat2.label)}</span></span>`);
  }

  if (d.trend) {
    const t = TREND_ICONS[d.trend] || TREND_ICONS.stable;
    parts.push(`
      <span class="hist-trend" style="color:${t.color}">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="${t.arrow}"/></svg>
        ${escapeHtml(d.trend)}
      </span>`);
  }

  return `<div class="hist-result-row">${parts.join("")}</div>`;
}

function getVal(id) { const element = document.getElementById(id); return element ? element.value : ""; }

// --- Facilities Map Module (CPDDO 2026) ---
let currentFacilityId = "health";
const FACILITY_MIN_ZOOM = 0.5;
const FACILITY_MAX_ZOOM = 4.0;
let facilityZoom = 1.0;
let facilityPanX = 0;
let facilityPanY = 0;
let isFacilityDragging = false;
let facilityDragStartX = 0;
let facilityDragStartY = 0;
let facilityInitialized = false;

function initFacilitiesPage() {
  renderFacilityCategory(currentFacilityId);

  // Wire View facilities from district detail card if not already wired
  const distFacBtn = document.getElementById("btn-view-district-facilities");
  if (distFacBtn && !distFacBtn.dataset.wired) {
    distFacBtn.dataset.wired = "true";
    distFacBtn.addEventListener("click", () => {
      showPage("facilities");
      const healthTab = document.querySelector('.facility-tab[data-cat="health"]');
      if (healthTab) healthTab.click();
    });
  }

  if (facilityInitialized) return;
  facilityInitialized = true;

  // Re-fit the map whenever the image finishes loading or the window resizes
  const facilityImg = document.getElementById("facility-active-img");
  if (facilityImg) facilityImg.addEventListener("load", resetFacilityTransform);
  window.addEventListener("resize", updateFacilityTransform);
  setTimeout(resetFacilityTransform, 100);

  // Category tab clicks
  const tabs = document.querySelectorAll(".facility-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      currentFacilityId = tab.dataset.cat;
      renderFacilityCategory(currentFacilityId);
    });
  });

  // Zoom controls
  const btnZoomIn = document.getElementById("btn-zoom-in");
  const btnZoomOut = document.getElementById("btn-zoom-out");
  const btnZoomReset = document.getElementById("btn-zoom-reset");
  const btnFullscreen = document.getElementById("btn-fullscreen");
  const btnExitFullscreen = document.getElementById("btn-exit-fullscreen");
  const viewport = document.getElementById("facilities-viewport");
  const canvas = document.getElementById("facilities-canvas");

  if (btnZoomIn) {
    btnZoomIn.addEventListener("click", () => {
      facilityZoom = Math.min(facilityZoom + 0.25, FACILITY_MAX_ZOOM);
      updateFacilityTransform();
    });
  }

  if (btnZoomOut) {
    btnZoomOut.addEventListener("click", () => {
      facilityZoom = Math.max(facilityZoom - 0.25, FACILITY_MIN_ZOOM);
      updateFacilityTransform();
    });
  }

  if (btnZoomReset) {
    btnZoomReset.addEventListener("click", () => {
      resetFacilityTransform();
    });
  }

  const toggleFullscreen = () => {
    if (!viewport) return;
    const isFull = viewport.classList.toggle("is-fullscreen");
    if (isFull) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    setTimeout(resetFacilityTransform, 50);
  };

  if (btnFullscreen) {
    btnFullscreen.addEventListener("click", toggleFullscreen);
  }

  if (btnExitFullscreen) {
    btnExitFullscreen.addEventListener("click", toggleFullscreen);
  }

  // Keyboard navigation for map
  window.addEventListener("keydown", (e) => {
    const facilitiesPage = document.getElementById("page-facilities");
    if (!facilitiesPage || !facilitiesPage.classList.contains("active")) return;

    if (e.key === "Escape" && viewport?.classList.contains("is-fullscreen")) {
      toggleFullscreen();
    } else if (e.key === "+" || e.key === "=") {
      facilityZoom = Math.min(facilityZoom + 0.25, FACILITY_MAX_ZOOM);
      updateFacilityTransform();
    } else if (e.key === "-" || e.key === "_") {
      facilityZoom = Math.max(facilityZoom - 0.25, FACILITY_MIN_ZOOM);
      updateFacilityTransform();
    } else if (e.key === "0") {
      resetFacilityTransform();
    }
  });

  // Pan / Drag handlers
  if (viewport && canvas) {
    viewport.addEventListener("mousedown", (e) => {
      if (e.target.closest(".viewer-btn") || e.target.closest(".exit-fullscreen-btn")) return;
      isFacilityDragging = true;
      facilityDragStartX = e.clientX - facilityPanX;
      facilityDragStartY = e.clientY - facilityPanY;
      canvas.classList.add("dragging");
    });

    window.addEventListener("mousemove", (e) => {
      if (!isFacilityDragging) return;
      facilityPanX = e.clientX - facilityDragStartX;
      facilityPanY = e.clientY - facilityDragStartY;
      updateFacilityTransform();
    });

    window.addEventListener("mouseup", () => {
      if (isFacilityDragging) {
        isFacilityDragging = false;
        canvas.classList.remove("dragging");
      }
    });

    // Touch support for mobile/tablets
    viewport.addEventListener("touchstart", (e) => {
      if (e.touches.length === 1) {
        isFacilityDragging = true;
        facilityDragStartX = e.touches[0].clientX - facilityPanX;
        facilityDragStartY = e.touches[0].clientY - facilityPanY;
      }
    }, { passive: true });

    window.addEventListener("touchmove", (e) => {
      if (!isFacilityDragging || e.touches.length !== 1) return;
      facilityPanX = e.touches[0].clientX - facilityDragStartX;
      facilityPanY = e.touches[0].clientY - facilityDragStartY;
      updateFacilityTransform();
    }, { passive: true });

    window.addEventListener("touchend", () => {
      isFacilityDragging = false;
    });

    // Wheel zoom
    viewport.addEventListener("wheel", (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 0.2 : -0.2;
      facilityZoom = Math.max(FACILITY_MIN_ZOOM, Math.min(FACILITY_MAX_ZOOM, facilityZoom + zoomFactor));
      updateFacilityTransform();
    }, { passive: false });
  }

  // Jump to districts button
  const jumpBtn = document.getElementById("btn-jump-districts");
  if (jumpBtn) {
    jumpBtn.addEventListener("click", () => showPage("districts"));
  }
}

// Measures the viewport and map image. `base` is the smallest zoom at which
// the map still fully covers the viewport (so no empty space can show).
function getFacilityMetrics() {
  const viewport = document.getElementById("facilities-viewport");
  const img = document.getElementById("facility-active-img");
  if (!viewport || !img) return null;
  const vw = viewport.clientWidth;
  const vh = viewport.clientHeight;
  const w = img.offsetWidth;
  const h = img.offsetHeight;
  if (!vw || !vh || !w || !h) return null;
  return { vw, vh, w, h, base: Math.max(vw / w, vh / h) };
}

function updateFacilityTransform() {
  const canvas = document.getElementById("facilities-canvas");
  if (!canvas) return;

  const m = getFacilityMetrics();
  let displayZoom = 100;

  if (m) {
    // Can't zoom out past "map fills the frame"
    const maxZoom = Math.max(FACILITY_MAX_ZOOM, m.base * 2);
    facilityZoom = Math.max(m.base, Math.min(maxZoom, facilityZoom));

    // Can't pan past the map's edges
    const maxX = Math.max(0, (m.w * facilityZoom - m.vw) / 2);
    const maxY = Math.max(0, (m.h * facilityZoom - m.vh) / 2);
    facilityPanX = Math.max(-maxX, Math.min(maxX, facilityPanX));
    facilityPanY = Math.max(-maxY, Math.min(maxY, facilityPanY));

    displayZoom = Math.round((facilityZoom / m.base) * 100);
  } else {
    displayZoom = Math.round(facilityZoom * 100);
  }

  canvas.style.transform = `translate(${facilityPanX}px, ${facilityPanY}px) scale(${facilityZoom})`;
  const zoomDisplay = document.getElementById("facility-zoom-display");
  if (zoomDisplay) zoomDisplay.textContent = `${displayZoom}%`;
}

function resetFacilityTransform() {
  const m = getFacilityMetrics();
  facilityZoom = m ? m.base : 1.0;
  facilityPanX = 0;
  facilityPanY = 0;
  updateFacilityTransform();
}

function renderFacilityCategory(catId) {
  resetFacilityTransform();
  const catalog = window.QC_FACILITIES_METADATA?.categories || [];
  const cat = catalog.find(c => c.id === catId) || catalog[0];
  if (!cat) return;

  const titleEl = document.getElementById("facility-active-title");
  const badgeEl = document.getElementById("facility-active-badge");
  const imgEl = document.getElementById("facility-active-img");
  const rawDownload = document.getElementById("btn-raw-download");
  const legendList = document.getElementById("facility-legend-items");
  const contextBox = document.getElementById("facility-dengue-context");

  if (titleEl) titleEl.textContent = cat.title;
  if (badgeEl) badgeEl.textContent = cat.badge;
  if (imgEl) {
    imgEl.src = cat.web_asset_url;
    imgEl.alt = `${cat.title} - Quezon City CPDDO 2026`;
  }
  if (rawDownload) {
    rawDownload.href = cat.web_asset_url;
  }

  // Render Legend
  if (legendList) {
    legendList.innerHTML = cat.legend.map(item => `
      <div class="facility-legend-item">
        <span class="legend-swatch" style="background: ${item.color};"></span>
        <div>
          <strong>${escapeHtml(item.label)}</strong>
          <div class="legend-desc">${escapeHtml(item.description || item.shape)}</div>
        </div>
      </div>
    `).join("");
  }

  // Render Dengue Context
  if (contextBox && cat.dengue_relevance) {
    const rel = cat.dengue_relevance;
    let html = "";
    if (rel.role) {
      html += `<h5>Role in Dengue Surveillance:</h5><p>${escapeHtml(rel.role)}</p>`;
    }
    if (rel.clinical_significance) {
      html += `<h5>Clinical & Public Health Significance:</h5><p>${escapeHtml(rel.clinical_significance)}</p>`;
    }
    if (rel.flood_compound_risk) {
      html += `<h5>CDRA 2022 Compound Flood Risk:</h5><p>${escapeHtml(rel.flood_compound_risk)}</p>`;
    }
    if (rel.diurnal_exposure) {
      html += `<h5>Diurnal Mosquito Biting Window:</h5><p>${escapeHtml(rel.diurnal_exposure)}</p>`;
    }
    if (rel.environmental_focus) {
      html += `<h5>Vector Search-and-Destroy Focus:</h5><p>${escapeHtml(rel.environmental_focus)}</p>`;
    }
    contextBox.innerHTML = html;
  }
}
