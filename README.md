# Group 4 – ATT Airlines Revenue Performance Dashboard

## Group Members
- *(add names)*

## Schema Used
`ATTGRP4` on the `ATTPLANE` DB2 database hosted at `52.211.123.34:25010`.

## How to Install

```bash
uv sync
uv run pip install ibm_db ibm_db_sa
```

> `ibm_db` is a C extension that requires IBM's native DB2 driver. On Windows it does not
> install cleanly through a standard `pip install`. Using `uv sync` first, then installing
> `ibm_db` and `ibm_db_sa` separately into the uv-managed venv, is the workaround that works.

## How to Run

**Step 1 – create a `.env` file based on `.env.example` and fill in your credentials:**
```bash
cp .env.example .env
# then open .env and fill in the values
```

**Step 2 – prepare data (runs once, queries DB2, saves Parquet files):**
```bash
uv run python prepare_data.py
```

**Step 3 – launch the dashboard:**
```bash
uv run streamlit run app.py
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
