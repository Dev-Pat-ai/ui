# DengueSense QC Research Prototype

DengueSense QC combines a static HTML/CSS/JavaScript frontend with a Flask backend for dengue forecasting and risk-classification research.

## CPDD/PSA 2020, CDRA 2022, and WACS 2021 integration

The project includes three validated authoritative reference datasets:

1. **Quezon City CPDD District Maps (2020)** (`data/authoritative/cpdd/district_profiles_2020.json`):
   - 6 districts, 142 unique barangays
   - Barangay-to-district membership, land area, PSA 2020 population, and population density.

2. **Quezon City CDRA Report (2022)** (`data/authoritative/cdra/qc_flood_vulnerability_2022.json`):
   - MGB Flood Susceptibility tables across Districts I to VI (depths 0.5-1m, 1-2m, >2m, and total flooded area %).
   - 3-Tier Barangay Vulnerability Index (BVI) ranking for 21 flood hotspot barangays.
   - Provides static spatial environmental vector-breeding hazard baselines.

3. **Quezon City WACS Solid Waste Study (2021)** (`data/authoritative/wacs/qc_waste_generation_2021.json`):
   - TFSWM/EPWMD solid waste generation across all 142 barangays (1,304.35 tons/day citywide).
   - Waste generation density (kg/ha/day) serving as an environmental proxy for artificial container breeding risk under the DOH 4S Strategy.

The District Overview on the dashboard integrates CPDD demographics, CDRA flood vulnerability, and WACS waste generation metrics.

## Important data boundary

The CPDD maps, CDRA reports, and WACS datasets do **not** contain weekly dengue surveillance counts or operational weather station feeds. Those fields remain clearly marked as demonstration or experimental values. They must not be used for operational public-health decisions.

The remaining core blockers are:

- True weekly district- or barangay-level dengue case counts for the study period (QCESD)
- Authoritative weekly weather observations and a documented station-to-district method (PAGASA)
- Confirmed risk taxonomy and threshold formulas

## API endpoints

Prototype and model endpoints:

- `GET /prototype/dashboard`
- `GET /api/prototype/data-readiness` (source-level provenance, coverage, limitations, and operational-readiness blockers)
- `GET /prototype/forecast` (all demonstration forecasts)
- `GET /prototype/forecast?district=I` (one selected district)
- `GET /prototype/historical`
- `GET /prototype/districts`
- `GET /prototype/districts/<id>`
- `POST /predict`
- `POST /lstm/forecast`

Authoritative reference endpoints:

- `GET /reference/cpdd/districts`
- `GET /reference/cpdd/districts/<id>`
- `GET /reference/cpdd/barangays`
- `GET /reference/cpdd/barangays?district=II`
- `GET /reference/cdra/flood-vulnerability`
- `GET /reference/cdra/flood-vulnerability/<district_id>`
- `GET /reference/cdra/hotspots`
- `GET /reference/wacs/waste-generation`
- `GET /reference/wacs/waste-generation/<district_id>`
- `GET /reference/wacs/top-generators`

Reference responses use `is_authoritative_reference: true` and `is_sample: false`. Mixed prototype responses contain a `data_provenance` object that separates authoritative demographic fields from demonstration health fields.

The data-readiness response is intentionally not a model-health indicator. It distinguishes validated static reference data from the weekly district-level dengue and PAGASA weather inputs still required for operational forecasting.

## Run locally

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the frontend and Flask API together (requires Node.js 20 or later):

```powershell
npm run dev
```

Open `http://localhost:5000`. The development command uses your active Python virtual environment, then a local `.venv/` or `venv/`, then Python on your PATH. It serves the editable `frontend/` files and defaults to prototype-only mode, skipping model training at startup. No frontend build or npm dependency installation is needed. Refresh the browser after frontend edits; restart the command after Python edits. Press `Ctrl+C` to stop.

