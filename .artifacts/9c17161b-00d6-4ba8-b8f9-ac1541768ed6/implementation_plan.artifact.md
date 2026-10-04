# Simulated Future Data Integration Plan

The goal is to show the panel that the system is ready for multi-factor data integration by simulating how Ecological, Waste, and Disaster data would affect risk levels.

## User Review Required

> [!NOTE]
> Since we don't have the raw data files for these yet, we will **simulate** their impact on the Risk Inference model. This demonstrates "future-proofing" without needing to re-train the core model today.

## Proposed Changes

### [Frontend - Interactive Simulations]

#### [MODIFY] [index.html](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/index.html)
- Add a new section in the **Risk Inference** sidebar called "Environmental Simulation (Roadmap Features)".
- Add inputs for:
    - **Water Proximity**: (Nearby water bodies / None)
    - **Waste Management**: (Standard / Efficient / Poor)
    - **Flood History**: (Recent flooding / No recent flooding)

#### [MODIFY] [style.css](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/css/style.css)
- Add a `.simulation-tag` class for the dashboard cards to show environmental risk factors (e.g., "Flood Prone").
- Add styling for the new simulation inputs to highlight them as "Roadmap" features.

#### [MODIFY] [app.js](file:///C:/Users/charm/Documents/GitHub/dengue-project/frontend/js/app.js)
- Update `collectEvidence` to send these extra parameters to the backend.
- Add simulated tags to the **District Risk Overview** cards (e.g., tagging District II as "Flood Zone").

### [Backend - Multi-Factor Logic]

#### [MODIFY] [bn_model.py](file:///C:/Users/charm/Documents/GitHub/dengue-project/backend/models/bn_model.py)
- Update `what_if` to accept these simulated parameters.
- Implement logic to adjust the `probs` dictionary based on these factors:
    - **Poor Waste Management** -> Increase "High" risk probability by +15%.
    - **Nearby Water Bodies** -> Increase "Medium/High" risk probability by +10%.
    - **Recent Flooding** -> Increase "High" risk probability by +20%.

## Verification Plan

### Manual Verification
- **Dashboard**: Check if District cards now have small text indicators for environmental factors.
- **Inference**: Select "Poor Waste Management" and run inference. Verify that the "Model Confidence" or "Risk Level" escalates compared to the standard model.
- **UI**: Ensure the new fields are clearly marked as part of the "Future Integration Roadmap".
