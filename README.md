# Group 4 – ATT Airlines Revenue Performance Dashboard

## Group Members
- Jose Maria Brandao
- Juan Camilo Lujan
- Laurenz Jakob Kluth
- Nicolas Beard
- Stephan Pentchev

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

## Activate the Virtual Environment

**Windows (PowerShell):**

```powershell
.venv\Scripts\activate
```

**Mac / Linux:**

```bash
source .venv/bin/activate
```

## How to Run

**Step 1 – create a `.env` file with your DB2 credentials (required before running anything):**
```bash
cp .env.example .env
```
Then open `.env` and fill in the values for `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USERNAME`, and `DB_PASSWORD`. The app will fail with a clear error if any of these are missing.

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
- Seasonality: Overall, November and April are valley months with lowest revenue generation. August and January, on the other hand are the months with highest revenue. This matches with usual holiday trends.
- Revenue by cabin class: The vast majority of the revenue (77%) comes from Economy class, while less than 5% of revenue comes from Premium class.
- Key routes: The top 8 routes in revenue generation are the ones that connect the following cities (in both ways):
Naples and Las Vegas
Tokyo and Rome
Hongkong and Manchester
Lille and Tokyo.
    These are all long distance, intercontinental routes. Tokyo is the city with highest presence.
- Based on the trend chart does not seem to be increasing or decreasing over time. 


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
