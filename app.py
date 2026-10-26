"""Streamlit dashboard for customer lifecycle and segment analytics."""

# Dashboard dependencies and the shared data-processing functions.
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime
from pathlib import Path

from modules.segmentation import load_data, compute_customer_lifecycle


# Configure the page before creating any Streamlit elements.
st.set_page_config(
    page_title="Customer Lifecycle Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Resolve project assets relative to this file so the app works from any cwd.
PROJECT_DIR = Path(__file__).resolve().parent
css_path = PROJECT_DIR / "assets" / "styles.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


# The workbook is the dashboard's customer-level source of truth.
DATA_PATH = PROJECT_DIR / "data" / "clients_dataset.xlsx"


@st.cache_resource
def get_dataset(source_mtime_ns, source_size):
    """Share the parsed workbook without serializing copies into the cache."""
    return load_data(str(DATA_PATH))


# Include file metadata in the cache key so a replaced workbook is reloaded.
# Report actionable guidance for missing data, unreadable files, and LFS pointers.
try:
    source_stat = DATA_PATH.stat()
    df = get_dataset(source_stat.st_mtime_ns, source_stat.st_size)
except Exception as error:
    if not DATA_PATH.exists():
        load_guidance = f"Expected workbook at `{DATA_PATH}`."
    else:
        try:
            with DATA_PATH.open("rb") as workbook_file:
                is_lfs_pointer = workbook_file.read(100).startswith(b"version https://git-lfs.github.com/spec/v1")
        except OSError:
            is_lfs_pointer = False
        load_guidance = (
            "The file is an unhydrated Git LFS pointer. Run `git lfs pull` in the repository."
            if is_lfs_pointer
            else f"Workbook found at `{DATA_PATH}`, but could not be read."
        )
    st.error(
        "Could not load the customer workbook. "
        f"{load_guidance} Error: {error}"
    )
    st.stop()


# Prefer the workbook refresh date; older workbooks fall back to transaction data.
if "SnapshotDate" in df and df["SnapshotDate"].notna().any():
    AS_OF = df["SnapshotDate"].max()
else:
    AS_OF = df["TransactionDate"].max()
LIFECYCLE_ORDER = ["Active", "Inactive", "Dormant", "Churned", "Idle"]
LIFECYCLE_COLORS = {
    "Active": "#64D6A5",
    "Inactive": "#F2C66D",
    "Dormant": "#F08A63",
    "Churned": "#B86B79",
    "Idle": "#77837B",
}


def valid_date_bounds(series, fallback):
    """Return usable date limits, ignoring invalid and placeholder dates."""
    dates = pd.to_datetime(series, errors="coerce").dropna()
    dates = dates[dates.dt.year > 1900]
    if dates.empty:
        return fallback, fallback
    return dates.min().date(), dates.max().date()


def format_currency(value):
    """Format large totals with compact suffixes and smaller totals as dollars."""
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.2f}"


