"""
Run this script once to pull data from DB2 and save Parquet files for the dashboard.

    pip:  python prepare_data.py
    uv:   uv run python prepare_data.py

The TICKETS table has 248M rows. All aggregations run inside DB2 so only
small result sets are transferred. Expect the passenger geography query to
take several minutes because it joins TICKETS with PASSENGERS.
"""

from pathlib import Path

import db

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

TASKS = [
    ("routes_with_airports",   db.fetch_routes_with_airports),
    ("fleet_utilization",      db.fetch_fleet_utilization),
    ("revenue_by_route_class", db.fetch_revenue_by_route_class),
    ("monthly_revenue",        db.fetch_monthly_revenue),
    ("passenger_geography",    db.fetch_passenger_geography),   # slowest — large join
]


def main() -> None:
    print("Checking network connectivity...")
    try:
        db.tcp_check()
        print(f"  TCP OK: {db.DB_HOST}:{db.DB_PORT}")
    except Exception as exc:
        print(f"  TCP FAILED: {exc}")
        return

    print("Connecting to DB2...")
    engine = db.make_engine()
    try:
        assert db.test_connection(engine)
        print("  Authentication OK")
    except Exception as exc:
        print(f"  Authentication FAILED: {exc}")
        return

    for name, fn in TASKS:
        path = DATA_DIR / f"{name}.parquet"
        print(f"  Fetching {name}...", end=" ", flush=True)
        try:
            df = fn(engine)
            df.write_parquet(path)
            print(f"{df.height:,} rows -> {path}")
        except Exception as exc:
            print(f"FAILED: {exc}")

    print("\nDone. Start the dashboard with:")
    print("  streamlit run app.py        (pip)")
    print("  uv run streamlit run app.py (uv)")


if __name__ == "__main__":
    main()
