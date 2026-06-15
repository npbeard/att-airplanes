# Group 4 – ATT Airlines Revenue Performance Dashboard

## Group Members
- *(add names)*

## Schema Used
`ATTGRP4` on the `ATTPLANE` DB2 database hosted at `52.211.123.34:25010`.

## How to Install

> **Windows users:** `ibm_db` does not install cleanly via a plain `pip install` on Windows.
> See the workaround in the section below before running `pip install -r requirements.txt`.

### Standard install (pip)
```bash
pip uninstall -y ibm_db ibm_db_sa sqlalchemy
pip install --upgrade pip
pip install -r requirements.txt
```

### Alternative (uv)
```bash
uv sync
# if ibm_db fails inside uv, install it manually into the venv:
uv run pip install ibm_db ibm_db_sa
```

### Windows workaround for ibm_db
`ibm_db` is a C extension that requires the IBM Data Server Driver Client to be installed
on the machine. On Windows, the pip wheel often fails because that driver is missing.
The fix used in this project was to install `uv` and let it manage the virtual environment,
then force-install `ibm_db` and `ibm_db_sa` directly into the uv-managed venv:

```bash
pip install uv
uv sync
uv run pip install ibm_db ibm_db_sa
```

If `ibm_db` still fails to compile, download and install the
**IBM Data Server Driver Package** from the IBM website, then retry the pip install.

## How to Run

**Step 1 – copy and configure the environment file:**
```bash
cp .env.example .env
# credentials are already set for attgrp4 / bigdata
```

**Step 2 – prepare data (runs once, queries DB2, saves Parquet files):**
```bash
python prepare_data.py        # pip
uv run python prepare_data.py # uv
```

**Step 3 – launch the dashboard:**
```bash
streamlit run app.py        # pip
uv run streamlit run app.py # uv
```

## Business Question Answered

> **Which routes, cabin classes, and departure periods generate the most revenue?**

The dashboard focuses on revenue performance across the airline network using three views:
- Top N routes by total revenue (filterable by cabin class and continent)
- Revenue share by cabin class (Economy, Premium, Business)
- Monthly revenue trend over time (filterable by year)

## Key Findings
*(fill in after running the dashboard)*

## Assumptions
- `CLASS` codes: `E` = Economy, `P` = Premium, `B` = Business.
- All monetary amounts are in the currency stored in `TOTAL_AMOUNT` (assumed USD).

## Limitations
- All TICKETS aggregations run entirely inside DB2 to avoid transferring 248M rows.
- Parquet files must be regenerated if the source data changes.

## Project Structure
```
att-airplanes/
├── app.py            # Streamlit dashboard
├── analysis.py       # Polars transformations on Parquet data
├── db.py             # DB2 connection and SQL aggregation queries
├── prepare_data.py   # One-time data preparation script
├── data/             # Prepared Parquet files (gitignored)
├── requirements.txt
├── pyproject.toml
├── .env              # DB credentials (gitignored)
└── .env.example
```
