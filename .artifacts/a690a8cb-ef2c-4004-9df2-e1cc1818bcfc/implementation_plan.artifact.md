# Implementation Plan - Update Historical and Sample Data to 2025

The historical research data currently displayed in the UI is from 2024, while the underlying raw dataset includes records up to **2025 Week 52**. This plan updates the sample data used by the prototype to reflect these latest records.

## User Review Required

> [!IMPORTANT]
> I will be updating the "Current" dashboard view and "Historical" trends to use data from **2025 Week 52** (the latest in the source file).
> The demo labels will be updated from "(2023-2024)" to **"(2023-2025)"**.

## Proposed Changes

### Data Layer

#### [MODIFY] [sample-data.js](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/js/sample-data.js)
- Update `window.SAMPLE_HISTORICAL_DATA` to include 2025 Week 51 and Week 52.
- Update `window.SAMPLE_DISTRICT_SUMMARY` to use cases from 2025 Week 52.
- Adjust `window.SAMPLE_FORECASTS` to be relative to the new 2025 "current" state.
- Update `OFFLINE_METADATA.sample_updated_at` to a more recent date if necessary (optional, but keep consistent).

### Frontend Labels

#### [MODIFY] [index.html](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/index.html)
- Update the historical data badge to read: **"Historical Research Data (2023-2025)"**.

## Verification Plan

### Manual Verification
- **Visual Check**: Navigate to the **Historical** page and confirm that 2025 records are now visible at the top.
- **Visual Check**: Verify that the **Dashboard** KPIs (Cases, Trends) reflect the new 2025 totals.
- **Visual Check**: Confirm the header badge now shows the updated 2023-2025 range.
