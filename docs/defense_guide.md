# Defense guide: evidence available on 25 September 2026

**May reproducible city forecasting experiment at validated CPDD reference tables na tayo. Hindi pa nito nava-validate ang original district-level spatio-temporal study o isang integrated BN–LSTM hybrid.** Ito ang claim na kayang suportahan ng kasalukuyang files, code, at evaluation.

Walang UI redesign sa model/data work na ito. Para sa defense, gamitin ang saved evaluation at canonical JSON bilang evidence; may existing sample/offline frontend content na hindi kasabay na na-update.

## Saklaw na kailangang malinaw

| Item | Current evidence |
|---|---|
| Original research contract | Six QC districts, epidemiological weeks, **2018–2024**; draft pa ang risk taxonomy at official threshold formulas. |
| Completed supplementary experiment | QC **city total**, source periods **2010–2025**, retrospective one-period-ahead case-count forecasting. |
| CPDD integration | Dated barangay reference table covering 142 barangays; geographic, census, household, flood, and estimated waste context. |
| Current Bayesian Network | Requires observed weekly barangay counts; unavailable without those inputs. Its defined task is contemporaneous inference, not an advance forecast. |
| Still unestablished | District forecast accuracy, calibrated outbreak probabilities, environmental causal effects, prospective operational performance, and hybrid-model improvement. |

The city experiment is supplementary feasibility evidence. Hindi nito awtomatikong binabago ang approved thesis scope. Keep the original [research contract](../data/contracts/research_data_contract.json) visible when explaining the remaining district work. Kung district-only weekly data ang makuha, valid iyon para sa original scope, pero kailangan ng district-specific pipeline; huwag itong ipasa bilang fabricated barangay rows.

## Actual result na ipapakita

Source: [model card](../output/model-evaluation/model_card.json), [predictions](../output/model-evaluation/holdout_predictions.csv), and [evaluation implementation](../backend/models/lstm_model.py). The predictions CSV includes train, validation, and test rows; filter `split=test` for final test charts.

Ready-to-show evidence: [evaluation report](model_evaluation.md) and [comparison chart](figures/city_holdout_evaluation.png). The report/chart are in `docs/` so they can be versioned even though `output/` is ignored.

| Split | Target periods | Number of targets | Purpose |
|---|---|---:|---|
| Train | 2010-W21 to 2021-W52 | 604 | Fit weights and scaling parameters. |
| Validation | 2022-W01 to 2023-W52 | 104 | Select LSTM epoch and final forecasting method by MAE. |
| Test | 2024-W01 to 2025-W52 | 104 | Final held-out comparison; no training or selection. |

The workbook has 832 source rows. Eight rows supply lag warmup and twelve more supply the first input sequence, leaving 812 forecast targets. No missing observations were imputed or dropped as invalid rows.

| Method | Validation MAE | Test MAE | Test RMSE |
|---|---:|---:|---:|
| LSTM | **11.79** | 35.00 | 58.12 |
| Last observed case count | 13.28 | **33.60** | **50.79** |
| Same source week, previous year | 43.17 | 109.83 | 152.89 |

All errors are **numbers of cases**, not percentages. MAE is the average absolute difference between forecast and actual count; RMSE gives larger errors more weight. “MAE 35” is not “65% accuracy” and does not mean every prediction is within 35 cases.

**Conclusion:** LSTM was selected on validation, but the simple last-observation baseline performed better on the final test set. Do not claim that LSTM outperformed all baselines. Do not choose new epochs, seeds, or features using this test result and then present the same period as an untouched test again.

## Paano ginawa ang experiment

- The supplied workbook's `QC Data` sheet provides `YR`, `WN`, `DC_QC`, and `RF_NASA`. Its dictionary attributes cases to QCESD and rainfall to NASA satellite data. Those agency attributions have **not been independently verified**; NASA rainfall must not be called PAGASA observations.
- The source explicitly uses periods 1–52 each year. ISO/MMWR week boundaries and treatment of week 53 are unverified. Labels such as `2025-W52` preserve the source convention; they are not verified calendar dates.
- Each prediction uses twelve preceding rows of case and rainfall information, including four- and eight-period lags. The target-period row is not an input. Scaling is fitted only on training inputs and targets.
- The LSTM has two layers, 64 hidden units, dropout 0.2, batch size 16, and learning rate 0.001. This run used CPU, one thread, and seed 42; best epoch was 21, with early stopping after 36 of at most 80 epochs.
- Holdouts use rolling observed history: the real observation from a completed test period can inform the next prediction. Model weights and scalers stay fixed. This is not a 104-period forecast made entirely at the start of 2024.
- The saved artifact is fitted through the 2021 targets; it was not refitted on all history. Source hash and artifact schema are checked before loading.
- The latest available observation is `2025-W52`. A future forecast starts at source period `2026-W01`, **not tomorrow or the current week**. Later recursive horizons and the assumption of unchanged future rainfall have not been evaluated. No calibrated prediction intervals are available.