def chart_layout(fig, height=330):
    """Apply the dashboard's shared chart colors, typography, and spacing."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#26352C", family="DM Sans, sans-serif"),
        margin=dict(l=18, r=24, t=28, b=18),
        legend_title_text="",
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#435248"), title_font=dict(color="#26352C")),
        yaxis=dict(showgrid=True, gridcolor="rgba(29,41,34,0.10)", zeroline=False, tickfont=dict(color="#435248"), title_font=dict(color="#26352C")),
    )
    return fig


def add_customer_names(frame):
    """Expose an optional source name column under one dashboard column name."""
    result = frame.copy()
    name_column = next((column for column in ("CustomerName", "name", "Name") if column in result), None)
    if name_column and isinstance(result[name_column].dtype, pd.CategoricalDtype):
        result["Name"] = result[name_column].astype("string[pyarrow]").fillna("")
    else:
        result["Name"] = result[name_column].fillna("").astype(str) if name_column else ""
    return result


# Introduce the dashboard and show the workbook refresh time and row count.
st.markdown("# Customer Lifecycle")
st.markdown("Customer health, recency, retention opportunities, and segment performance")
st.caption(
    f"Source workbook refreshed {datetime.fromtimestamp(source_stat.st_mtime).strftime('%b %d, %Y %H:%M')} "
    f"· {len(df):,} records"
)

# Build sidebar options and date limits from the loaded workbook.
st.sidebar.header("Filters")
fallback_date = AS_OF.date()
first_min, first_max = valid_date_bounds(df["FirstTransaction"], fallback_date)
last_min, last_max = valid_date_bounds(df["LastTransaction"], fallback_date)
all_biz_segments = sorted(df["BizSegment"].dropna().unique().tolist())
selected_biz_segments = st.sidebar.multiselect(
    "Business segment",
    all_biz_segments,
    default=[],
    placeholder="All business segments",
    key="main_biz_segment_v2",
)

# Limit category choices to the selected business segment(s), and discard stale
# category widget values if a segment change makes them unavailable.
category_source = df[df["BizSegment"].isin(selected_biz_segments)] if selected_biz_segments else df
category_options = sorted(category_source["BusinessCategory"].dropna().unique().tolist())
if "main_business_category_v2" in st.session_state:
    st.session_state["main_business_category_v2"] = [
        value for value in st.session_state["main_business_category_v2"] if value in category_options
    ]
customer_type_options = sorted(df["CustomerType"].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect(
    "Business category",
    category_options,
    default=[],
    placeholder="All business categories",
    key="main_business_category_v2",
)
selected_types = st.sidebar.multiselect(
    "Customer segment",
    customer_type_options,
    default=[],
    placeholder="All customer segments",
    key="main_customer_type_v2",
)

first_date_range = st.sidebar.date_input(
    "First transaction date",
    value=(first_min, first_max),
    min_value=first_min,
    max_value=first_max,
    key="main_first_transaction_date",
)
last_date_range = st.sidebar.date_input(
    "Last transaction date",
    value=(last_min, last_max),
    min_value=last_min,
    max_value=last_max,
    key="main_last_transaction_date",
)

# Apply all selected filters while retaining records with missing transaction
# dates when the user filters by date.
filtered_df = df
if selected_biz_segments:
    filtered_df = filtered_df[filtered_df["BizSegment"].isin(selected_biz_segments)]
if selected_categories:
    filtered_df = filtered_df[filtered_df["BusinessCategory"].isin(selected_categories)]
if selected_types:
    filtered_df = filtered_df[filtered_df["CustomerType"].isin(selected_types)]

if len(first_date_range) == 2:
    first_start, first_end = map(pd.Timestamp, first_date_range)
    first_end += pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    filtered_df = filtered_df[
        filtered_df["FirstTransaction"].isna()
        | filtered_df["FirstTransaction"].between(first_start, first_end)
    ]
if len(last_date_range) == 2:
    last_start, last_end = map(pd.Timestamp, last_date_range)
    last_end += pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    filtered_df = filtered_df[
        filtered_df["LastTransaction"].isna()
        | filtered_df["LastTransaction"].between(last_start, last_end)
    ]

# Stop early rather than rendering misleading empty charts and totals.
if filtered_df.empty:
    st.info("No customer records match these filters. Adjust the selections above.")
    st.stop()

# Derive lifecycle fields once for the filtered customers and prepare display
# columns used by the metrics and tables below.
cust_df = compute_customer_lifecycle(filtered_df, snapshot_date=AS_OF)
cust_df = add_customer_names(cust_df)
cust_df["Tenure (years)"] = (cust_df["Tenure_Days"].clip(lower=0) / 365.25).round(1)
cust_df["As of"] = AS_OF.date()

# Summarize customer counts, transaction volume, and value for the selection.
st.markdown("### Customer totals")
active_mask = cust_df["Lifecycle_Status"].eq("Active")
total_revenue = cust_df["Total_Value"].sum()
total_volume = cust_df["Success_Count"].sum()
total_cards = st.columns(5)
total_cards[0].metric("All records", f"{len(cust_df):,}")
total_cards[1].metric("Active", f"{active_mask.sum():,}")
total_cards[2].metric("Not active", f"{(~active_mask).sum():,}")
total_cards[3].metric("Total volume", f"{total_volume:,.0f}")
total_cards[4].metric("Total value", format_currency(total_revenue))

# Count each lifecycle class and calculate its share of the filtered customers.
class_counts = cust_df["Lifecycle_Status"].value_counts().reindex(LIFECYCLE_ORDER, fill_value=0)
class_stats = pd.DataFrame(
    {
        "Lifecycle class": LIFECYCLE_ORDER,
        "Records": class_counts.values,
        "Share": (class_counts / max(len(cust_df), 1) * 100).reindex(LIFECYCLE_ORDER).values,
    }
)
class_stats["Count and share"] = class_stats.apply(
    lambda row: f"{row['Records']:,} ({row['Share']:.1f}%)", axis=1
)
st.subheader("Records by lifecycle class")
count_fig = px.bar(
    class_stats,
    x="Records",
    y="Lifecycle class",
    orientation="h",
    color="Lifecycle class",
    color_discrete_map=LIFECYCLE_COLORS,
    text="Count and share",
    category_orders={"Lifecycle class": list(reversed(LIFECYCLE_ORDER))},
)
count_fig.update_traces(
    textposition="outside",
    cliponaxis=False,
    textfont_color="#26352C",
    showlegend=False,
)
chart_layout(count_fig, 320).update_layout(
    xaxis_title="Customers",
    yaxis_title="",
    xaxis_range=[0, class_stats["Records"].max() * 1.28 if class_stats["Records"].max() else 1],
)
st.plotly_chart(count_fig, use_container_width=True)

# Compare the lifecycle distribution separately for each business segment.
st.subheader("Lifecycle mix by business segment")
segment_columns = st.columns(len(all_biz_segments))
for segment_column, business_segment in zip(segment_columns, all_biz_segments):
    segment_rows = cust_df[cust_df["BizSegment"].eq(business_segment)]
    segment_counts = (
        segment_rows["Lifecycle_Status"]
        .value_counts()
        .reindex(LIFECYCLE_ORDER, fill_value=0)
        .rename_axis("Lifecycle")
        .reset_index(name="Customers")
    )
    with segment_column:
        st.markdown(f"**{business_segment}** · {len(segment_rows):,} customers")
        segment_fig = px.pie(
            segment_counts,
            names="Lifecycle",
            values="Customers",
            hole=0.58,
            color="Lifecycle",
            color_discrete_map=LIFECYCLE_COLORS,
        )
        segment_fig.update_traces(
            texttemplate="%{percent:.1%}",
            textposition="inside",
            hovertemplate="%{label}<br>%{value:,} customers (%{percent:.1%})<extra></extra>",
            sort=False,
        )
        chart_layout(segment_fig, 310).update_layout(
            showlegend=True,
            legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center", font=dict(size=10)),
            margin=dict(l=4, r=4, t=8, b=32),
        )
        segment_fig.add_annotation(
            text=f"{len(segment_rows):,}<br><span style='font-size:10px'>customers</span>",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16, color="#26352C"),
        )
        st.plotly_chart(segment_fig, use_container_width=True)

# Show customer recency bands alongside acquisition-quarter cohort outcomes.
st.divider()
recency_col, trend_col = st.columns(2)
with recency_col:
    st.subheader("Customer recency")
    recency_days = cust_df["Days_Since_Last_Success"]
    # Use explicit bins so the chart includes empty ranges and missing dates.
    recency_bins = [-float("inf"), 30, 60, 90, 180, 365, float("inf")]
    recency_labels = ["0–30 days", "31–60 days", "61–90 days", "91–180 days", "181–365 days", "366+ days"]
    recency_order = recency_labels + ["No date"]
    recency_band = pd.cut(recency_days, bins=recency_bins, labels=recency_labels).astype("string").fillna("No date")
    recency_counts = recency_band.value_counts().reindex(recency_order, fill_value=0)
    recency_stats = recency_counts.rename_axis("Recency").reset_index(name="Customers")
    recency_fig = px.bar(recency_stats, x="Recency", y="Customers", text="Customers", color="Recency")
    recency_fig.update_traces(texttemplate="%{text:,}", textposition="outside", showlegend=False)
    chart_layout(recency_fig, 340).update_layout(xaxis_title="Days since last transaction", yaxis_title="Customers")
    st.plotly_chart(recency_fig, use_container_width=True)

with trend_col:
    st.subheader("1st Trans cohorts by Quarter-year")
    cohort_source = cust_df.dropna(subset=["FirstTransaction"]).copy()
    if cohort_source.empty:
        st.info("No customers with a valid first transaction date match these filters.")
    else:
        # Count unique acquisitions per quarter and current lifecycle outcomes
        # for those same customers.
        cohort_source["CohortQuarter"] = cohort_source["FirstTransaction"].dt.to_period("Q").dt.start_time
        cohort_source["CurrentlyActive"] = cohort_source["Lifecycle_Status"].eq("Active").astype(int)
        cohort_source["CurrentlyChurned"] = cohort_source["Lifecycle_Status"].eq("Churned").astype(int)
        cohort_monthly = (
            cohort_source.groupby("CohortQuarter", observed=True)
            .agg(
                Acquired=("CustomerID", "nunique"),
                ActiveNow=("CurrentlyActive", "sum"),
                ChurnedNow=("CurrentlyChurned", "sum"),
            )
            .reset_index()
        )
        cohort_long = cohort_monthly.melt(
            id_vars="CohortQuarter",
            var_name="Cohort status",
            value_name="Customers",
        )
        trend_colors = {
            "Acquired": "#4778A8",
            "ActiveNow": "#17845A",
            "ChurnedNow": "#D65B54",
        }
        trend_fig = px.line(
            cohort_long,
            x="CohortQuarter",
            y="Customers",
            color="Cohort status",
            markers=True,
            color_discrete_map=trend_colors,
        )
        trend_fig.update_traces(line=dict(width=2.5))
        chart_layout(trend_fig, 390).update_layout(
            xaxis_title="First transaction quarter",
            yaxis_title="Customers",
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                tickfont=dict(color="#435248"),
                title_font=dict(color="#26352C"),
                tickformat="Q%q<br>%Y",
                dtick="M6",
            ),
            hovermode="x unified",
            legend=dict(
                orientation="h",
                y=-0.3,
                x=0.5,
                xanchor="center",
                yanchor="top",
            ),
            margin=dict(l=18, r=24, t=28, b=72),
        )
        st.plotly_chart(trend_fig, use_container_width=True)
        st.caption("Acquired counts use each customer's first-transaction quarter. Active and churned lines show each cohort's current status as of the latest transaction date in the workbook.")

# Compare idle customers by acquisition year with churn by estimated churn year.
st.subheader("Idle and churned customers by year")
# Exclude never-transacted customers from the idle-by-year chart because they
# have no valid first-transaction year to group by.
idle_customers = cust_df[
    cust_df["Lifecycle_Status"].eq("Idle")
    & cust_df["Status"].ne("NEVER TRANSACTED")
].copy()
never_transacted_count = int(
    cust_df["Lifecycle_Status"].eq("Idle")
    .mul(cust_df["Status"].eq("NEVER TRANSACTED"))
    .sum()
)
idle_customers = idle_customers.dropna(subset=["FirstTransaction"])
idle_customers["Year"] = idle_customers["FirstTransaction"].dt.year
idle_by_year = idle_customers.groupby("Year", observed=True).size().rename("Idle").to_frame()

# Estimate a customer's churn year as one year after their last transaction.
churned_customers = cust_df[
    cust_df["Lifecycle_Status"].eq("Churned") & cust_df["LastTransaction"].notna()
].copy()
churned_customers["Year"] = (churned_customers["LastTransaction"] + pd.Timedelta(days=365)).dt.year
churn_by_year = churned_customers.groupby("Year", observed=True).size().rename("Churned").to_frame()

idle_chart_col, churn_chart_col = st.columns(2)
with idle_chart_col:
    st.markdown("**Idle by first-transaction year**")
    idle_annual = idle_by_year.sort_index().rename_axis("Year").reset_index()
    idle_fig = px.area(
        idle_annual,
        x="Year",
        y="Idle",
        color_discrete_sequence=["#E5A43A"],
    )
    idle_fig.update_traces(line=dict(width=2.5, color="#E5A43A"), fillcolor="rgba(229,164,58,0.22)")
    chart_layout(idle_fig, 360).update_layout(
        xaxis_title="Year",
        yaxis_title="Idle customers",
        xaxis=dict(tickmode="linear", dtick=1, tickformat="d"),
    )
    st.plotly_chart(idle_fig, use_container_width=True)
    st.metric("Never Transacted customers excluded from Idle series", f"{never_transacted_count:,}")

with churn_chart_col:
    st.markdown("**Churned by estimated churn year**")
    churn_annual = churn_by_year.sort_index().rename_axis("Year").reset_index()
    churn_fig = px.area(
        churn_annual,
        x="Year",
        y="Churned",
        color_discrete_sequence=["#D65B54"],
    )
    churn_fig.update_traces(line=dict(width=2.5, color="#D65B54"), fillcolor="rgba(214,91,84,0.20)")
    chart_layout(churn_fig, 360).update_layout(
        xaxis_title="Year",
        yaxis_title="Churned customers",
        xaxis=dict(tickmode="linear", dtick=1, tickformat="d"),
    )
    st.plotly_chart(churn_fig, use_container_width=True)

st.caption("Idle year counts exclude Never Transacted records, which have no first-transaction date. Churn year is estimated as 365 days after the last recorded transaction.")

# Count unique new customers by first-transaction quarter and business segment.
st.subheader("New clients by quarter and year")
new_clients = cust_df.dropna(subset=["FirstTransaction"]).copy()
if new_clients.empty:
    st.info("No customers with a valid first transaction date match these filters.")
else:
    new_clients["Quarter"] = new_clients["FirstTransaction"].dt.to_period("Q")
    new_client_counts = (
        new_clients.groupby(["Quarter", "BizSegment"], observed=True)["CustomerID"]
        .nunique()
        .reset_index(name="New clients")
    )
    new_client_counts["Quarter-year"] = new_client_counts["Quarter"].map(str)
    quarter_order = sorted(new_client_counts["Quarter"].unique())
    quarter_labels = [str(quarter) for quarter in quarter_order]
    business_segments = sorted(new_client_counts["BizSegment"].dropna().unique())
    # Reuse a stable palette when drawing one quarterly chart per segment.
    segment_colors = {segment: color for segment, color in zip(business_segments, ["#4778A8", "#17845A", "#E5A43A"])}
    for business_segment in business_segments:
        segment_counts = new_client_counts[new_client_counts["BizSegment"].eq(business_segment)]
        st.markdown(f"**{business_segment}**")
        new_clients_fig = px.bar(
            segment_counts,
            x="Quarter-year",
            y="New clients",
            text_auto=".2s",
            category_orders={"Quarter-year": quarter_labels},
            color_discrete_sequence=[segment_colors[business_segment]],
        )
        chart_layout(new_clients_fig, 380).update_layout(
            xaxis_title="Quarter-year",
            yaxis_title="New customers",
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                tickfont=dict(color="#435248"),
                title_font=dict(color="#26352C"),
                tickangle=-45,
                tickmode="array",
                tickvals=quarter_labels[::2],
                ticktext=quarter_labels[::2],
            ),
        )
        st.plotly_chart(new_clients_fig, use_container_width=True)

# List the longest-tenured active customers, ranking separately by segment.
st.divider()
st.markdown("### Longest active customers by business segment")
longest_active = cust_df[active_mask].sort_values(
    ["BizSegment", "Tenure_Days", "Total_Value"], ascending=[True, False, False]
).copy()
longest_active["Rank"] = longest_active.groupby("BizSegment").cumcount() + 1
longest_active = longest_active[longest_active["Rank"] <= 10]
longest_columns = [
    "Rank", "CustomerID", "Name", "BizSegment", "FirstTransaction", "LastTransaction",
    "Tenure (years)", "As of", "Success_Count", "Total_Value",
]
st.caption("Top 10 by tenure within each business segment.")
st.dataframe(
    longest_active[longest_columns].rename(
        columns={"Success_Count": "Total Volume", "Total_Value": "Total Value"}
    ),
    use_container_width=True,
    hide_index=True,
)

# Show value and volume leaders in separate tables, each ranked per segment.
value_col, volume_col = st.columns(2)
value_columns = [
    "Rank", "CustomerID", "Name", "BizSegment", "Success_Count", "Total_Value", "Lifecycle_Status"
]
with value_col:
    st.subheader("Top 5 customers by value · each business segment")
    top_value = cust_df.sort_values(["BizSegment", "Total_Value"], ascending=[True, False]).copy()
    top_value["Rank"] = top_value.groupby("BizSegment").cumcount() + 1
    top_value = top_value[top_value["Rank"] <= 5]
    st.dataframe(
        top_value[value_columns].rename(
            columns={"Success_Count": "Total Volume", "Total_Value": "Total Value", "Lifecycle_Status": "Lifecycle"}
        ),
        use_container_width=True,
        hide_index=True,
    )
with volume_col:
    st.subheader("Top 5 customers by volume · each business segment")
    top_volume = cust_df.sort_values(["BizSegment", "Success_Count"], ascending=[True, False]).copy()
    top_volume["Rank"] = top_volume.groupby("BizSegment").cumcount() + 1
    top_volume = top_volume[top_volume["Rank"] <= 5]
    st.dataframe(
        top_volume[value_columns].rename(
            columns={"Success_Count": "Total Volume", "Total_Value": "Total Value", "Lifecycle_Status": "Lifecycle"}
        ),
        use_container_width=True,
        hide_index=True,
    )

# Highlight the highest-value successful customers who are not currently active.
not_active = cust_df[
    ~active_mask & cust_df["Status"].eq("SUCCESS")
].nlargest(10, "Total_Value")
st.subheader("Top 10 customers who are not active")
st.dataframe(
    not_active[["CustomerID", "Name", "BizSegment", "Lifecycle_Status", "Days_Since_Last_Success", "Success_Count", "Total_Value", "LastTransaction"]].rename(
        columns={"Lifecycle_Status": "Lifecycle", "Days_Since_Last_Success": "Days Since Last Transaction", "Success_Count": "Total Volume", "Total_Value": "Total Value"}
    ),
    use_container_width=True,
    hide_index=True,
)