# ATT Airlines Dashboard – Project Walkthrough

## Which Business Dashboard Example We Used

**Example 1 – Revenue Performance Dashboard**

> Business question: *Which routes, cabin classes, and departure periods generate the most revenue?*

This was chosen as the simplest example because:
- It relies on a single core table (`TICKETS`) with two supporting reference tables (`ROUTES`, `AIRPORTS`).
- The metrics are straightforward: sum of revenue, count of tickets, average ticket value.
- No joins across complex operational tables (e.g., FLIGHTS, AIRPLANES, PASSENGERS) are required.
- The visualizations map directly to the business question without needing derived or estimated metrics.

---

## Database Connection and Setup

### The Problem on Windows

The `ibm_db` Python package is a C extension that wraps IBM's native DB2 driver. On Windows, simply running `pip install ibm_db` often fails or silently produces a broken installation because:

1. **The IBM Data Server Driver Client is not installed on the machine.** `ibm_db` requires IBM's native DLLs to be present at the system level. Without them, the installed package can import successfully but fails the moment it tries to open a connection.
2. **Version conflicts between `ibm_db`, `ibm_db_sa`, and `sqlalchemy`.** The SQLAlchemy dialect for DB2 (`ibm_db_sa`) is sensitive to the exact version of SQLAlchemy installed. A fresh `pip install` without version pinning can resolve a combination that does not work together.

The professor's instructions likely assumed a Linux/Mac environment or that students had already installed the IBM driver separately, which is why Windows machines hit errors that others did not.

### The Workaround Used

The project uses **`uv`** as the package manager instead of plain `pip`. `uv` creates an isolated virtual environment and resolves dependencies more predictably. The key steps that made it work:

```bash
# 1. Install uv (if not already installed)
pip install uv

# 2. Let uv resolve and install all declared dependencies
uv sync

# 3. Force-install ibm_db and ibm_db_sa directly into uv's managed venv
#    (uv sync may skip or fail these; installing them separately avoids the conflict)
uv run pip install ibm_db ibm_db_sa
```

After this, running any script through `uv run` ensures it uses the correct environment where `ibm_db` is properly wired up.

**Why does `uv run pip install ibm_db ibm_db_sa` work when `pip install` alone didn't?**
Two reasons:
- It installs into the isolated venv that `uv sync` already set up, avoiding conflicts with system-level packages.
- `uv sync` first installs the pinned version of `sqlalchemy` declared in `pyproject.toml` (`>=2.0.50`), so when `ibm_db_sa` is added afterwards it finds a compatible SQLAlchemy already in place.

### Environment File

Credentials are stored in a `.env` file (not committed to git). Copy the example and the defaults are already correct for Group 4:

```bash
cp .env.example .env
```

The `.env` file contains:
```
DB_HOST=52.211.123.34
DB_PORT=25010
DB_NAME=ATTPLANE
DB_USERNAME=attgrp4
DB_PASSWORD=bigdata
```

These are loaded at runtime by `python-dotenv` inside `db.py`.

### How the Connection Works in Code (`db.py`)

The connection is built with SQLAlchemy using the `db2+ibm_db` dialect:

```python
url = f"db2+ibm_db://{user}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(url, pool_pre_ping=True)
```

Before attempting a full connection, `db.py` runs two checks:

1. **TCP check** (`tcp_check()`): Opens a raw socket to `52.211.123.34:25010` to verify that the database server is reachable over the network. If this fails, the DB2 driver itself never gets called, which makes the error message much clearer.
2. **Authentication check** (`test_connection()`): Runs `SELECT 1 FROM SYSIBM.SYSDUMMY1`, the DB2 equivalent of a ping query, to confirm the username and password are accepted.

Once connected, `read_sql()` executes any query and returns a Polars DataFrame, automatically normalizing all column names to lowercase (DB2 returns uppercase names by default).

---

## How the Project Was Built – Step by Step

### Step 1: Project Structure

```
att-airplanes/
├── app.py            ← Streamlit dashboard UI
├── analysis.py       ← Polars transformations
├── db.py             ← DB2 connection + SQL queries
├── prepare_data.py   ← One-time data pull script
├── data/             ← Parquet files (not committed to git)
├── requirements.txt
├── .env              ← DB credentials (not committed to git)
└── .env.example
```

---

### Step 2: SQL Queries in DB2 (`db.py`)

Three queries were written to pull only what the Revenue Performance dashboard needs.
All heavy aggregations run **inside DB2** so that only small result sets travel over the network
(the TICKETS table has 248 million rows — pulling it raw would be impractical):

| Function | Tables Used | What It Fetches |
|---|---|---|
| `fetch_revenue_by_route_class` | `TICKETS` | Revenue, ticket count, avg ticket value grouped by route code and cabin class |
| `fetch_monthly_revenue` | `TICKETS` | Same metrics grouped by year, month, and cabin class |
| `fetch_routes_with_airports` | `ROUTES` + `AIRPORTS` (×2) | Route metadata: origin/destination city, country, continent, distance |

