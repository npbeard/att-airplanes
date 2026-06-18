import polars as pl
import plotly.express as px
import plotly.graph_objects as go
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

# top N routes by revenue, filtered by class and continent
@st.cache_data
def get_revenue_by_route(class_filter: tuple, continent_filter: tuple, top_n: int) -> pl.DataFrame:
    return an.revenue_by_route(list(class_filter), list(continent_filter), top_n)

# revenue split by cabin class (for the donut chart)
@st.cache_data
def get_revenue_by_class(class_filter: tuple) -> pl.DataFrame:
    return an.revenue_by_class(list(class_filter))

# monthly revenue aggregated by year/month (for the trend line)
@st.cache_data
def get_monthly_trend(class_filter: tuple, year_filter: int | None) -> pl.DataFrame:
    return an.monthly_trend(list(class_filter), year_filter)

# revenue by origin and destination region pair
@st.cache_data
def get_regional_revenue(class_filter: tuple, continent_filter: tuple) -> pl.DataFrame:
    return an.regional_revenue(list(class_filter), list(continent_filter))

# unique continent names for the sidebar filter dropdown
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

# unique years available in the data for the year filter
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

# overall KPI numbers shown at the top of the dashboard
@st.cache_data
def get_kpi_totals(class_filter: tuple) -> tuple[float, int, float, int]:
    df = (
        pl.scan_parquet("data/revenue_by_route_class.parquet")
        .filter(pl.col("class").is_in(list(class_filter)))
        .select([
            pl.col("revenue").cast(pl.Float64).alias("revenue"),
            "ticket_count",
            "route_code",
        ])
        .collect()
    )
    total_revenue = float(df["revenue"].sum())
    total_tickets = int(df["ticket_count"].sum())
    avg_ticket = total_revenue / total_tickets if total_tickets > 0 else 0.0
    active_routes = df["route_code"].n_unique()
    return total_revenue, total_tickets, avg_ticket, active_routes


def trim_number(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".")


def format_compact_number(value: float | int, prefix: str = "", decimals: int = 1) -> str:
    value = float(value or 0)
    sign = "-" if value < 0 else ""
    abs_value = abs(value)

    if abs_value >= 1_000_000_000:
        return f"{sign}{prefix}{trim_number(abs_value / 1_000_000_000, decimals)}B"
    if abs_value >= 1_000_000:
        return f"{sign}{prefix}{trim_number(abs_value / 1_000_000, decimals)}M"
    if abs_value >= 1_000:
        return f"{sign}{prefix}{trim_number(abs_value / 1_000, decimals)}K"
    return f"{sign}{prefix}{abs_value:,.0f}"


def format_compact_money(value: float | int) -> str:
    return format_compact_number(value, prefix="$")


def format_markdown_money(value: float | int) -> str:
    return format_compact_money(value).replace("$", "\\$")


def add_display_labels(df: pl.DataFrame) -> pl.DataFrame:
    expressions = []
    if "revenue" in df.columns:
        expressions.append(
            pl.col("revenue")
            .map_elements(format_compact_money, return_dtype=pl.String)
            .alias("revenue_label")
        )
    if "ticket_count" in df.columns:
        expressions.append(
            pl.col("ticket_count")
            .map_elements(format_compact_number, return_dtype=pl.String)
            .alias("ticket_count_label")
        )
    if "avg_ticket_value" in df.columns:
        expressions.append(
            pl.col("avg_ticket_value")
            .map_elements(format_compact_money, return_dtype=pl.String)
            .alias("avg_ticket_value_label")
        )
    if "route_count" in df.columns:
        expressions.append(
            pl.col("route_count")
            .map_elements(format_compact_number, return_dtype=pl.String)
            .alias("route_count_label")
        )

    return df.with_columns(expressions) if expressions else df


