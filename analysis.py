from pathlib import Path

import polars as pl

DATA_DIR = Path("data")

CLASS_ORDER = ["Economy", "Premium", "Business"]

# reusable expression to translate E/P/B codes into readable labels
_CABIN_LABEL = (
    pl.when(pl.col("class") == "E").then(pl.lit("Economy"))
    .when(pl.col("class") == "P").then(pl.lit("Premium"))
    .when(pl.col("class") == "B").then(pl.lit("Business"))
    .otherwise(pl.col("class"))
    .alias("cabin_class")
)


# returns the top N routes by total revenue, filtered by class and continent
def revenue_by_route(
    class_filter: list[str],
    continent_filter: list[str],
    top_n: int = 15,
) -> pl.DataFrame:
    # pull only the columns we need from routes to keep the join light
    route_meta = (
        pl.scan_parquet(DATA_DIR / "routes_with_airports.parquet")
        .select([
            "route_code", "origin_city", "dest_city",
            "origin_continent", "distance",
        ])
    )

    return (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        # collapse the class breakdown into one row per route
        .group_by("route_code")
        .agg(
            pl.col("ticket_count").sum(),
            pl.col("revenue").sum(),
            pl.col("avg_ticket_value").mean(),
        )
        # bring in city names and continent from the routes file
        .join(route_meta, on="route_code", how="left")
        .filter(pl.col("origin_continent").is_in(continent_filter))
        .sort("revenue", descending=True)
        .head(top_n)
        # fall back to route_code if city name is missing
        .with_columns(
            (
                pl.col("origin_city").fill_null(pl.col("route_code"))
                + " → "
                + pl.col("dest_city").fill_null("?")
            ).alias("route_label")
        )
        .collect()
    )


# returns total revenue and ticket count per cabin class (for the donut chart)
def revenue_by_class(class_filter: list[str]) -> pl.DataFrame:
    return (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        .group_by("class")
        .agg(
            pl.col("ticket_count").sum(),
            pl.col("revenue").sum(),
        )
        # convert E/P/B codes to readable names before returning
        .with_columns(_CABIN_LABEL)
        .sort("revenue", descending=True)
        .collect()
    )


# returns monthly revenue aggregated across classes, with optional year filter
def monthly_trend(
    class_filter: list[str],
    year_filter: int | None = None,
) -> pl.DataFrame:
    lf = (
        pl.scan_parquet(DATA_DIR / "monthly_revenue.parquet")
        .filter(pl.col("class").is_in(class_filter))
    )
    # year filter is optional - if None, all years are included
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
        # build a proper date column so Plotly renders the x-axis correctly
        .with_columns(
            pl.date(
                pl.col("year").cast(pl.Int32),
                pl.col("month").cast(pl.Int32),
                pl.lit(1),
            ).alias("date")
        )
    )


# returns monthly revenue keeping the class dimension for a stacked chart
def monthly_by_class(
    class_filter: list[str],
    year_filter: int | None = None,
) -> pl.DataFrame:
    lf = (
        pl.scan_parquet(DATA_DIR / "monthly_revenue.parquet")
        .filter(pl.col("class").is_in(class_filter))
        .with_columns(_CABIN_LABEL)
    )
    if year_filter is not None:
        lf = lf.filter(pl.col("year") == year_filter)
    return (
        lf.sort("year", "month")
        .collect()
        .with_columns(
            pl.date(
                pl.col("year").cast(pl.Int32),
                pl.col("month").cast(pl.Int32),
                pl.lit(1),
            ).alias("date")
        )
    )


# returns total revenue and ticket count grouped by origin continent
def revenue_by_continent(class_filter: list[str]) -> pl.DataFrame:
    route_meta = (
        pl.scan_parquet(DATA_DIR / "routes_with_airports.parquet")
        .select(["route_code", "origin_continent"])
    )
    return (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        .group_by("route_code")
        .agg(pl.col("ticket_count").sum(), pl.col("revenue").sum())
        .join(route_meta, on="route_code", how="left")
        .filter(pl.col("origin_continent").is_not_null())
        .group_by("origin_continent")
        .agg(pl.col("revenue").sum(), pl.col("ticket_count").sum())
        .sort("revenue", descending=True)
        .collect()
    )


# returns top N routes ranked by revenue per km - reveals route efficiency
def route_efficiency(
    class_filter: list[str],
    continent_filter: list[str],
    top_n: int = 15,
) -> pl.DataFrame:
    route_meta = (
        pl.scan_parquet(DATA_DIR / "routes_with_airports.parquet")
        .select([
            "route_code", "origin_city", "dest_city",
            "origin_continent", "distance",
        ])
    )
    return (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        .group_by("route_code")
        .agg(pl.col("ticket_count").sum(), pl.col("revenue").sum())
        .join(route_meta, on="route_code", how="left")
        .filter(pl.col("origin_continent").is_in(continent_filter))
        .filter(pl.col("distance").is_not_null())
        .filter(pl.col("distance") > 0)
        .with_columns(
            (pl.col("revenue") / pl.col("distance")).alias("revenue_per_km"),
            (
                pl.col("origin_city").fill_null(pl.col("route_code"))
                + " → "
                + pl.col("dest_city").fill_null("?")
            ).alias("route_label"),
        )
        .sort("revenue_per_km", descending=True)
        .head(top_n)
        .collect()
    )
