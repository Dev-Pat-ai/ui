# Research Decision Register

This register tracks critical research parameters that require formal confirmation before final modeling.

## Resolved Reference Input

### Barangay-to-District Mapping and 2020 Demographics
- **Status**: `AVAILABLE_VALIDATED`
- **Source**: Six Quezon City CPDD District Maps (2020), with population columns identified as PSA 2020.
- **Coverage**: 6 districts and 142 unique barangays.
- **Included Fields**: District membership, land area, actual population 2020, and population density.
- **Limit**: The maps contain no weekly dengue cases or weather observations, so they cannot by themselves produce district forecasts or operational risk labels.

## 1. Unresolved Decisions

### 1.1 Risk Taxonomy
- **Current Status**: `REQUIRES_CONFIRMATION`
- **Candidates**:
    - `Low / Moderate / High`
    - `Below / Alert / Epidemic`
- **Action**: Researcher to confirm which taxonomy aligns with the final thesis objectives.

### 1.2 Risk Classification Thresholds
- **Current Status**: `REQUIRES_CONFIRMATION`
- **Issue**: The exact numeric formulas or percentile cut-offs for the chosen taxonomy labels (e.g., what constitutes an "Epidemic" week) are not yet finalized.
- **Action**: Define official QCESD threshold formulas or research-specific cut-offs.

### 1.3 Weather Station to District Assignment
- **Current Status**: `REQUIRES_CONFIRMATION`
- **Issue**: How to assign observations from a limited number of weather stations to 6 specific districts.
- **Candidates**:
    - Nearest neighbor (Assignment to the closest station).
    - Spatial interpolation (Inverse Distance Weighting, Kriging).
    - Unified city-wide weather (assuming homogeneous conditions across QC).
- **Action**: Define and justify the mapping methodology.

### 1.4 Treatment of Missing Epidemiological Weeks
- **Current Status**: `REQUIRES_CONFIRMATION`
- **Issue**: Strategy for handling weeks with missing case reports.
- **Candidates**:
    - Zero-imputation (assuming no cases were reported).
    - Linear interpolation.
    - Exclusion of the week/district.
- **Action**: Select a method that minimizes bias in the LSTM and Bayesian models.

### 1.5 Inclusion of Candidate Non-Core Features
- **Current Status**: `RESOLVED_FOR_FLOOD_AND_WASTE`
- **Resolution**:
    - **Environmental Flood Susceptibility & BVI Hotspots**: Extracted and validated from Quezon City's authoritative *Climate and Disaster Risk Assessment (CDRA) Report 2022* (Tables 14-19 MGB flood susceptibility and Table 71 3-tier Barangay Vulnerability Index).
    - **Solid Waste Generation & Sanitation Risk (WACS 2021)**: Extracted and validated from Quezon City Task Force on Solid Waste Management (TFSWM) & EPWMD *Waste Generated per Barangay 2021*. Covers daily waste in kg/day, tons/day, and waste generation density (kg/ha/day) across all 142 barangays.
    - **Epidemiological Rationale**: 
        - CDRA Page 55 explicitly documents that extreme temperature and rainfall frequency increase mosquito breeding and dengue transmission. Flood pooling and drainage overflow create stagnant water reservoirs, functioning as a spatial hazard amplifier interacting with lagged rainfall.
        - WACS waste density (kg/ha/day) serves as a quantitative proxy for artificial container accumulation (discarded plastics, tin cans, uncollected household refuse) which constitute the primary breeding sites of *Aedes aegypti* targeted by the DOH 4S "Search and Destroy" strategy.
    - **Remaining Non-Core Candidates**: Satellite NDVI and LST remain optional candidates pending remote-sensing pipeline confirmation.

