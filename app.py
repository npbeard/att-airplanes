import polars as pl
import plotly.express as px
import streamlit as st

import analysis as an

st.set_page_config(
    page_title="ATT Airlines Dashboard – Group 4",
    layout="wide",
    page_icon="✈️",
)

# ---------------------------------------------------------------------------
# Cached data loaders
# @st.cache_data stores the result so the pipeline doesn't re-run on every
# Streamlit interaction. Tuples instead of lists because cache requires hashable args.
# ---------------------------------------------------------------------------


@st.cache_data
def get_revenue_by_route(
    class_filter: tuple, continent_filter: tuple, top_n: int
) -> pl.DataFrame:
    return an.revenue_by_route(list(class_filter), list(continent_filter), top_n)


@st.cache_data
def get_revenue_by_class(class_filter: tuple) -> pl.DataFrame:
    return an.revenue_by_class(list(class_filter))


@st.cache_data
def get_monthly_trend(
    class_filter: tuple, year_filter: int | None
) -> pl.DataFrame:
    return an.monthly_trend(list(class_filter), year_filter)


@st.cache_data
def get_monthly_by_class(
    class_filter: tuple, year_filter: int | None
) -> pl.DataFrame:
    return an.monthly_by_class(list(class_filter), year_filter)


@st.cache_data
def get_revenue_by_continent(class_filter: tuple) -> pl.DataFrame:
    return an.revenue_by_continent(list(class_filter))


@st.cache_data
def get_route_efficiency(
    class_filter: tuple, continent_filter: tuple, top_n: int
) -> pl.DataFrame:
    return an.route_efficiency(list(class_filter), list(continent_filter), top_n)


@st.cache_data
def get_continents() -> list[str]:
    return (
        pl.scan_parquet("data/routes_with_airports.parquet")
        .select("origin_continent")
        .drop_nulls()
        .unique()
        .collect()
        .sort("origin_continent")
        ["origin_continent"]
        .to_list()
    )


@st.cache_data
def get_years() -> list[int]:
    return (
        pl.scan_parquet("data/monthly_revenue.parquet")
        .select("year")
        .unique()
        .collect()
        .sort("year")
        ["year"]
        .to_list()
    )


