# Implementation Plan - District Detail Revamp

Revamp the "District Detail" view to match the premium, structured design provided. This update will organize district-specific epidemiological, demographic, and environmental data into clear, actionable sections.

## Proposed Changes

### [Component Name] Frontend UI

#### [MODIFY] [index.html](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/index.html)
- Completely replace the `#district-detail-card` content.
- Add **Breadcrumbs** (e.g., District Overview / District V).
- Add **Dengue Situation Banner**: Highlighting recent cases, current status, and risk level in a prominent, colored container (red for high risk).
- Add **District Profile Section**: A row of key demographic indicators (Population, Land Area, Density, Barangay count) with icons.
- Add **Barangay Accordion**: An expandable section showing the list of barangays in the district.
- Add **Environmental Risk Grid**: Two side-by-side boxes for "Flood Vulnerability" and "Waste Pressure" with detailed metrics like Tier counts and waste density.
- Add **Action Button**: A refined full-width button to jump to the Facilities Map.

#### [MODIFY] [app.js](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/js/app.js)
- Update `window.showDistrictDetail` to populate the new layout.
- Map `cases`, `status`, and `risk` to the situation banner.
- Calculate and display CDRA Tier breakdowns (Tier 1, 2, 3) in the Flood section.
- Calculate and display WACS equivalents (kg/day) in the Waste section.
- Handle the barangay list rendering for the new accordion.

#### [MODIFY] [style.css](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/css/style.css)
- Add styles for the detail view:
    - `.detail-card`: Wider, cleaner background, and refined shadow.
    - `.situation-banner`: Prominent colored bar (red/yellow/green depending on risk).
    - `.profile-row`: Flexbox container for demographic tiles with icons.
    - `.risk-grid`: Two-column layout for Flood and Waste sections.
    - `.comparison-box`: Styling for the environmental risk containers.
    - `.tier-badge`: Small pill-style indicators for flood hotspots.
- Ensure responsiveness for smaller screens by stacking the grids.

## Verification Plan

### Automated Tests
- N/A (UI-only change)

### Manual Verification
- Navigate to the "District Overview" tab.
- Click on a district card (e.g., District V).
- Verify the following in the detail view:
    - The breadcrumb correctly reflects the selected district.
    - The "Dengue Situation" banner shows the correct case count and risk level.
    - The population and area data match the CPDD/PSA datasets.
    - The "Flood Vulnerability" section correctly displays the hotspot count and Tier breakdown.
    - The "Waste Pressure" section shows tons/day and the top-generating barangay.
    - Clicking "View Health & School Facilities Map" navigates to the facilities page.
