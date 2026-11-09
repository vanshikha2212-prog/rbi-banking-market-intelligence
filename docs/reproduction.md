# Reproduction

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m rbi_intelligence validate-data
python -m rbi_intelligence run
python -m rbi_intelligence verify
python -m pytest -q
```

The standard run is offline and publishes outputs transactionally. It recomputes and verifies all tables, charts, report, dashboard, database, and exports.

To retrieve a new official NSE vintage:

```bash
python scripts/fetch_nse_history.py
python -m rbi_intelligence run
```

A refresh is explicit because new source bytes change downstream results. Review and commit the manifest and outputs together.
