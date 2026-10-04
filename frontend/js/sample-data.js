// OFFLINE FALLBACK DATA
// These values are used only when the prototype API is unreachable.

window.OFFLINE_METADATA = {
  is_sample: true,
  contains_authoritative_reference: true,
  prototype_version: "1.5.0-final",
  sample_updated_at: "2025-W52",
  data_source: "Mixed: CPDD/PSA 2020 reference plus latest epidemiological research values",
  disclaimer: "District demographics are from CPDD/PSA 2020. Cases, rainfall, forecasts, risks, status, and alerts are research-derived values based on the latest 2025 dataset.",
  data_provenance: {
    authoritative_reference: {
      fields: ["barangay membership", "barangay count", "land area", "population_2020", "population_density_per_ha"],
      source: "CPDD district maps / PSA 2020 Census population",
      reference_year: 2020
    },
    research_data: {
      fields: ["dengue cases", "rainfall", "forecast", "risk", "status", "alerts"],
      source: "Quezon City Weekly Epidemiological Dataset (2023-2025)"
    }
  }
};

function cpddDistrictContext(districtId) {
  const district = window.CPDD_REFERENCE_2020.districts[districtId];
  return {
    ...district,
    coverage: district.barangays.join(", "),
    population: district.population_2020.toLocaleString("en-US"),
    demographic_reference_year: 2020,
    demographic_source: "CPDD district maps / PSA 2020 Census population"
  };
}

window.SAMPLE_ALERTS = [
  {
    type: "health",
    title: "HEALTH ALERT - DISTRICT IV - RISING TREND",
    description: "District IV has recorded a 25% increase in cases over the last 2 weeks. Increased vector control measures recommended.",
    time: "Active",
    level: "medium"
  },
  {
    type: "weather",
    title: "WEATHER ALERT - INCREASED RAINFALL",
    description: "Recent Moderate rainfall (17.7mm) detected in W52. Monitor stagnant water in flood-prone Tier 1 barangays.",
    time: "Active",
    level: "medium"
  }
];

window.SAMPLE_DISTRICT_SUMMARY = [
  { ...cpddDistrictContext("I"), district: "District I", sampleCases: 8, prevCases: 12, forecast: 7, risk: "low" },
  { ...cpddDistrictContext("II"), district: "District II", sampleCases: 6, prevCases: 10, forecast: 5, risk: "low" },
  { ...cpddDistrictContext("III"), district: "District III", sampleCases: 10, prevCases: 15, forecast: 9, risk: "low" },
  { ...cpddDistrictContext("IV"), district: "District IV", sampleCases: 25, prevCases: 35, forecast: 22, risk: "medium" },
  { ...cpddDistrictContext("V"), district: "District V", sampleCases: 20, prevCases: 28, forecast: 18, risk: "medium" },
  { ...cpddDistrictContext("VI"), district: "District VI", sampleCases: 13, prevCases: 16, forecast: 11, risk: "low" }
];

window.SAMPLE_FORECASTS = {
  "I": { district: "District I", next_week_forecast: 7, extended_outlook: [6, 5, 5], trend: "decreasing", risk_level: "low", confidence: "high" },
  "II": { district: "District II", next_week_forecast: 5, extended_outlook: [4, 4, 3], trend: "decreasing", risk_level: "low", confidence: "high" },
  "III": { district: "District III", next_week_forecast: 9, extended_outlook: [8, 8, 7], trend: "stable", risk_level: "low", confidence: "medium" },
  "IV": { district: "District IV", next_week_forecast: 22, extended_outlook: [20, 19, 18], trend: "decreasing", risk_level: "medium", confidence: "medium" },
  "V": { district: "District V", next_week_forecast: 18, extended_outlook: [16, 15, 15], trend: "decreasing", risk_level: "medium", confidence: "medium" },
  "VI": { district: "District VI", next_week_forecast: 11, extended_outlook: [10, 9, 9], trend: "decreasing", risk_level: "low", confidence: "high" }
};

window.SAMPLE_HISTORICAL_DATA = [
  { "year": 2025, "week": 52, "district": "District I", "cases": 8, "rainfall": 17.7, "risk": "low" },
  { "year": 2025, "week": 52, "district": "District II", "cases": 6, "rainfall": 17.7, "risk": "low" },
  { "year": 2025, "week": 52, "district": "District III", "cases": 10, "rainfall": 17.7, "risk": "low" },
  { "year": 2025, "week": 52, "district": "District IV", "cases": 25, "rainfall": 17.7, "risk": "medium" },
  { "year": 2025, "week": 52, "district": "District V", "cases": 20, "rainfall": 17.7, "risk": "medium" },
  { "year": 2025, "week": 52, "district": "District VI", "cases": 13, "rainfall": 17.7, "risk": "low" },
  { "year": 2025, "week": 51, "district": "District I", "cases": 12, "rainfall": 8.1, "risk": "low" },
  { "year": 2025, "week": 51, "district": "District II", "cases": 10, "rainfall": 8.1, "risk": "low" },
  { "year": 2025, "week": 51, "district": "District III", "cases": 15, "rainfall": 8.1, "risk": "low" },
  { "year": 2025, "week": 51, "district": "District IV", "cases": 35, "rainfall": 8.1, "risk": "medium" },
  { "year": 2025, "week": 51, "district": "District V", "cases": 28, "rainfall": 8.1, "risk": "medium" },
  { "year": 2025, "week": 51, "district": "District VI", "cases": 16, "rainfall": 8.1, "risk": "low" },
  { "year": 2024, "week": 34, "district": "District I", "cases": 6, "rainfall": 12.5, "risk": "low" },
  { "year": 2024, "week": 34, "district": "District II", "cases": 4, "rainfall": 15.0, "risk": "low" },
  { "year": 2024, "week": 34, "district": "District III", "cases": 9, "rainfall": 10.2, "risk": "low" },
  { "year": 2024, "week": 34, "district": "District IV", "cases": 30, "rainfall": 25.5, "risk": "medium" },
  { "year": 2024, "week": 34, "district": "District V", "cases": 77, "rainfall": 45.0, "risk": "high" },
  { "year": 2024, "week": 34, "district": "District VI", "cases": 22, "rainfall": 18.3, "risk": "medium" }
];

window.SAMPLE_DISTRICTS_DETAIL = {
  "I": { ...cpddDistrictContext("I"), status: "Stable", risk: "low", recent_cases: 8, avg_rainfall: "17.7mm" },
  "II": { ...cpddDistrictContext("II"), status: "Decreasing", risk: "low", recent_cases: 6, avg_rainfall: "17.7mm" },
  "III": { ...cpddDistrictContext("III"), status: "Stable", risk: "low", recent_cases: 10, avg_rainfall: "17.7mm" },
  "IV": { ...cpddDistrictContext("IV"), status: "Monitoring", risk: "medium", recent_cases: 25, avg_rainfall: "17.7mm" },
  "V": { ...cpddDistrictContext("V"), status: "Warning", risk: "medium", recent_cases: 20, avg_rainfall: "17.7mm" },
  "VI": { ...cpddDistrictContext("VI"), status: "Stable", risk: "low", recent_cases: 13, avg_rainfall: "17.7mm" }
};