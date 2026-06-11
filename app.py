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
# Each function is decorated with @st.cache_data so results are stored in
# memory and reused across reruns as long as the arguments don't change.
# Tuples are used instead of lists because @st.cache_data requires hashable args.
# ---------------------------------------------------------------------------

@st.cache_data
def get_revenue_by_route(class_filter: tuple, continent_filter: tuple, top_n: int) -> pl.DataFrame:
    return an.revenue_by_route(list(class_filter), list(continent_filter), top_n)

@st.cache_data
def get_revenue_by_class(class_filter: tuple) -> pl.DataFrame:
    return an.revenue_by_class(list(class_filter))

@st.cache_data
def get_monthly_trend(class_filter: tuple, year_filter: int | None) -> pl.DataFrame:
    return an.monthly_trend(list(class_filter), year_filter)

@st.cache_data
def get_route_efficiency(class_filter: tuple, continent_filter: tuple) -> pl.DataFrame:
    return an.route_efficiency(list(class_filter), list(continent_filter))

@st.cache_data
def get_fleet_by_model() -> pl.DataFrame:
    return an.fleet_by_model()

@st.cache_data
def get_fleet_age_maintenance() -> pl.DataFrame:
    return an.fleet_age_maintenance()

@st.cache_data
def get_top_countries(top_n: int) -> pl.DataFrame:
    return an.top_passenger_countries(top_n)

@st.cache_data
def get_vip_comparison() -> pl.DataFrame:
    return an.vip_comparison()

@st.cache_data
def get_cabin_preference() -> pl.DataFrame:
    return an.cabin_preference_by_segment()

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


# ---------------------------------------------------------------------------
# Guard: parquet files must exist before rendering
# ---------------------------------------------------------------------------

try:
    get_continents()
except FileNotFoundError:
    st.error("Parquet files not found. Run `python prepare_data.py` first.")
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
class_filter = tuple(CLASS_OPTIONS[l] for l in selected_class_labels) or tuple(CLASS_OPTIONS.values())

all_continents = get_continents()
selected_continents = st.sidebar.multiselect(
    "Origin continent", options=all_continents, default=all_continents
)
continent_filter = tuple(selected_continents) or tuple(all_continents)

all_years = get_years()
selected_year = st.sidebar.selectbox("Year (trend chart)", options=["All"] + [str(y) for y in all_years])
year_filter = int(selected_year) if selected_year != "All" else None

top_n = st.sidebar.slider("Top N routes", min_value=5, max_value=30, value=15)

st.sidebar.markdown("---")
st.sidebar.caption("Data: ATTPLANE DB2 · Schema: ATTGRP4")

# ---------------------------------------------------------------------------
# Header + KPIs
# ---------------------------------------------------------------------------

st.title("✈️ ATT Airlines – Operations Dashboard")
st.caption("Revenue performance, route efficiency, fleet utilization, and passenger segments.")

total_revenue, total_tickets, avg_ticket, active_routes = get_kpi_totals(class_filter)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Revenue",    f"${total_revenue:,.0f}")
k2.metric("Total Tickets",    f"{total_tickets:,}")
k3.metric("Avg Ticket Value", f"${avg_ticket:,.2f}")
k4.metric("Active Routes",    f"{active_routes}")

st.divider()

# ---------------------------------------------------------------------------
# Section 1 – Revenue Performance
# ---------------------------------------------------------------------------

st.header("1. Revenue Performance")
st.markdown("Which routes, cabin classes, and departure periods generate the most revenue?")

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
    fig_routes.update_layout(yaxis={"autorange": "reversed"}, coloraxis_showscale=False)
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
# Section 2 – Route Efficiency
# ---------------------------------------------------------------------------

st.header("2. Route Efficiency")
st.markdown(
    "Which routes yield the highest revenue per kilometer? "
    "How does route distance relate to average ticket value?"
)

df_eff = get_route_efficiency(class_filter, continent_filter)

col3, col4 = st.columns(2)

