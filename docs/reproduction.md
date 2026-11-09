# Reproducing the corrected project

The normal build uses the retained source snapshots and requires **no data download**. Installing Python dependencies and deliberately refreshing market data are separate operations that can require network access. Run commands from the repository root.

## 1. Create the pinned environment

Python 3.12 is the tested runtime; the package declares Python 3.11–3.13 support, but that declaration is not a claim that every supported version has been exercised. A virtual environment keeps project dependencies separate from your other work.

Linux/macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

The lock file pins core, test and transitive dependencies. It excludes optional PySpark. The shorter `requirements.txt` lists the directly used analysis packages; use the lock file when reproducing the reviewed environment. The examples below use `.venv/bin/python`; substitute `.\.venv\Scripts\python.exe` on Windows.

No editable installation is needed for `python -m rbi_intelligence` when run from this directory. If dependency installation must also be offline, populate a compatible wheel cache in advance; the repository does not bundle Python or package wheels.

## 2. Validate the frozen data

```bash
.venv/bin/python -m rbi_intelligence validate-data
```

This reads the official-source event table and the retained Yahoo/NSE files, verifies source hashes, applies the documented source-backed repair, checks the selected NSE price comparisons and rebuilds `data/processed/market_panel.csv`. It does not contact the data providers. Normalized source tables and data diagnostics are also regenerated locally, so this command is an offline validation/build step rather than a read-only hash inspection.

For the reviewed snapshot, the command reports 18 events, eight symbols and 9,888 asset/session price rows. There are 1,236 common dates per asset, 7,416 bank price rows and 7,410 non-null bank returns. The first return per asset is unavailable by construction. A missing source, changed checksum, inconsistent date, unexplained price gap or failed selected price comparison stops the build; prices are not forward-filled to make it pass.

Source details and the limited scope of price checking are recorded in [data_sources.md](data_sources.md). Matching a file hash preserves the recorded bytes; it does not guarantee that every external observation is correct.

## 3. Run the complete offline analysis

```bash
.venv/bin/python -m rbi_intelligence run
.venv/bin/python -m rbi_intelligence verify
```

`run` builds the event study, event-level inference, corporate-action sensitivities, past-only GARCH forecasts, chronological prediction evaluation, figures, dashboard, exports, database, report and manifest. Progress messages identify the stage. GARCH fitting and bootstrap evaluation take longer than data validation; exact runtime depends on the machine.

The default statistical settings are:

| Setting | Default |
|---|---:|
| Random seed | 42 |
| Event-inference bootstrap repetitions | 10,000 |
| Held-out prediction bootstrap repetitions | 2,000 |
| Market-model estimation returns | 250 over inclusive relative days `[-255,-6]` |
| GARCH minimum historical returns | 500 |
| Prediction training end | 2024-12-31 |
| Prediction holdout | 2025-01-01 through 2025-12-31 |

The CLI exposes the seed and bootstrap counts. These equivalent explicit settings make the numerical choices reviewable:

```bash
.venv/bin/python -m rbi_intelligence run --seed 42 --bootstrap 10000 --prediction-bootstrap 2000
```

For an isolated additional build, choose a dedicated generated-output directory:

```bash
.venv/bin/python -m rbi_intelligence run --output-dir outputs-review
.venv/bin/python -m rbi_intelligence verify --output-dir outputs-review
```

The chosen directory is a complete generated destination. A successful run replaces its previous contents after validating the new staging directory; do not put hand-written work there. A failed build preserves the previous complete output directory. Local data normalization still updates the canonical processed panel and data diagnostics. Core source/data directories are protected from being selected as output destinations.

### Generated artifacts