The `AIRPORTS` table is joined twice in `fetch_routes_with_airports` — once aliased as `orig` for the origin airport and once as `dest` for the destination — to get city names and continent labels for both ends of each route.

---

### Step 3: Data Preparation (`prepare_data.py`)

This script runs **once** before launching the dashboard. It:
1. Checks TCP connectivity to the DB2 server.
2. Authenticates via a test query.
3. Calls each fetch function and saves the result as a Parquet file in `data/`.

The three Parquet files produced are:
- `routes_with_airports.parquet`
- `revenue_by_route_class.parquet`
- `monthly_revenue.parquet`

After this step the dashboard runs entirely from local Parquet files — no DB2 connection is needed during normal use.

---

### Step 4: Polars Analytics (`analysis.py`)

Three functions, each a self-contained lazy pipeline:

**`revenue_by_route(class_filter, continent_filter, top_n)`**
- Reads `revenue_by_route_class.parquet`, filters by cabin class, aggregates revenue and ticket count per route.
- Joins with `routes_with_airports.parquet` to attach city names and continent.
- Filters by origin continent, sorts by revenue descending, returns the top N rows.
- Adds a `route_label` column formatted as `"City A → City B"` for chart display.

**`revenue_by_class(class_filter)`**
- Reads `revenue_by_route_class.parquet`, groups by cabin class, sums revenue and ticket count.
- Translates class codes (`E`, `P`, `B`) to readable labels (`Economy`, `Premium`, `Business`).

**`monthly_trend(class_filter, year_filter)`**
- Reads `monthly_revenue.parquet`, optionally filters by a single year.
- Groups by year and month, sums revenue and ticket count.
- Constructs a proper `date` column (`YYYY-MM-01`) for correct time-axis plotting.

All three use `.lazy()` / `scan_parquet()` so Polars can push filter predicates down to the file scan before loading any data into memory.

---

### Step 5: Streamlit Dashboard (`app.py`)

**Sidebar filters (4 filters):**
- Cabin class — multiselect (Economy, Premium, Business)
- Origin continent — multiselect populated dynamically from the data
- Year — selectbox (All years or a specific year, affects the trend chart only)
- Top N routes — slider from 5 to 30

**KPI header (4 metrics, update with cabin class filter):**
- Total Revenue
- Total Tickets
- Average Ticket Value
- Active Routes

**Section 1 – Revenue by Route:**
- Horizontal bar chart: top N routes sorted by total revenue
- Donut chart: revenue share split by Economy / Premium / Business

**Section 2 – Revenue Over Time:**
- Line chart: monthly revenue from `monthly_revenue.parquet`, filtered by year if selected

**Data Preview:**
- Two tabs — Top Routes and Monthly Trend — each with a CSV download button

All data-loading functions use `@st.cache_data` with tuple arguments (tuples are hashable; lists are not) so Polars pipelines are not re-executed on every Streamlit rerender.

---

## Assignment Requirements – Checklist

| Requirement | Status | Notes |
|---|---|---|
| Connect to DB2 | ✅ | `db.py` with SQLAlchemy + ibm_db |
| Use Polars to clean and prepare data | ✅ | All transformations in `analysis.py` |
| Join at least two tables | ✅ | `ROUTES` + `AIRPORTS` (×2) in `fetch_routes_with_airports` |
| At least three analytical outputs | ✅ | Top routes, cabin class share, monthly trend |
| At least two interactive filters | ✅ | Four filters: cabin class, continent, year, top N |
| At least three charts | ✅ | Bar chart, donut chart, line chart |
| Short written explanation of insights | ✅ | Text blocks under each section heading in `app.py` |
| Clear title and description | ✅ | Title + caption at the top of the dashboard |
| Key metrics at the top | ✅ | Four KPI cards |
| Data preview or downloadable table | ✅ | Tabs with dataframes and CSV download buttons |
| README with all required sections | ⚠️ | Group members and key findings still need to be filled in manually |
| Save prepared datasets as Parquet | ✅ | Three `.parquet` files in `data/` |
| Polars lazy pipelines | ✅ | All functions use `scan_parquet()` + `.collect()` |

---

## Business Insights to Present

These are the talking points you can use in the live demo. Fill in the actual numbers after running the dashboard.

**Top routes by revenue:**
- A small number of routes likely account for a disproportionate share of total revenue (Pareto effect). Identifying these routes is the first step for capacity and pricing decisions.
- Routes near the top of the bar chart that also have high average ticket values (visible on hover) represent premium-priced connections — potentially candidates for increased frequency.

**Cabin class share:**
- Business class generates a much higher revenue-per-ticket than Economy, even though ticket volume is lower. If the donut shows Business contributing more than its proportional seat share, that supports expanding Business seating on top routes.
- Economy's high ticket count but lower revenue share reflects price-sensitive demand — useful context for yield management.

**Monthly revenue trend:**
- Seasonal peaks (e.g., summer months, end-of-year holidays) are visible in the line chart. These indicate when demand is highest and when pricing could be adjusted upward.
- Year-over-year comparison (using the year filter) can reveal whether revenue is growing or declining on the same seasonal pattern.