with col3:
    fig_scatter = px.scatter(
        df_eff,
        x="distance", y="avg_ticket_value",
        size="ticket_count", color="origin_continent",
        hover_data={"route_label": True, "revenue": ":,.0f", "ticket_count": ":,"},
        title="Route Distance vs Average Ticket Value",
        labels={
            "distance": "Distance (km)",
            "avg_ticket_value": "Avg Ticket Value ($)",
            "origin_continent": "Continent",
        },
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

with col4:
    df_rev_km = df_eff.sort("revenue_per_km", descending=True).head(15)
    fig_rev_km = px.bar(
        df_rev_km,
        x="revenue_per_km", y="route_label", orientation="h",
        title="Top 15 Routes by Revenue per km",
        labels={"revenue_per_km": "Revenue per km ($)", "route_label": "Route"},
        color="revenue_per_km", color_continuous_scale="Greens",
    )
    fig_rev_km.update_layout(yaxis={"autorange": "reversed"}, coloraxis_showscale=False)
    st.plotly_chart(fig_rev_km, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Section 3 – Fleet Utilization
# ---------------------------------------------------------------------------

st.header("3. Fleet Utilization")
st.markdown(
    "How is the fleet being used? "
    "Which models are most scheduled and which aircraft show maintenance risk?"
)

df_model = get_fleet_by_model()
df_age   = get_fleet_age_maintenance()

col5, col6 = st.columns(2)

with col5:
    fig_fleet = px.bar(
        df_model,
        x="model", y="scheduled_flights",
        title="Scheduled Flights by Aircraft Model",
        labels={"model": "Aircraft Model", "scheduled_flights": "Scheduled Flights"},
        color="scheduled_flights", color_continuous_scale="Purples",
        hover_data={"aircraft_count": True, "avg_seats": True, "avg_fuel_gph": True},
    )
    fig_fleet.update_layout(xaxis_tickangle=-35, coloraxis_showscale=False)
    st.plotly_chart(fig_fleet, use_container_width=True)

with col6:
    fig_maint = px.scatter(
        df_age,
        x="age_years", y="maintenance_flight_hours",
        color="model", size="total_seats",
        hover_data=["aircraft_registration", "maintenance_takeoffs", "total_flight_distance"],
        title="Aircraft Age vs Maintenance Flight Hours",
        labels={
            "age_years": "Aircraft Age (years)",
            "maintenance_flight_hours": "Maintenance Flight Hours",
            "model": "Model",
        },
    )
    st.plotly_chart(fig_maint, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Section 4 – Passenger Segments
# ---------------------------------------------------------------------------

st.header("4. Passenger Segments")
st.markdown(
    "Which countries and customer segments drive the most revenue? "
    "How do VIP and regular passengers differ?"
)

col7, col8 = st.columns(2)

with col7:
    df_countries = get_top_countries(15)
    fig_geo = px.bar(
        df_countries,
        x="revenue", y="country", orientation="h",
        title="Top 15 Passenger Countries by Revenue",
        labels={"revenue": "Revenue ($)", "country": "Country"},
        color="revenue", color_continuous_scale="Oranges",
        hover_data={"ticket_count": ":,", "passenger_count": ":,"},
    )
    fig_geo.update_layout(yaxis={"autorange": "reversed"}, coloraxis_showscale=False)
    st.plotly_chart(fig_geo, use_container_width=True)

with col8:
    df_vip = get_vip_comparison()
    fig_vip = px.bar(
        df_vip,
        x="vip_status", y="revenue",
        title="VIP vs Regular Passenger Revenue",
        color="vip_status",
        labels={"vip_status": "Passenger Type", "revenue": "Revenue ($)"},
        color_discrete_sequence=["#636EFA", "#EF553B"],
        text_auto=".3s",
    )
    fig_vip.update_layout(showlegend=False)
    st.plotly_chart(fig_vip, use_container_width=True)

df_cabin_pref = get_cabin_preference()
fig_pref = px.bar(
    df_cabin_pref,
    x="cabin_class", y="revenue", color="vip_status",
    barmode="group",
    title="Cabin Class Revenue by Passenger Segment",
    labels={"cabin_class": "Cabin Class", "revenue": "Revenue ($)", "vip_status": "Segment"},
    color_discrete_sequence=["#636EFA", "#EF553B"],
    category_orders={"cabin_class": an.CLASS_ORDER},
)
st.plotly_chart(fig_pref, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Data preview & download
# ---------------------------------------------------------------------------

st.header("Data Preview")

tab1, tab2, tab3, tab4 = st.tabs(["Top Routes", "Monthly Trend", "Fleet", "Passengers"])

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

with tab3:
    st.dataframe(df_model, use_container_width=True)

with tab4:
    st.dataframe(get_top_countries(30), use_container_width=True)

st.caption("Source: ATTPLANE DB2 · Schema: ATTGRP4 · Built with Polars + Streamlit")
