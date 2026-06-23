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
        # cast the DB2 Decimal to float so the metric formats cleanly downstream
        .with_columns(pl.col("revenue").cast(pl.Float64))
        # collapse the class breakdown into one row per route
        .group_by("route_code")
        .agg(
            pl.col("ticket_count").sum(),
            pl.col("revenue").sum(),
        )
        # avg ticket value must be recomputed from the route totals — averaging
        # the per-class averages would be wrong when classes have different volumes
        .with_columns(
            (pl.col("revenue") / pl.col("ticket_count")).alias("avg_ticket_value")
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


# returns airport tax, local tax and the effective tax rate per origin continent
def tax_by_continent(
    class_filter: list[str],
    continent_filter: list[str],
) -> pl.DataFrame:
    # total_airport_tax / total_local_tax are fetched by db.py but were unused —
    # this surfaces the tax burden that sits on top of each continent's revenue
    route_meta = (
        pl.scan_parquet(DATA_DIR / "routes_with_airports.parquet")
        .select(["route_code", "origin_continent"])
    )
    return (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        # cast the DB2 Decimals to float so the ratios format cleanly downstream
        .with_columns(
            pl.col("revenue").cast(pl.Float64),
            pl.col("total_airport_tax").cast(pl.Float64),
            pl.col("total_local_tax").cast(pl.Float64),
        )
        .group_by("route_code")
        .agg(
            pl.col("revenue").sum(),
            pl.col("total_airport_tax").sum(),
            pl.col("total_local_tax").sum(),
        )
        .join(route_meta, on="route_code", how="left")
        .filter(pl.col("origin_continent").is_not_null())
        .filter(pl.col("origin_continent").is_in(continent_filter))
        .group_by("origin_continent")
        .agg(
            pl.col("revenue").sum(),
            pl.col("total_airport_tax").sum(),
            pl.col("total_local_tax").sum(),
        )
        .with_columns(
            (pl.col("total_airport_tax") + pl.col("total_local_tax")).alias("total_tax")
        )
        # effective tax rate = all taxes collected / ticket revenue for that continent
        .with_columns(
            pl.when(pl.col("revenue") > 0)
            .then((pl.col("total_tax") / pl.col("revenue")) * 100)
            .otherwise(0.0)
            .alias("tax_rate_pct")
        )
        .sort("total_tax", descending=True)
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


# returns total revenue per origin airport with coordinates, for the map view
def revenue_by_airport(
    class_filter: list[str],
    continent_filter: list[str],
) -> pl.DataFrame:
    # origin airport coordinates and continent, one row per route
    route_meta = (
        pl.scan_parquet(DATA_DIR / "routes_with_airports.parquet")
        .select([
            "route_code", "origin", "origin_airport", "origin_city",
            "origin_continent", "origin_lat", "origin_lon",
        ])
    )
    return (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        # cast the DB2 Decimal so Plotly can size/colour the bubbles
        .with_columns(pl.col("revenue").cast(pl.Float64))
        .group_by("route_code")
        .agg(pl.col("ticket_count").sum(), pl.col("revenue").sum())
        .join(route_meta, on="route_code", how="left")
        .filter(pl.col("origin_continent").is_in(continent_filter))
        # revenue is attributed to the route's departure (origin) airport
        .group_by("origin")
        .agg(
            pl.col("origin_airport").first(),
            pl.col("origin_city").first(),
            pl.col("origin_continent").first(),
            pl.col("origin_lat").first(),
            pl.col("origin_lon").first(),
            pl.col("ticket_count").sum(),
            pl.col("revenue").sum(),
        )
        # can't plot an airport without coordinates
        .drop_nulls(["origin_lat", "origin_lon"])
        .sort("revenue", descending=True)
        .collect()
    )


# overall KPI numbers — honors both the class and origin-continent filters
def kpi_totals(
    class_filter: list[str],
    continent_filter: list[str],
) -> tuple[float, int, float, int]:
    route_meta = (
        pl.scan_parquet(DATA_DIR / "routes_with_airports.parquet")
        .select(["route_code", "origin_continent"])
    )
    df = (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        .with_columns(pl.col("revenue").cast(pl.Float64))
        .group_by("route_code")
        .agg(pl.col("ticket_count").sum(), pl.col("revenue").sum())
        .join(route_meta, on="route_code", how="left")
        .filter(pl.col("origin_continent").is_in(continent_filter))
        .select(["revenue", "ticket_count", "route_code"])
        .collect()
    )
    total_revenue = float(df["revenue"].sum() or 0.0)
    total_tickets = int(df["ticket_count"].sum() or 0)
    avg_ticket = total_revenue / total_tickets if total_tickets > 0 else 0.0
    active_routes = df["route_code"].n_unique()
    return total_revenue, total_tickets, avg_ticket, active_routes


# returns revenue by origin -> destination continent pair (for the region heatmap)
def regional_revenue(
    class_filter: list[str],
    continent_filter: list[str],
) -> pl.DataFrame:
    route_meta = (
        pl.scan_parquet(DATA_DIR / "routes_with_airports.parquet")
        .select(["route_code", "origin_continent", "dest_continent", "distance"])
    )
    return (
        pl.scan_parquet(DATA_DIR / "revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(class_filter))
        .with_columns(pl.col("revenue").cast(pl.Float64))
        .group_by("route_code")
        .agg(pl.col("ticket_count").sum(), pl.col("revenue").sum())
        .join(route_meta, on="route_code", how="left")
        .filter(pl.col("origin_continent").is_in(continent_filter))
        .with_columns(
            (
                pl.col("origin_continent").fill_null("Unknown")
                + " → "
                + pl.col("dest_continent").fill_null("Unknown")
            ).alias("region_pair")
        )
        # one row per origin/destination continent pair
        .group_by(["origin_continent", "dest_continent", "region_pair"])
        .agg(
            pl.col("ticket_count").sum(),
            pl.col("revenue").sum(),
            pl.col("route_code").n_unique().alias("route_count"),
            pl.col("distance").mean().alias("avg_distance"),
        )
        .with_columns(
            (pl.col("revenue") / pl.col("ticket_count")).alias("avg_ticket_value"),
            (pl.col("revenue") / pl.col("revenue").sum()).alias("revenue_share"),
        )
        .sort("revenue", descending=True)
        .collect()
    )
