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
        .select(["revenue", "ticket_count", "route_code"])
        .collect()
    )
    total_revenue = df["revenue"].sum()
    total_tickets = int(df["ticket_count"].sum())
    avg_ticket = total_revenue / total_tickets if total_tickets > 0 else 0.0
    active_routes = df["route_code"].n_unique()
    return total_revenue, total_tickets, avg_ticket, active_routes


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
k1.metric("Total Revenue",    f"${total_revenue:,.0f}")
k2.metric("Total Tickets",    f"{total_tickets:,}")
k3.metric("Avg Ticket Value", f"${avg_ticket:,.2f}")
k4.metric("Active Routes",    f"{active_routes}")

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
    df_top_routes = get_revenue_by_route(class_filter, continent_filter, top_n)
    fig_routes = px.bar(
        df_top_routes,
        x="revenue", y="route_label", orientation="h",
        title=f"Top {top_n} Routes by Total Revenue",
        labels={"revenue": "Revenue ($)", "route_label": "Route"},
        color="revenue", color_continuous_scale="Blues",
        hover_data={"ticket_count": True, "avg_ticket_value": ":.2f"},
    )
    # reversed so the highest revenue route appears at the top
    fig_routes.update_layout(yaxis={"autorange": "reversed"}, coloraxis_showscale=False)
    st.plotly_chart(fig_routes, use_container_width=True)

with col2:
    df_class = get_revenue_by_class(class_filter)
    # hole=0.45 makes it a donut instead of a full pie
    fig_class = px.pie(
        df_class, values="revenue", names="cabin_class",
        title="Revenue Share by Cabin Class",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    st.plotly_chart(fig_class, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Section 2 – Revenue Over Time
# ---------------------------------------------------------------------------

st.header("Revenue Over Time")
st.markdown(
    "Monthly revenue trend across all selected cabin classes. "
    "Use the Year filter in the sidebar to focus on a specific year and detect seasonal patterns."
)

df_trend = get_monthly_trend(class_filter, year_filter)
fig_trend = px.line(
    df_trend, x="date", y="revenue",
    title="Monthly Revenue Trend",
    labels={"date": "Month", "revenue": "Revenue ($)"},
    markers=True,
)
fig_trend.update_traces(line_color="#1f77b4")
st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Data preview & download
# ---------------------------------------------------------------------------

st.header("Data Preview")

# tabs let the user switch between the two datasets without cluttering the page
tab1, tab2 = st.tabs(["Top Routes", "Monthly Trend"])

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

st.caption("Source: ATTPLANE DB2 · Schema: ATTGRP4 · Built with Polars + Streamlit")