## Ano ang naidagdag ng CPDD

The [folder audit](../output/cpdd-audit/report.md) inventoried 558 file locations and 333 distinct contents, including 225 identical extra copies. It inspected workbooks, extracted available PDF text, and reviewed images/maps. Some scans lack searchable text; the audit is not a certification of every sentence or map feature. Its descriptions of old synthetic model paths are a **pre-fix snapshot**; use the current code and this guide for implementation status.

| Integrated reference | Verified use and limitation |
|---|---|
| PSA 2020 population/households | 142 QC barangays from visible `by Bgy_1!A1016:D1157`; 2,960,048 total population, 2,950,493 household population, 738,724 households. Hidden duplicate sheet excluded. |
| Geography and density | Canonical six-district membership and explicit barangay area basis. Density is population / hectares × 100, in people/km²; household size uses household population / households. |
| CDRA flood susceptibility | 119 listed MGB records; 23 unlisted barangays remain **null**, not measured zero. The 21 BVI hotspots are vulnerability references, not dengue probabilities. |
| WACS 2021 | Estimated waste from projected population × 0.44 kg/person/day; not measured uncollected waste or sanitation quality. |
| Combined context table | 142 matched rows, dated fields, missingness flags, and source hashes; **not a weekly training dataset**. |

See [household reference](../data/authoritative/cpdd/barangay_households_2020.json) and [combined context table](../data/authoritative/cpdd/barangay_context_features.json). **These CPDD variables are not fitted predictors of the current city LSTM.** Reference integration, statistical association, predictive benefit, and causation are different claims.

Do not mix the old four-district area workbook with current six-district labels. Reservoir allocation differs across district aggregate sources, so district density requires reconciliation. Population projections remain projections; 2026 facility maps cannot automatically describe conditions in 2018–2024. Any historical use of later static references needs an explicit availability assumption and suitable evaluation.

## Bakit blocked ang barangay risk output

Annual barangay totals cannot reveal actual weekly timing. The previous annual-to-week allocation is no longer accepted as observed labels. Current intake requires complete, continuous observations for all 142 canonical barangays, nonnegative integer counts, source labels, correct districts, and a provider-declared ISO-8601 or MMWR calendar.

The expected path is `data/processed/weekly_dengue_cases.csv`, configurable with `DENGUE_WEEKLY_CASES_PATH`. The [CSV template](../data/templates/weekly_dengue_cases_template.csv) documents the columns. Optional rainfall must be aligned to the same declared reporting weeks and have its own source. An absent observation cannot be replaced with a zero without source confirmation.

Without valid observed data, `/predict` returns an actionable unavailable/error response instead of invented probabilities. Unsupported environmental switches are rejected; fixed probability increments have been removed. Reference endpoints and the independent city experiment remain available.

Even after loading valid data, the current BN uses current-week city evidence that includes the target barangay. It therefore describes **contemporaneous case burden**. Its Low/Medium/High thresholds come from training-data percentiles, not verified DOH alert/epidemic formulas. Separate temporal validation and task redesign are needed before claiming advance district or barangay warning.

## One-minute opening script

> Ang study namin ay nakatuon sa dengue risk sa Quezon City. Sa kasalukuyang implementation, nakapag-validate kami ng CPDD reference data para sa 142 barangays at nakagawa ng reproducible city-level forecasting experiment. Hiwalay ang train, validation, at test years, at ikinumpara namin ang LSTM sa simpleng baselines. Sa 2024–2025 test set, ang LSTM MAE ay 35 cases, habang 33.60 ang last-observation baseline. Kaya hindi namin kini-claim na mas mahusay ang LSTM sa lahat ng kondisyon. Ang original district-level objective ay nangangailangan pa ng observed weekly district data at verified risk thresholds. Hindi namin ginawang weekly observations ang annual barangay totals, at hindi namin tinatrato ang flood o waste references bilang learned dengue probabilities. Ang contribution ngayon ay malinaw na data provenance, reproducible evaluation, at honest boundaries ng model.

## Likely panel questions

**“Model na ba talaga ito?”** May fitted, saved, retrospectively evaluated city LSTM. May reference-data integration din. Hindi pa complete validation ng original district-level system o proof ng operational readiness.

**“Bakit mas maganda ang baseline?”** Iyan ang observed test result; hindi pa established ang dahilan. Complex models do not guarantee lower error. Investigate where errors cluster, compare prespecified alternatives on validation, and reserve new unseen periods for confirmation. Do not invent a causal explanation from the metric alone.

**“Bakit LSTM pa rin ang selected?”** Validation MAE selected it before the final test comparison. Changing the winner after seeing test performance would change the selection protocol. Report both the selection and the final test result transparently.

**“Nasaan ang accuracy percentage?”** This task predicts counts, so we report MAE and RMSE in cases. Classification accuracy or outbreak sensitivity would require a defined classification task, verified thresholds, and an appropriate held-out evaluation.

