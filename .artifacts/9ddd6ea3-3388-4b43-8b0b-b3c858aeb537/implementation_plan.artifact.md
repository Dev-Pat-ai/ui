# Phase 6H — Historical Records UI Enhancement

This plan upgrades the "Historical Records" page to match the premium "iPhone-like" aesthetic, focusing on a card-based filter system and a refined, high-fidelity data table.

## User Review Required

> [!IMPORTANT]
> **Filter Card**: The filter controls (District and Year) will be housed within a soft-shadowed white card, similar to the dashboard panels, rather than floating on the canvas.

## Proposed Changes

### 1. Structure Refinement

#### [MODIFY] [index.html](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/index.html)
- Wrap the filter elements in a `.card` container.
- Standardize filter labels using the `.field-group` structure used in the Forecast section.

### 2. Styling Enhancements

#### [MODIFY] [style.css](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/css/style.css)
- **Table Styling**:
    - Apply refined typography to `.hist-table` headers (smaller, uppercase, tracked-out).
    - Increase row padding for better legibility.
    - Add a subtle hover effect to table rows.
- **Filter Bar**:
    - Style the filter card to be compact and centered or left-aligned with proper spacing.
    - Ensure `select` elements match the iOS-style used on other pages.

### 3. Logic Sync

#### [MODIFY] [app.js](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/js/app.js)
- Update `renderHistoricalTable` to ensure the generated table classes align with the new design system.

## Verification Plan

### Manual Verification
1. Navigate to the **Historical** page.
2. Verify that the filters are contained within a clean white card with rounded corners.
3. Check the table for improved typography and spacing.
4. Verify that filtering still works correctly after the structural changes.
