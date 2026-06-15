import os
import socket
from urllib.parse import quote_plus

import polars as pl
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "52.211.123.34")
DB_PORT = int(os.getenv("DB_PORT", "25010"))
DB_NAME = os.getenv("DB_NAME", "ATTPLANE")
DB_USERNAME = os.getenv("DB_USERNAME", "attgrp4")
DB_PASSWORD = os.getenv("DB_PASSWORD", "bigdata")
SCHEMA = "ATTGRP4"


def make_engine():
    user = quote_plus(DB_USERNAME)
    password = quote_plus(DB_PASSWORD)
    url = f"db2+ibm_db://{user}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url, pool_pre_ping=True)


def tcp_check(host: str = DB_HOST, port: int = DB_PORT, timeout: float = 8.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port))
    return True


def test_connection(engine) -> bool:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 AS ok FROM SYSIBM.SYSDUMMY1"))
        row = result.fetchone()
    return row is not None and row[0] == 1


def read_sql(query: str, engine) -> pl.DataFrame:
    with engine.connect() as conn:
        df = pl.read_database(query=query, connection=conn)
    return df.rename({col: col.strip().lower() for col in df.columns})


def fetch_revenue_by_route_class(engine) -> pl.DataFrame:
    """Revenue aggregated by route and cabin class from TICKETS (248M rows — runs in DB)."""
    query = f"""
    SELECT
        t.ROUTE_CODE,
        t.CLASS,
        COUNT(*) AS ticket_count,
        SUM(t.TOTAL_AMOUNT) AS revenue,
        AVG(t.TOTAL_AMOUNT) AS avg_ticket_value,
        SUM(t.AIRPORT_TAX) AS total_airport_tax,
        SUM(t.LOCAL_TAX) AS total_local_tax
    FROM {SCHEMA}.TICKETS t
    GROUP BY t.ROUTE_CODE, t.CLASS
    """
    return read_sql(query, engine)


def fetch_monthly_revenue(engine) -> pl.DataFrame:
    """Monthly revenue trend by cabin class."""
    query = f"""
    SELECT
        YEAR(t.DEPARTURE) AS year,
        MONTH(t.DEPARTURE) AS month,
        t.CLASS,
        COUNT(*) AS ticket_count,
        SUM(t.TOTAL_AMOUNT) AS revenue
    FROM {SCHEMA}.TICKETS t
    GROUP BY YEAR(t.DEPARTURE), MONTH(t.DEPARTURE), t.CLASS
    ORDER BY year, month, t.CLASS
    """
    return read_sql(query, engine)


def fetch_routes_with_airports(engine) -> pl.DataFrame:
    """Route details joined with origin and destination airport metadata."""
    query = f"""
    SELECT
        r.ROUTE_CODE, r.ORIGIN, r.DESTINATION, r.PARENT_ROUTE,
        r.LEG_NUMBER, r.DISTANCE, r.FLIGHT_MINUTES,
        orig.AIRPORT  AS origin_airport,
        orig.CITY     AS origin_city,
        orig.COUNTRY  AS origin_country,
        orig.CONTINENT AS origin_continent,
        orig.LATITUDE  AS origin_lat,
        orig.LONGITUDE AS origin_lon,
        orig.AIRPORT_TAX AS origin_tax,
        dest.AIRPORT  AS dest_airport,
        dest.CITY     AS dest_city,
        dest.COUNTRY  AS dest_country,
        dest.CONTINENT AS dest_continent,
        dest.LATITUDE  AS dest_lat,
        dest.LONGITUDE AS dest_lon,
        dest.AIRPORT_TAX AS dest_tax
    FROM {SCHEMA}.ROUTES r
    JOIN {SCHEMA}.AIRPORTS orig ON r.ORIGIN  = orig.IATA_CODE
    JOIN {SCHEMA}.AIRPORTS dest ON r.DESTINATION = dest.IATA_CODE
    """
    return read_sql(query, engine)
