# Group 4 – ATT Airlines Operations Dashboard

## Group Members
- *(add names)*

## Schema Used
`ATTGRP4` on the `ATTPLANE` DB2 database hosted at `52.211.123.34:25010`.

## How to Install

### Option A – pip (recommended by instructor)
```bash
pip uninstall -y ibm_db ibm_db_sa sqlalchemy
pip install --upgrade pip
pip install -r requirements.txt
```

### Option B – uv
```bash
uv sync
# if ibm_db fails inside uv, install manually into the venv:
uv run pip install ibm_db ibm_db_sa
```

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
> The `passenger_geography` query joins 248M tickets with 500K passengers and may take several minutes.

**Step 3 – launch the dashboard:**
```bash
streamlit run app.py        # pip
uv run streamlit run app.py # uv
```

## Business Questions Answered

| Section | Question |
|---|---|
| Revenue Performance | Which routes, cabin classes, and months generate the most revenue? |
| Route Efficiency | Which routes yield the highest revenue per kilometer? How does distance relate to ticket value? |
| Fleet Utilization | Which aircraft models are most scheduled? Which aircraft show high maintenance indicators? |
| Passenger Segments | Which countries drive the most revenue? How do VIP and regular passengers differ? |

## Key Findings
*(fill in after running the dashboard)*

## Assumptions
- `CLASS` codes: `E` = Economy, `P` = Premium, `B` = Business.
- All monetary amounts are in the currency stored in `TOTAL_AMOUNT` (assumed USD).
- `VIPCARD IS NOT NULL` is used to classify VIP passengers.
- Aircraft age is computed as 2025 minus the `BUILD_DATE` year.

## Limitations
- All TICKETS aggregations run entirely inside DB2 to avoid transferring 248M rows.
- Parquet files must be regenerated if the source data changes.
- The map/geo chart is not included due to only 30 airports being in the reference table.

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