def build_region_heatmap(df_regions: pl.DataFrame) -> go.Figure:
    origin_regions = df_regions["origin_continent"].unique().sort().to_list()
    dest_regions = df_regions["dest_continent"].unique().sort().to_list()
    region_lookup = {
        (row["origin_continent"], row["dest_continent"]): row
        for row in df_regions.to_dicts()
    }

    z_values = []
    text_values = []
    for origin in origin_regions:
        z_row = []
        text_row = []
        for dest in dest_regions:
            row = region_lookup.get((origin, dest))
            revenue = float(row["revenue"]) if row else 0.0
            z_row.append(revenue)
            text_row.append(format_compact_money(revenue))
        z_values.append(z_row)
        text_values.append(text_row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=dest_regions,
            y=origin_regions,
            text=text_values,
            texttemplate="%{text}",
            colorscale="Blues",
            hovertemplate=(
                "Origin: %{y}<br>"
                "Destination: %{x}<br>"
                "Revenue: %{text}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title="Revenue by Origin and Destination Region",
        xaxis_title="Destination Region",
        yaxis_title="Origin Region",
        coloraxis_showscale=False,
    )
    return fig


def format_month(row: dict) -> str:
    return f"{int(row['year'])}-{int(row['month']):02d}"


def describe_revenue_trend(df_trend: pl.DataFrame) -> str:
    first_month = df_trend.head(1).row(0, named=True)
    last_month = df_trend.tail(1).row(0, named=True)
    first_revenue = float(first_month["revenue"])
    last_revenue = float(last_month["revenue"])

    if first_revenue == 0:
        return "the trend cannot be compared because the first month has no revenue"

    pct_change = (last_revenue - first_revenue) / first_revenue
    if abs(pct_change) < 0.03:
        direction = "remained broadly stable"
    elif pct_change > 0:
        direction = "increased"
    else:
        direction = "decreased"

    return (
        f"revenue {direction} from {format_month(first_month)} to {format_month(last_month)} "
        f"({pct_change:+.1%})"
    )


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

# multiselect for cabin class — defaults to all three selected
selected_class_labels = st.sidebar.multiselect(
    "Cabin class",
    options=list(CLASS_OPTIONS.keys()),
    default=list(CLASS_OPTIONS.keys()),
)
# fall back to all classes if user deselects everything
class_filter = tuple(CLASS_OPTIONS[l] for l in selected_class_labels) or tuple(CLASS_OPTIONS.values())

# multiselect for origin continent — populated dynamically from the data
all_continents = get_continents()
selected_continents = st.sidebar.multiselect(
    "Origin continent", options=all_continents, default=all_continents
)
continent_filter = tuple(selected_continents) or tuple(all_continents)

# year filter only affects the trend chart, not the route or class charts
all_years = get_years()
selected_year = st.sidebar.selectbox("Year (trend chart)", options=["All"] + [str(y) for y in all_years])
year_filter = int(selected_year) if selected_year != "All" else None

# slider to control how many routes appear in the bar chart
top_n = st.sidebar.slider("Top N routes", min_value=5, max_value=30, value=15)

st.sidebar.markdown("---")
st.sidebar.caption("Data: ATTPLANE DB2 · Schema: ATTGRP4")

# ---------------------------------------------------------------------------
# Header + KPIs
# ---------------------------------------------------------------------------

st.title("✈️ ATT Airlines – Revenue Performance Dashboard")
st.caption(
    "Analyzing which routes, cabin classes, and departure periods generate the most revenue. "
    "Data source: ATTPLANE DB2 · Schema: ATTGRP4."
)

total_revenue, total_tickets, avg_ticket, active_routes = get_kpi_totals(class_filter)

# four summary metrics at the top — update automatically with the class filter
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Revenue",    format_compact_money(total_revenue))
k2.metric("Total Tickets",    format_compact_number(total_tickets))
k3.metric("Avg Ticket Value", format_compact_money(avg_ticket))
k4.metric("Active Routes",    format_compact_number(active_routes))

st.divider()

# ---------------------------------------------------------------------------
# Section 1 – Revenue by Route
# ---------------------------------------------------------------------------

st.header("Revenue by Route")
st.markdown(
    "The chart below shows the top routes ranked by total revenue. "
    "Routes with high ticket volumes tend to dominate, but some shorter routes "
    "with premium pricing also appear near the top."
)

# two columns: bar chart on the left (wider), donut chart on the right
col1, col2 = st.columns([2, 1])

with col1:
    df_top_routes = add_display_labels(get_revenue_by_route(class_filter, continent_filter, top_n))
    fig_routes = px.bar(
        df_top_routes,
        x="revenue", y="route_label", orientation="h",
        title=f"Top {top_n} Routes by Total Revenue",
        labels={"revenue": "Revenue ($)", "route_label": "Route"},
        color="revenue", color_continuous_scale="Blues",
        text="revenue_label",
        custom_data=["revenue_label", "ticket_count_label", "avg_ticket_value_label"],
        hover_data={"ticket_count": True, "avg_ticket_value": ":.2f"},
    )
    # reversed so the highest revenue route appears at the top
    fig_routes.update_layout(yaxis={"autorange": "reversed"}, coloraxis_showscale=False)
    fig_routes.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "Route: %{y}<br>"
            "Revenue: %{customdata[0]}<br>"
            "Tickets: %{customdata[1]}<br>"
            "Avg ticket: %{customdata[2]}<extra></extra>"
        ),
    )
    fig_routes.update_xaxes(tickprefix="$", tickformat=".2s")
    st.plotly_chart(fig_routes, use_container_width=True)

