from pathlib import Path

import db

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# each tuple is (output filename, fetch function from db.py)
TASKS = [
    ("routes_with_airports",   db.fetch_routes_with_airports),
    ("revenue_by_route_class", db.fetch_revenue_by_route_class),
    ("monthly_revenue",        db.fetch_monthly_revenue),
]


def main() -> None:
    # check network before attempting a full DB2 connection
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
    print("  uv run streamlit run app.py")


if __name__ == "__main__":
    main()