**“Ginamit ba ang lahat ng CPDD files sa training?”** Hindi. Relevant census and context fields were validated and linked. The city LSTM uses past case and rainfall information. Adding more documents does not establish predictive value; later spatial work needs aligned observations and feature comparisons.

**“Mas mataas ba ang flood/waste, mas mataas agad ang dengue risk?”** Hindi natin maikiklaim iyon mula sa current model. Susceptibility and estimated waste are candidate contextual variables. No learned effect size, causal effect, or validated probability adjustment is established.

**“Hybrid BN–LSTM na ba ang result?”** These are separate components with different tasks. No jointly validated hybrid improvement is established. A hybrid claim would require a specified connection between components and comparison against each component and baselines on the same held-out target.

**“Forecast ba ito para bukas?”** Hindi. The dataset ends at source period 2025-W52; generated forecasts follow that origin. Updated observed data and confirmed week dates are required for a current-date forecast.

**“Excel lang o pati PDF?”** Prefer original Excel/CSV for structured observations and retain PDF/data dictionaries for definitions, units, methodology, and source evidence. PDF alone can be extracted and checked, but it cannot supply weekly detail absent from its tables.

## Reproduce and rehearse

Verified in this workspace: **84 automated Python tests passed** and **6 live API acceptance checks passed**. The live backend was started in research mode on a separate port: missing BN observations did not crash startup; reference/evaluation endpoints remained available; unsupported barangay LSTM requests and unlearned environmental scenarios were rejected. These are software checks, separate from the forecast accuracy reported above.

Run from the repository root in PowerShell, using the existing environment and original source files. Preserve the original dataset and configuration; training below regenerates the saved city artifact and reports.

```powershell
& ./venv/Scripts/python.exe -m pip install -r requirements.txt
& ./venv/Scripts/python.exe scripts/import_psa_households.py
& ./venv/Scripts/python.exe scripts/import_cdra_flood_data.py --backend-only
& ./venv/Scripts/python.exe scripts/prepare_context_features.py
& ./venv/Scripts/python.exe scripts/evaluate_city_forecast.py --epochs 80 --hidden-size 64 --seed 42
& ./venv/Scripts/python.exe scripts/build_defense_report.py
& ./venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v
```

The exact recorded library versions and source SHA-256 are in the model card. Matching configuration and environment makes reproduction assessable; results across different library/platform versions should be rechecked. Keep `model_card.json` and `holdout_predictions.csv` together when transferring the defense evidence; `output/` is ignored by Git.

Start the backend in a separate terminal on a free port:

```powershell
$env:PORT = '5051'
$env:DENGUESENSE_PROTOTYPE_ONLY = '0'
$env:SKIP_TRAINING = '0'
& ./venv/Scripts/python.exe backend/app.py
```

Then inspect the saved evidence without retraining:

```powershell
Invoke-RestMethod 'http://127.0.0.1:5051/model/health' | ConvertTo-Json -Depth 8
Invoke-RestMethod 'http://127.0.0.1:5051/lstm/evaluation' | ConvertTo-Json -Depth 12
Invoke-RestMethod 'http://127.0.0.1:5051/reference/cpdd/households' | ConvertTo-Json -Depth 6
Invoke-RestMethod 'http://127.0.0.1:5051/lstm/forecast?area=city&weeks=1' | ConvertTo-Json -Depth 12
$env:BASE_URL = 'http://127.0.0.1:5051'
& ./venv/Scripts/python.exe tests/final_acceptance.py
```

Rehearse in this order: original research objective and scope gap; source files and reference checks; chronological split and baselines; final test table; unavailable barangay inference; concrete data request. Presenting a working API is implementation evidence, not evidence of forecast accuracy. Do not describe frontend sample charts or unchanged offline flood assets as the newly evaluated model output.

## Data needed to finish the original objective

1. Request observed **weekly district counts for 2018–2024**, preferably with underlying barangay counts, from QCESD. Ask for the case definition, onset versus reporting date, revision policy, coverage, zeros versus missing records, district boundary version, and exact week calendar including week 53.
2. Obtain dated weather observations and metadata: agency/product, station or spatial coverage, units, aggregation method, missingness, and publication timing. If the contract requires PAGASA, obtain PAGASA data or explicitly justify and approve a documented alternative.
3. Verify the intended risk taxonomy and official threshold formulas. Define whether the final target is next-week counts, a future risk category, or contemporaneous inference before comparing models.
4. Align all inputs to the chosen district/week target and forecast horizon. Test temporal leakage, evaluate against simple baselines, assess added CPDD features, and evaluate any proposed hybrid on the same held-out periods.
5. Use later unseen observations for prospective checks after any changes informed by the current final test. Performance and intervals need evidence before operational use can be claimed.

Keep the conclusion factual: the current work improves the reliability and reproducibility of the research, while the district-level objective remains dependent on the missing observed data and an agreed evaluation specification.