| Path | Contents |
|---|---|
| `data/processed/market_panel.csv` | Validated common-calendar panel, actions and both return conventions |
| `outputs/tables/` | Event studies, inference, sensitivities, volatility and prediction tables |
| `outputs/figures/` | Static research figures generated from those tables |
| `outputs/tableau/` | Tableau-compatible and optional SAS-input CSV exports |
| `outputs/study.sqlite` | Validated SQLite database, regenerated locally and excluded from Git |
| `outputs/dashboard.html` | Offline interactive dashboard with embedded data |
| `outputs/RESEARCH_REPORT.md` | Current numerical findings, methods and limitations |
| `outputs/run_manifest.json` | Runtime, parameters, counts, source/code hashes and artifact hashes |

Open `outputs/dashboard.html` directly in a modern browser. It needs no account, hosted service or local web server. GitHub displays HTML source, so download the file before opening it as a dashboard.

The retained [browser verification record](verification/browser_smoke.json) identifies the tested dashboard hash and checks for filter behavior, displayed units/counts, CSV export, empty/reset behavior, mobile layout and external network requests. It is evidence for that generated version, not a substitute for checking a later changed dashboard.

`verify` checks existing generated files against the run manifest and also checks the recorded input and analysis-code hashes. It does not repeat the statistical fit or contact a source. The regenerable database is checked if present; its absence in a fresh clone is allowed and reported. Run the full pipeline when you need the database. If recorded data or code changed, rebuild the outputs instead of editing the manifest to suppress a mismatch.

## 4. Run the automated checks

```bash
.venv/bin/python -m pytest -q
```

Tests use frozen or synthetic fixtures to exercise source integrity, corrected event dates, missing-session handling, known market-model results, event-level inference, leakage/timing rules, corporate-action sensitivity, failed forecasts, database/export invariants and output rollback. Optional Spark comparison tests exercise the validator on fixtures; a passing unit suite alone does not claim a real Java/Spark job ran. The separate job below verifies that execution path.

The reviewed rebuild passed **77 Python tests** and two complete default offline builds. All **23 numerical result CSVs** were byte-identical across those builds. SQLite integrity and all supplied SQL scripts also passed. The [rebuild verification record](verification/rebuild_checks.json) records the executed scope.

Tests verify specific behavior rather than guarantee universal price accuracy or a successful forecasting strategy. The generated report, source diagnostics and declared limitations remain part of the review.

## 5. Refresh market snapshots deliberately

Use this only when you intend to acquire a new vendor vintage of the **same fixed 2021–2025 historical window**:

```bash
.venv/bin/python -m rbi_intelligence refresh-data
.venv/bin/python -m rbi_intelligence run
.venv/bin/python -m rbi_intelligence verify
```

`refresh-data` is the explicit network operation. It requests eight Yahoo chart responses and the three official NSE archive files needed for the documented repair and selected comparisons. Acquisition uses Python's standard-library HTTPS client; yfinance, browser authentication and API credentials are not required by this implementation. Provider availability or request restrictions can still prevent a download.

Downloads and validation occur in a temporary staging directory. A failed retrieval or validation preserves the preceding source snapshot. On success, the source directory is replaced with the validated new snapshot and the analytical market panel is rebuilt. Query URLs, UTC acquisition times, response hashes, sizes, actions and coverage are recorded. The policy table is validated and retained; this command does not automatically discover new RBI announcements or extend the study beyond 2025.

Historical vendor prices and adjustments can change between retrievals. Preserve the reviewed snapshot in version control before refreshing if you need to reproduce its exact findings. Review changed sources, diagnostics and numerical results before accepting a new vintage. A refresh does not justify accepting an unexplained failed price check or silently deleting an awkward observation.

## 6. Optional PySpark parity demonstration

The core analysis fits in pandas. Spark is an optional implementation-parity exercise and is not required for the research outputs. The executed environment used **PySpark 3.5.7, py4j 0.10.9.7, OpenJDK 17.0.20 and Python 3.12.14**. Install a compatible Java 17 runtime and make it available to the shell, then install the separate pinned package set:

```bash
java -version
.venv/bin/python -m pip install -r requirements-spark.txt
.venv/bin/python pyspark/01_market_data_pipeline.py --master 'local[2]' --partitions 6
.venv/bin/python pyspark/02_validate_against_pandas.py --report outputs/spark/validation.json
```