To train the research model at startup, set `$env:DENGUESENSE_PROTOTYPE_ONLY="0"` before running `npm run dev`. The `PORT` environment variable overrides the default port of 5000.

You can also start Flask directly in prototype-only mode:

```powershell
$env:DENGUESENSE_PROTOTYPE_ONLY="1"
python backend/app.py
```

Open `http://localhost:5000`.

## Share a public localhost demo

Start the app and a temporary Cloudflare public link together:

```powershell
npm run share
```

Copy the `https://...trycloudflare.com` link printed in the terminal. Visitors
can sign in with **demo@example.com** / **demo123**; these credentials are also
shown in the sign-in panel. The latest link is saved in
`output/public-share/url.txt`.

Keep this computer awake and connected to the internet while sharing. The link
works while the app and tunnel are running, and a new sharing session gets a
new URL. Press `Ctrl+C` in the sharing terminal, or stop a background session
from another terminal:

```powershell
npm run share:stop
```

This command serves the editable frontend with a separate, disposable SQLite
database. Existing accounts, saved forecast history, account changes, and model
training are unavailable in the public demo. Profile edits stay in each
visitor's browser. The normal `npm run dev` database configuration is unaffected.
Existing research-data limitations and model-readiness messages still apply.

The launcher uses the repository's `cloudflared.exe`, or `cloudflared` on your
PATH, and the same Python selection as `npm run dev`. The public demo defaults
to port 5001 so your normal development server can keep using port 5000. If the
demo port is occupied, choose another with `$env:PORT="5002"`.
See [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
for service limitations.

The public demo serves a `robots.txt` allowing `ChatGPT-User` and
`OAI-SearchBot`, while opting out of `GPTBot` training crawls. Cloudflare can
prepend its own [managed crawler rules](https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/),
and ChatGPT's web reader may still be unable to fetch a temporary tunnel link.
An HTTP 200 check does not verify ChatGPT access. For an interactive dashboard
review, use [ChatGPT browser mode](https://learn.chatgpt.com/docs/browser) and
the demo login; the dashboard also requires JavaScript and browser interaction.

## Build the frontend

The frontend is static HTML, CSS, JavaScript, and assets. Node.js 20 or later is required; no npm dependencies need to be installed.

```powershell
npm run build
```

This validates the browser JavaScript and copies the deployable frontend to `dist/`. To have Flask serve that build instead of the editable `frontend/` source directory, set the build flag before starting the server:

```powershell
$env:DENGUESENSE_SERVE_BUILD="1"
$env:DENGUESENSE_PROTOTYPE_ONLY="1"
python backend/app.py
```

Use `npm run clean` to remove the generated `dist/` directory.

## Rebuild the CPDD reference files

Keep the six PDFs in one folder, install Poppler so `pdftotext` is available, then run:

```powershell
python scripts/import_cpdd_district_maps.py --pdf-dir "C:\path\to\district-maps"
```

The importer validates district row counts, unique barangays, district population sums, land-area totals, and the city population total before replacing the generated JSON and offline JavaScript files.

## Test

```powershell
python -m unittest discover -s tests -p "test_*.py"
npm run test:frontend
python tests/final_acceptance.py
```

The frontend suite tests forecast state and history. Browser layout checks are explicitly skipped unless `FRONTEND_TEST_URL` points to a running development server. They require Node.js 22 or later and Chrome/Chromium, and exercise seven viewport widths from 320px to 1440px.

With `npm run dev` running in another terminal:

```powershell
$env:FRONTEND_TEST_URL="http://localhost:5000"
npm run test:frontend
```

Use `npm run test:frontend:browser` to run only browser checks. This command also accepts `BASE_URL` and defaults to `http://127.0.0.1:5000` when neither URL variable is set. Set `CHROME_PATH` if Chrome/Chromium is installed outside the usual Windows, macOS, or Linux locations. Screenshots, layout measurements, and an isolated browser profile are saved under the ignored `output/frontend-layout/` directory.