with col2:
    df_class = add_display_labels(get_revenue_by_class(class_filter))
    # hole=0.45 makes it a donut instead of a full pie
    fig_class = px.pie(
        df_class, values="revenue", names="cabin_class",
        title="Revenue Share by Cabin Class",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Set2,
        custom_data=["revenue_label", "ticket_count_label"],
    )
    fig_class.update_traces(
        textinfo="label+percent",
        hovertemplate=(
            "%{label}<br>"
            "Revenue: %{customdata[0]}<br>"
            "Tickets: %{customdata[1]}<extra></extra>"
        ),
    )
    st.plotly_chart(fig_class, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Section 2 – Regional Revenue
# ---------------------------------------------------------------------------

st.header("Regional Revenue")
st.markdown(
    "This view compares where revenue originates and which origin-destination region pairs "
    "generate the strongest network performance."
)

df_regions = add_display_labels(get_regional_revenue(class_filter, continent_filter))

if df_regions.is_empty():
    df_origin_regions = pl.DataFrame()
    st.info("No regional revenue is available for the current filters.")
else:
    df_origin_regions = (
        df_regions.group_by("origin_continent")
        .agg(
            pl.col("ticket_count").sum(),
            pl.col("revenue").sum(),
            pl.col("route_count").sum(),
        )
        .with_columns(
            (pl.col("revenue") / pl.col("ticket_count")).alias("avg_ticket_value"),
            (pl.col("revenue") / pl.col("revenue").sum()).alias("revenue_share"),
        )
        .sort("revenue", descending=True)
    )
    df_origin_regions = add_display_labels(df_origin_regions)

    region_col1, region_col2 = st.columns([1, 1])

    with region_col1:
        fig_origin_regions = px.bar(
            df_origin_regions,
            x="revenue", y="origin_continent", orientation="h",
            title="Revenue by Origin Region",
            labels={"revenue": "Revenue ($)", "origin_continent": "Origin Region"},
            color="revenue", color_continuous_scale="Greens",
            text="revenue_label",
            custom_data=["revenue_label", "ticket_count_label", "route_count_label"],
        )
        fig_origin_regions.update_layout(
            yaxis={"autorange": "reversed"},
            coloraxis_showscale=False,
        )
        fig_origin_regions.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate=(
                "Origin region: %{y}<br>"
                "Revenue: %{customdata[0]}<br>"
                "Tickets: %{customdata[1]}<br>"
                "Routes: %{customdata[2]}<extra></extra>"
            ),
        )
        fig_origin_regions.update_xaxes(tickprefix="$", tickformat=".2s")
        st.plotly_chart(fig_origin_regions, use_container_width=True)

    with region_col2:
        st.plotly_chart(build_region_heatmap(df_regions), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Section 3 – Revenue Over Time
# ---------------------------------------------------------------------------

st.header("Revenue Over Time")
st.markdown(
    "Monthly revenue trend across all selected cabin classes. "
    "Use the Year filter in the sidebar to focus on a specific year and detect seasonal patterns."
)

df_trend = add_display_labels(get_monthly_trend(class_filter, year_filter))
fig_trend = px.line(
    df_trend, x="date", y="revenue",
    title="Monthly Revenue Trend",
    labels={"date": "Month", "revenue": "Revenue ($)"},
    markers=True,
    custom_data=["revenue_label", "ticket_count_label"],
)
fig_trend.update_traces(
    line_color="#1f77b4",
    hovertemplate=(
        "Month: %{x|%Y-%m}<br>"
        "Revenue: %{customdata[0]}<br>"
        "Tickets: %{customdata[1]}<extra></extra>"
    ),
)
fig_trend.update_yaxes(tickprefix="$", tickformat=".2s")
st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Section 4 – Conclusion
# ---------------------------------------------------------------------------

st.header("Conclusion")

if df_top_routes.is_empty() or df_class.is_empty() or df_trend.is_empty() or df_regions.is_empty():
    st.info("No conclusion is available for the current filters because one or more charts have no data.")
else:
    top_route = df_top_routes.row(0, named=True)
    top_class = df_class.row(0, named=True)
    top_origin_region = df_origin_regions.row(0, named=True)
    top_region_pair = df_regions.row(0, named=True)
    class_revenue_total = float(df_class["revenue"].sum())
    regional_revenue_total = float(df_regions["revenue"].sum())
    top_class_share = float(top_class["revenue"]) / class_revenue_total if class_revenue_total else 0.0
    top_origin_share = (
        float(top_origin_region["revenue"]) / regional_revenue_total
        if regional_revenue_total
        else 0.0
    )
    top_region_pair_share = (
        float(top_region_pair["revenue"]) / regional_revenue_total
        if regional_revenue_total
        else 0.0
    )

    peak_month = df_trend.sort("revenue", descending=True).row(0, named=True)
    low_month = df_trend.sort("revenue").row(0, named=True)
    trend_summary = describe_revenue_trend(df_trend)

    st.markdown(
        f"Based on the selected filters, ATT Airlines' revenue is concentrated in a small set of "
        f"high-performing routes, led by **{top_route['route_label']}** with "
        f"**{format_markdown_money(top_route['revenue'])}** in revenue. The strongest cabin class is "
        f"**{top_class['cabin_class']}**, contributing **{top_class_share:.1%}** of filtered cabin "
        "revenue, which shows that pricing and seat mix are central to the network's performance."
        "\n\n"
        f"Regionally, **{top_origin_region['origin_continent']}** is the strongest origin region, "
        f"generating **{format_markdown_money(top_origin_region['revenue'])}** "
        f"(**{top_origin_share:.1%}** of filtered regional revenue). The strongest region pair is "
        f"**{top_region_pair['region_pair']}**, with "
        f"**{format_markdown_money(top_region_pair['revenue'])}** "
        f"(**{top_region_pair_share:.1%}** of filtered regional revenue), so regional demand is "
        "not evenly distributed across the network."
        "\n\n"
        f"The time-series view shows that **{format_month(peak_month)}** was the highest-revenue "
        f"month and **{format_month(low_month)}** was the lowest-revenue month. Overall, "
        f"**{trend_summary}**. This suggests the main opportunity is to protect the top-performing "
        "routes and regions while investigating seasonal demand swings and using cabin-class pricing "
        "to improve weaker months."
    )

st.divider()

# ---------------------------------------------------------------------------
# Data preview & download
# ---------------------------------------------------------------------------

st.header("Data Preview")

# tabs let the user switch between the two datasets without cluttering the page
tab1, tab2, tab3 = st.tabs(["Top Routes", "Monthly Trend", "Regions"])

with tab1:
    # drop route_label since it's only used for chart display
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

with tab3:
    st.dataframe(df_regions, use_container_width=True)
    st.download_button(
        "Download CSV",
        df_regions.to_pandas().to_csv(index=False),
        "regional_revenue.csv", "text/csv",
    )

st.caption("Source: ATTPLANE DB2 · Schema: ATTGRP4 · Built with Polars + Streamlit")
