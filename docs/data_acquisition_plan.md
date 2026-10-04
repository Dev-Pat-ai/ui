# Data Acquisition Plan

This document outlines the authoritative datasets required for the final research modeling phase of the Dengue Risk Prediction project.

## 1. Authoritative Datasets Required

### 1.1 Weekly Dengue Cases (Core)
- **Required Fields**: `epi_year`, `epi_week`, `district_id`, `barangay_name` (optional), `dengue_cases`.
- **Expected Source**: Quezon City Epidemiology and Surveillance Division (QCESD).
- **Geographic Resolution**: District level (I-VI). Barangay level is preferred if available.
- **Temporal Resolution**: Epidemiological Week.
- **Study Period**: 2018–2024.
- **Status**: **BLOCKER**. Currently only city-level weekly or annual barangay-level data is available. Annual data cannot be disaggregated into weekly data without authoritative week weights.

### 1.2 Barangay-to-District Mapping
- **Required Fields**: `barangay_name`, `district_id`.
- **Source Received**: Quezon City Planning and Development Department (CPDD) district map tables.
- **Geographic Resolution**: Barangay to District link.
- **Reference Year**: 2020.
- **Status**: **AVAILABLE AND VALIDATED**. The six maps cover 142 unique barangays and provide district membership, land area, PSA 2020 population, and population density. This resolves the geographic mapping input, but does not resolve the weekly dengue target-data blocker.

### 1.3 Authoritative Meteorological Data (Core)
- **Required Fields**: `rainfall_mm`, `min_temp`, `max_temp`, `humidity`.
- **Expected Source**: PAGASA (Philippine Atmospheric, Geophysical and Astronomical Services Administration).
- **Geographic Resolution**: Station level (to be mapped to Districts).
- **Temporal Resolution**: Weekly / Daily.
- **Status**: **BLOCKER**. Current rainfall data is from NASA (Satellite), which must not be relabeled as PAGASA data.

### 1.4 Environmental, Socioeconomic, and Infrastructure Features
- **Expected Sources**: DENR, PSA, QC SSDD, Satellite imagery.
- **Geographic Resolution**: District/Barangay level.
- **Status**: **PENDING**. Candidate features to be acquired once core epidemiological and meteorological data are secured.

## 2. Acquisition Actions

- **Official Request**: Submit a formal data request to QCESD for weekly district-level dengue counts (2018-2024).
- **PAGASA Coordination**: Acquire official weather station data for Quezon City (Science Garden station or similar).
- **Mapping Verification**: Completed from the six CPDD District Maps (2020); retain source PDFs and checksums for traceability.

## 3. Critical Technical Notes

- **No disaggregation**: City-level weekly data cannot be disaggregated into districts without introducing artificial bias.
- **No synthetic weeks**: Annual barangay data cannot be converted into weekly data without the actual case-per-week distribution.
- **Source Integrity**: Data from different sources (e.g., NASA vs PAGASA) must be clearly distinguished due to potential variance in measurement methods and accuracy.