@st.cache_data
def get_kpi_totals(class_filter: tuple) -> tuple[float, int, float, int]:
    df = (
        pl.scan_parquet("data/revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(list(class_filter)))
        .select(["revenue", "ticket_count", "route_code"])
        .collect()
    )
    total_revenue = df["revenue"].sum()
    total_tickets = int(df["ticket_count"].sum())
    avg_ticket = total_revenue / total_tickets if total_tickets > 0 else 0.0
    active_routes = df["route_code"].n_unique()
    return total_revenue, total_tickets, avg_ticket, active_routes


@st.cache_data
def get_db_stats() -> dict:
    routes = pl.scan_parquet("data/routes_with_airports.parquet").collect()
    revenue = pl.scan_parquet("data/revenue_by_route_class.parquet").collect()
    monthly = pl.scan_parquet("data/monthly_revenue.parquet").collect()
    iata_codes = set(routes["origin"].to_list()) | set(routes["destination"].to_list())
    return {
        "routes": routes["route_code"].n_unique(),
        "airports": len(iata_codes),
        "tickets": int(revenue["ticket_count"].sum()),
        "countries": routes["origin_country"].drop_nulls().n_unique(),
        "year_min": int(monthly["year"].min()),
        "year_max": int(monthly["year"].max()),
    }


# stop early if parquet files haven't been generated yet
try:
    get_continents()
except FileNotFoundError:
    st.error("Parquet files not found. Run `uv run python prepare_data.py` first.")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.sidebar.title("Filters")
st.sidebar.markdown("---")

CLASS_OPTIONS = {"Economy": "E", "Premium": "P", "Business": "B"}

selected_class_labels = st.sidebar.multiselect(
    "Cabin class",
    options=list(CLASS_OPTIONS.keys()),
    default=list(CLASS_OPTIONS.keys()),
)
class_filter = (
    tuple(CLASS_OPTIONS[label] for label in selected_class_labels)
    or tuple(CLASS_OPTIONS.values())
)

all_continents = get_continents()
selected_continents = st.sidebar.multiselect(
    "Origin continent", options=all_continents, default=all_continents
)
continent_filter = tuple(selected_continents) or tuple(all_continents)

all_years = get_years()
selected_year = st.sidebar.selectbox(
    "Year (trend chart)", options=["All"] + [str(y) for y in all_years]
)
year_filter = int(selected_year) if selected_year != "All" else None

top_n = st.sidebar.slider("Top N routes", min_value=5, max_value=30, value=15)

st.sidebar.markdown("---")
st.sidebar.caption("Data: ATTPLANE DB2 · Schema: ATTGRP4")

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

st.title("✈️ ATT Airlines – Revenue Performance Dashboard")
st.caption(
    "Analyzing which routes, cabin classes, and departure periods generate the most "
    "revenue. Data source: ATTPLANE DB2 · Schema: ATTGRP4."
)

# ---------------------------------------------------------------------------
# Top-level page tabs
# ---------------------------------------------------------------------------

page_intro, page_dashboard, page_conclusions = st.tabs(
    ["🗄️ About the Data", "📊 Dashboard", "📝 Conclusions & Future Work"]
)

# ===========================================================================
# Tab 1 – About the Data
# ===========================================================================

with page_intro:

    st.header("Project Overview")
    st.markdown(
        """
        This dashboard was built by **Group 4** as part of the Advanced Topics in
        Technology course at IE University. Our goal is to answer the following
        business question:

        > **Which routes, cabin classes, and departure periods generate the most
        > revenue for ATT Airlines?**

        We connect to an **IBM DB2** enterprise database, extract pre-aggregated
        data from the `ATTGRP4` schema, and present it as an interactive Streamlit
        dashboard backed by Polars and Plotly.
        """
    )

    st.divider()

    st.header("Database at a Glance")

    stats = get_db_stats()
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Unique Routes", f"{stats['routes']:,}")
    s2.metric("Airports", f"{stats['airports']:,}")
    s3.metric("Total Tickets", f"{stats['tickets']:,}")
    s4.metric("Countries", f"{stats['countries']:,}")
    s5.metric("Years Covered", f"{stats['year_min']} – {stats['year_max']}")

    st.markdown(
        """
        The source database is an **IBM DB2** instance named `ATTPLANE`, hosted at
        `52.211.123.34:25010`, accessed via the `ATTGRP4` schema. Because the
        TICKETS table alone contains approximately **248 million rows**, all
        aggregations are pushed down to DB2 at data preparation time - Python only
        ever sees the summarised result. The prepared data is stored locally as
        Parquet files for fast, offline querying.
        """
    )

    st.divider()

    st.header("Schema Description")

    with st.expander("TICKETS  (~248 million rows)", expanded=True):
        st.markdown(
            """
            The central fact table. Each row represents one sold ticket.

            | Column | Type | Description |
            |--------|------|-------------|
            | `ROUTE_CODE` | VARCHAR | Foreign key to the ROUTES table |
            | `CLASS` | CHAR(1) | Cabin class: `E` Economy · `P` Premium · `B` Business |
            | `TOTAL_AMOUNT` | DECIMAL | Total ticket price (assumed USD) |
            | `AIRPORT_TAX` | DECIMAL | Airport tax charged on the ticket |
            | `LOCAL_TAX` | DECIMAL | Local/government tax charged on the ticket |
            | `DEPARTURE` | TIMESTAMP | Scheduled departure date and time |
            """
        )

    with st.expander("ROUTES"):
        st.markdown(
            """
            Dimension table describing each flight route.

            | Column | Type | Description |
            |--------|------|-------------|
            | `ROUTE_CODE` | VARCHAR | Primary key |
            | `ORIGIN` | CHAR(3) | Origin airport IATA code |
            | `DESTINATION` | CHAR(3) | Destination airport IATA code |
            | `DISTANCE` | DECIMAL | Route distance in kilometres |
            | `FLIGHT_MINUTES` | INTEGER | Scheduled flight duration |
            | `PARENT_ROUTE` | VARCHAR | Parent route for multi-leg journeys |
            | `LEG_NUMBER` | INTEGER | Leg sequence within a multi-leg journey |
            """
        )

    with st.expander("AIRPORTS"):
        st.markdown(
            """
            Dimension table with geographic details for each airport.

            | Column | Type | Description |
            |--------|------|-------------|
            | `IATA_CODE` | CHAR(3) | Primary key |
            | `AIRPORT` | VARCHAR | Full airport name |
            | `CITY` | VARCHAR | City the airport serves |
            | `COUNTRY` | VARCHAR | Country |
            | `CONTINENT` | VARCHAR | Continent |
            | `LATITUDE` | DECIMAL | Geographic latitude |
            | `LONGITUDE` | DECIMAL | Geographic longitude |
            | `AIRPORT_TAX` | DECIMAL | Standard airport tax rate |
            """
        )

    st.divider()

    st.header("Group Members")
    st.markdown(
        """
        - Jose Maria Brandao
        - Juan Camilo Lujan
        - Laurenz Jakob Kluth
        - Nicolas Beard
        - Stephan Pentchev
        """
    )

# ===========================================================================
# Tab 2 – Dashboard
# ===========================================================================

with page_dashboard:

    total_revenue, total_tickets, avg_ticket, active_routes = get_kpi_totals(
        class_filter
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Revenue",    f"${total_revenue:,.0f}")
    k2.metric("Total Tickets",    f"{total_tickets:,}")
    k3.metric("Avg Ticket Value", f"${avg_ticket:,.2f}")
    k4.metric("Active Routes",    f"{active_routes}")

    st.divider()

    # -----------------------------------------------------------------------
    # Section 1 – Revenue by Route & Class
    # -----------------------------------------------------------------------

    st.header("Revenue by Route & Cabin Class")
    st.markdown(
        "Top routes by total revenue alongside the revenue split by cabin class. "
        "Long-haul routes tend to dominate, but routes with a stronger Business-class "
        "mix can outperform higher-volume Economy routes."
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        df_top_routes = get_revenue_by_route(class_filter, continent_filter, top_n)
        fig_routes = px.bar(
            df_top_routes,
            x="revenue", y="route_label", orientation="h",
            title=f"Top {top_n} Routes by Total Revenue",
            labels={"revenue": "Revenue ($)", "route_label": "Route"},
            color="revenue", color_continuous_scale="Blues",
            hover_data={"ticket_count": True, "avg_ticket_value": ":.2f"},
        )
        fig_routes.update_layout(
            yaxis={"autorange": "reversed"}, coloraxis_showscale=False
        )
        st.plotly_chart(fig_routes, use_container_width=True)

    with col2:
        df_class = get_revenue_by_class(class_filter)
        fig_class = px.pie(
            df_class, values="revenue", names="cabin_class",
            title="Revenue Share by Cabin Class",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        st.plotly_chart(fig_class, use_container_width=True)

    st.divider()

    # -----------------------------------------------------------------------
    # Section 2 – Revenue by Continent
    # -----------------------------------------------------------------------

    st.header("Revenue by Origin Continent")
    st.markdown(
        "Revenue and ticket volume grouped by the continent the flight departs from. "
        "Comparing the two charts shows whether a continent's revenue share is driven "
        "by volume or by higher average ticket prices."
    )

    df_continent = get_revenue_by_continent(class_filter)
    col3, col4 = st.columns(2)

    with col3:
        fig_cont_rev = px.bar(
            df_continent,
            x="revenue", y="origin_continent", orientation="h",
            title="Revenue by Origin Continent",
            labels={"revenue": "Revenue ($)", "origin_continent": "Continent"},
            color="revenue", color_continuous_scale="Teal",
        )
        fig_cont_rev.update_layout(
            yaxis={"autorange": "reversed"}, coloraxis_showscale=False
        )
        st.plotly_chart(fig_cont_rev, use_container_width=True)

    with col4:
        fig_cont_tix = px.bar(
            df_continent,
            x="ticket_count", y="origin_continent", orientation="h",
            title="Ticket Volume by Origin Continent",
            labels={"ticket_count": "Tickets Sold", "origin_continent": "Continent"},
            color="ticket_count", color_continuous_scale="Teal",
        )
        fig_cont_tix.update_layout(
            yaxis={"autorange": "reversed"}, coloraxis_showscale=False
        )
        st.plotly_chart(fig_cont_tix, use_container_width=True)

    st.divider()

    # -----------------------------------------------------------------------
    # Section 3 – Revenue Over Time
    # -----------------------------------------------------------------------

    st.header("Revenue Over Time")
    st.markdown(
        "The top chart shows the overall monthly revenue trend. The stacked bar below "
        "breaks it down by cabin class so you can see how each class contributes "
        "month by month. Use the Year filter in the sidebar to zoom into a specific year."
    )

    df_trend = get_monthly_trend(class_filter, year_filter)
    fig_trend = px.line(
        df_trend, x="date", y="revenue",
        title="Monthly Revenue Trend (all selected classes)",
        labels={"date": "Month", "revenue": "Revenue ($)"},
        markers=True,
    )
    fig_trend.update_traces(line_color="#1f77b4")
    st.plotly_chart(fig_trend, use_container_width=True)

    df_by_class = get_monthly_by_class(class_filter, year_filter)
    fig_stacked = px.bar(
        df_by_class,
        x="date", y="revenue", color="cabin_class",
        barmode="stack",
        title="Monthly Revenue by Cabin Class (stacked)",
        labels={
            "date": "Month",
            "revenue": "Revenue ($)",
            "cabin_class": "Class",
        },
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    st.plotly_chart(fig_stacked, use_container_width=True)

    st.divider()

    # -----------------------------------------------------------------------
    # Section 4 – Route Efficiency
    # -----------------------------------------------------------------------

    st.header("Route Efficiency – Revenue per km")
    st.markdown(
        "Revenue divided by route distance reveals which routes earn the most per "
        "kilometre flown. Short routes with strong demand or premium pricing can "
        "outperform long-haul routes on this metric even if their total revenue is lower."
    )

    df_efficiency = get_route_efficiency(class_filter, continent_filter, top_n)
    fig_efficiency = px.bar(
        df_efficiency,
        x="revenue_per_km", y="route_label", orientation="h",
        title=f"Top {top_n} Routes by Revenue per km",
        labels={
            "revenue_per_km": "Revenue per km ($/km)",
            "route_label": "Route",
        },
        color="revenue_per_km", color_continuous_scale="Oranges",
        hover_data={"revenue": ":,.0f", "distance": True, "ticket_count": True},
    )
    fig_efficiency.update_layout(
        yaxis={"autorange": "reversed"}, coloraxis_showscale=False
    )
    st.plotly_chart(fig_efficiency, use_container_width=True)

    st.divider()

    # -----------------------------------------------------------------------
    # Data preview & download
    # -----------------------------------------------------------------------

    st.header("Data Preview")

    tab1, tab2 = st.tabs(["Top Routes", "Monthly Trend"])

    with tab1:
        st.dataframe(df_top_routes.drop("route_label"), use_container_width=True)
        st.download_button(
            "Download CSV",
            df_top_routes.to_pandas().to_csv(index=False),
            "top_routes.csv", "text/csv",
        )

    with tab2:
        st.dataframe(df_trend, use_container_width=True)
        st.download_button(
            "Download CSV",
            df_trend.to_pandas().to_csv(index=False),
            "monthly_trend.csv", "text/csv",
        )

    st.caption("Source: ATTPLANE DB2 · Schema: ATTGRP4 · Built with Polars + Streamlit")

# ===========================================================================
# Tab 3 – Conclusions & Future Work
# ===========================================================================

with page_conclusions:

    st.header("Key Findings")

    st.subheader("Seasonality")
    st.markdown(
        "Revenue follows a clear seasonal pattern across all years in the dataset. "
        "**November and April** are consistently the lowest-revenue months, while "
        "**August and January** peak - matching the major holiday travel periods "
        "(summer vacations and the Christmas/New Year season). "
        "Airlines can leverage this to plan capacity and dynamic pricing well in advance."
    )

    st.subheader("Revenue by Cabin Class")
    st.markdown(
        "**Economy class drives ~77% of total revenue**, despite having a much lower "
        "average ticket price than Business or Premium. Premium class accounts for less "
        "than 5% of revenue - suggesting it is either a niche offering or not heavily "
        "marketed on these routes. Business class punches above its weight in average "
        "ticket value but is constrained by volume."
    )

    st.subheader("Top Routes")
    st.markdown(
        "The 8 highest-revenue routes are all **long-haul intercontinental connections**:\n"
        "- Naples ↔ Las Vegas\n"
        "- Tokyo ↔ Rome\n"
        "- Hong Kong ↔ Manchester\n"
        "- Lille ↔ Tokyo\n\n"
        "Tokyo appears in two of the four route pairs, making it the single most "
        "commercially important hub in the network by revenue. Volume alone does not "
        "explain the rankings - these routes also carry a higher mix of Business-class "
        "tickets, which inflates total revenue per route."
    )

    st.subheader("Revenue Trend Over Time")
    st.markdown(
        "The monthly trend chart shows **no clear upward or downward trend** over the "
        "full period in the dataset. Revenue is stable year-over-year, with variation "
        "driven primarily by seasonality rather than network growth or decline."
    )

    st.subheader("Route Efficiency")
    st.markdown(
        "When normalised by distance, **shorter routes with premium demand** can "
        "outperform many long-haul routes on revenue per km. This suggests that "
        "not all high-volume long-haul routes are equally profitable on a per-km basis, "
        "and that medium-haul routes with strong pricing power can be highly efficient."
    )

    st.divider()

    st.header("Assumptions")
    st.markdown(
        "- **CLASS codes** are interpreted as: `E` = Economy, `P` = Premium, "
        "`B` = Business. These are not documented in the schema but are consistent "
        "with standard airline conventions.\n"
        "- All monetary amounts (`TOTAL_AMOUNT`, `AIRPORT_TAX`, `LOCAL_TAX`) are "
        "assumed to be in **USD**. No currency column exists in the schema.\n"
        "- `ROUTE_CODE` is treated as a unique identifier for a city-pair connection. "
        "Routes with the same origin/destination but different codes are counted "
        "separately.\n"
        "- The `DEPARTURE` timestamp is used for all time-based aggregations. "
        "Arrival date is not used.\n"
        "- Missing or null `CONTINENT` values are excluded from continent-level "
        "filtering but are still included in overall totals."
    )

    st.divider()

    st.header("Limitations")
    st.markdown(
        "- **All ticket aggregations run entirely inside DB2.** The TICKETS table has "
        "~248 million rows, making a full extract impractical. Any analysis requiring "
        "row-level data (e.g. individual passenger segmentation) is not supported.\n"
        "- **Parquet files must be regenerated** by running `prepare_data.py` if the "
        "source data in DB2 changes. The dashboard does not query the database live.\n"
        "- **No load factor or seat capacity data** is available, so it is not possible "
        "to distinguish between a high-revenue route driven by high prices vs. one "
        "driven purely by volume.\n"
        "- The dashboard does not account for **cancellations or refunds** - all "
        "TICKETS records are treated as completed, revenue-generating trips.\n"
        "- **Route efficiency** uses straight-line route distance, not actual flown "
        "distance, which can differ for routes with intermediate stops."
    )

    st.divider()

    st.header("What Would Be Interesting to Explore in the Future")
    st.markdown(
        "- **Load factor analysis**: If seat capacity data were available, computing "
        "revenue per available seat-km (RASK) would give a much more precise picture "
        "of route profitability - the industry standard metric.\n"
        "- **Route network map**: Plotting origin-destination pairs on a world map "
        "with arc thickness proportional to revenue would make the network structure "
        "immediately intuitive and visually compelling.\n"
        "- **Passenger segmentation**: With row-level ticket data it would be possible "
        "to analyse booking lead times, repeat customers, and origin-country of "
        "passengers - useful for targeted marketing.\n"
        "- **Price elasticity**: Combining ticket prices with booking volumes over time "
        "could reveal how sensitive demand is to price changes on key routes.\n"
        "- **Revenue forecasting**: A time-series model (e.g. SARIMA or Prophet) "
        "trained on the monthly trend data could provide revenue forecasts and quantify "
        "the seasonal effect with confidence intervals.\n"
        "- **Tax burden analysis**: The dataset includes `AIRPORT_TAX` and `LOCAL_TAX` "
        "per ticket. Analysing the effective tax burden by route or country could "
        "inform network expansion and pricing strategy."
    )