Run this **after** the core build, because a subsequent complete `run` replaces the generated output directory, including an optional Spark subdirectory placed inside it. Alternatively choose an independent Spark location:

```bash
.venv/bin/python pyspark/01_market_data_pipeline.py --output spark-review/bank_returns --master 'local[2]' --partitions 6
.venv/bin/python pyspark/02_validate_against_pandas.py --spark-dir spark-review/bank_returns --report spark-review/validation.json
```

Defaults read `data/raw/market_prices_2021_2025.csv`, retain bank rows and write CSV partitions. The validator compares all emitted `part-*.csv` files with bank rows in `data/processed/market_panel.csv`. It checks complete unique `(date, symbol)` key equality, finite returns, identical initial-null locations and numerical tolerance `1e-10`.

The executed frozen-snapshot check matched 7,416 keys, including 7,410 finite returns and six initial nulls. Its maximum absolute daily-return difference was approximately `9.90e-15`, below tolerance; the [retained parity report](verification/spark_parity.json) records the input, partition and validator hashes. The number of nonempty emitted files can differ from the requested partition count; every emitted part is read. This check covers daily close-to-close bank returns. It does not independently authenticate source prices or certify every rolling feature.

If a restricted environment blocks Spark's local Java socket, run the same command in an environment allowing that local process communication. Such an environment failure is separate from a parity failure; do not report parity as passed unless the comparison command succeeds.

## 7. SAS, Tableau and SQL

`sas/01_event_study_validation.sas` is an optional script using `outputs/tableau/sas_event_results.csv` and `sas_event_means.csv`. Run SAS with the repository as its working directory, or update the two import paths for your SAS environment. The script performs selected descriptive and event-level checks. **SAS execution has not been performed for this release**; an actual log and results are needed before claiming it as executed validation.

The files under `outputs/tableau/` can be imported into Tableau, preserving benchmark/window filters and unique event/bank grain. No `.twb` or `.twbx` workbook is supplied or claimed as executed. The delivered interactive visualization is the generated offline HTML dashboard.

The SQL scripts under `sql/` use the regenerated `outputs/study.sqlite` database. The database has enforced primary/foreign keys, retained record details and an `event_explorer` view. It is rebuilt from the same validated analytical frames used for CSV export, rather than from leftover results of earlier script runs.

## 8. What reproducibility means here

Frozen source bytes, version-pinned packages, fixed model specifications, complete calendar alignment and explicit seeds make the numerical analysis repeatable. Core result tables should agree in the reviewed environment; numerical libraries and platforms can introduce small floating-point differences. A fresh build intentionally changes UTC timestamps and therefore some manifest, dashboard, report or database bytes. **Byte-for-byte equality of every fresh build artifact is not the reproducibility claim.**

Within a completed build, checksums bind each recorded artifact, source and analysis-code file to its manifest. Across independent builds, compare the numerical tables with a declared tolerance, the parameter settings, counts and source hashes. Keep low-bootstrap development runs clearly separate from the default 10,000/2,000-replicate report. A historical-data refresh is a new source vintage, not a failed attempt to reproduce the old vintage.

## 10. Optional browser interaction check

`tests/browser_smoke.cjs` exercises the actual HTML in Chromium, including five filters, displayed units and sample counts, the corrected August date, empty/reset states, CSV download, and a 390px mobile viewport. It blocks external HTTP(S) requests and fails on page errors or attempted network access.

With Node.js, Playwright and its Chromium runtime available:

```bash
node tests/browser_smoke.cjs
```

Install the browser test dependency separately from the Python environment. The script also accepts `PLAYWRIGHT_MODULE` for an installed Playwright module path and `RBI_CHROMIUM_EXECUTABLE` for an existing Chromium binary. Browser binaries are not included in the repository. The check writes ignored desktop/mobile screenshots under `test-results/` and a fresh `docs/verification/browser_smoke.json`. The retained check ran on Chromium 133.0.6943.0.
