"""
Polars analytics on prepared Parquet datasets.

Every public function is a self-contained lazy pipeline:
  pl.scan_parquet(...)  <- lazy read, no data loaded yet
  .filter(...)          <- predicate pushed down to the file scan
  .group_by(...).agg(...)
  .join(pl.scan_parquet(...), ...)  <- lazy join, optimised together
  .collect()            <- single execution point
"""

from pathlib import Path

import polars as pl

DATA_DIR = Path("data")

CLASS_LABELS = {"E": "Economy", "P": "Premium", "B": "Business"}
CLASS_ORDER = ["Economy", "Premium", "Business"]

_CABIN_LABEL = (
    pl.when(pl.col("class") == "E").then(pl.lit("Economy"))
    .when(pl.col("class") == "P").then(pl.lit("Premium"))
    .when(pl.col("class") == "B").then(pl.lit("Business"))
    .otherwise(pl.col("class"))
    .alias("cabin_class")
)


def revenue_by_route(
    class_filter: list[str],
    continent_filter: list[str],
    top_n: int = 15,
) -> pl.DataFrame:
    route_meta = (
        pl.scan_parquet(DATA_DIR / "routes_with_airports.parquet")
        .select(["route_code", "origin_city", "dest_city", "origin_continent", "distance"])
    )

    return (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        .group_by("route_code")
        .agg(
            pl.col("ticket_count").sum(),
            pl.col("revenue").sum(),
            pl.col("avg_ticket_value").mean(),
        )
        .join(route_meta, on="route_code", how="left")
        .filter(pl.col("origin_continent").is_in(continent_filter))
        .sort("revenue", descending=True)
        .head(top_n)
        .with_columns(
            (
                pl.col("origin_city").fill_null(pl.col("route_code"))
                + " → "
                + pl.col("dest_city").fill_null("?")
            ).alias("route_label")
        )
        .collect()
    )


def revenue_by_class(class_filter: list[str]) -> pl.DataFrame:
    return (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        .group_by("class")
        .agg(
            pl.col("ticket_count").sum(),
            pl.col("revenue").sum(),
        )
        .with_columns(_CABIN_LABEL)
        .sort("revenue", descending=True)
        .collect()
    )


def monthly_trend(
    class_filter: list[str],
    year_filter: int | None = None,
) -> pl.DataFrame:
    lf = (
        pl.scan_parquet(DATA_DIR / "monthly_revenue.parquet")
        .filter(pl.col("class").is_in(class_filter))
    )
    if year_filter is not None:
        lf = lf.filter(pl.col("year") == year_filter)

    return (
        lf.group_by("year", "month")
        .agg(
            pl.col("revenue").sum(),
            pl.col("ticket_count").sum(),
        )
        .sort("year", "month")
        .collect()
        .with_columns(
            pl.date(
                pl.col("year").cast(pl.Int32),
                pl.col("month").cast(pl.Int32),
                pl.lit(1),
            ).alias("date")
        )
    )
