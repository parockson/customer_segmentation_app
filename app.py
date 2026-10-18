import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

from modules.segmentation import load_data, compute_customer_lifecycle


st.set_page_config(
    page_title="Customer Lifecycle Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

css_path = Path("assets/styles.css")
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


@st.cache_data
def get_dataset(data_version):
    return load_data("data/clients_dataset.xlsx")


try:
    df = get_dataset("main-page-lifecycle-v3")
except Exception as error:
    st.error(
        "Could not load `data/clients_dataset.xlsx`. "
        f"Check that the workbook exists and contains the expected sheets. Error: {error}"
    )
    st.stop()


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
    dates = pd.to_datetime(series, errors="coerce").dropna()
    dates = dates[dates.dt.year > 1900]
    if dates.empty:
        return fallback, fallback
    return dates.min().date(), dates.max().date()


def format_currency(value):
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.2f}"


def chart_layout(fig, height=330):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F1F3EF", family="DM Sans, sans-serif"),
        margin=dict(l=12, r=16, t=22, b=12),
        legend_title_text="",
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", zeroline=False),
    )
    return fig


def add_customer_names(frame):
    result = frame.copy()
    name_column = next((column for column in ("CustomerName", "name", "Name") if column in result), None)
    result["Name"] = result[name_column].fillna("").astype(str) if name_column else ""
    return result


st.markdown("# Customer Lifecycle")
st.markdown("Customer health, recency, retention opportunities, and segment performance")

st.markdown("### Filters")
fallback_date = AS_OF.date()
first_min, first_max = valid_date_bounds(df["FirstTransaction"], fallback_date)
last_min, last_max = valid_date_bounds(df["LastTransaction"], fallback_date)
filter_segment, filter_category, filter_type = st.columns([1, 1, 1])
all_biz_segments = sorted(df["BizSegment"].dropna().unique().tolist())
with filter_segment:
    selected_biz_segments = st.multiselect(
        "Business segment",
        all_biz_segments,
        default=[],
        placeholder="All business segments",
        key="main_biz_segment_v2",
    )

category_source = df[df["BizSegment"].isin(selected_biz_segments)] if selected_biz_segments else df
category_options = sorted(category_source["BusinessCategory"].dropna().unique().tolist())
if "main_business_category_v2" in st.session_state:
    st.session_state["main_business_category_v2"] = [
        value for value in st.session_state["main_business_category_v2"] if value in category_options
    ]
customer_type_options = sorted(df["CustomerType"].dropna().unique().tolist())
with filter_category:
    selected_categories = st.multiselect(
        "Business category",
        category_options,
        default=[],
        placeholder="All business categories",
        key="main_business_category_v2",
    )
with filter_type:
    selected_types = st.multiselect(
        "Customer segment",
        customer_type_options,
        default=[],
        placeholder="All customer segments",
        key="main_customer_type_v2",
    )

filter_first_date, filter_last_date = st.columns(2)
with filter_first_date:
    first_date_range = st.date_input(
        "First transaction date",
        value=(first_min, first_max),
        min_value=first_min,
        max_value=first_max,
        key="main_first_transaction_date",
    )
with filter_last_date:
    last_date_range = st.date_input(
        "Last transaction date",
        value=(last_min, last_max),
        min_value=last_min,
        max_value=last_max,
        key="main_last_transaction_date",
    )

filtered_df = df
if selected_biz_segments:
    filtered_df = filtered_df[filtered_df["BizSegment"].isin(selected_biz_segments)]
if selected_categories:
    filtered_df = filtered_df[filtered_df["BusinessCategory"].isin(selected_categories)]
if selected_types:
    filtered_df = filtered_df[filtered_df["CustomerType"].isin(selected_types)]

if len(first_date_range) == 2:
    first_start, first_end = map(pd.Timestamp, first_date_range)
    filtered_df = filtered_df[
        filtered_df["FirstTransaction"].isna()
        | filtered_df["FirstTransaction"].between(first_start, first_end)
    ]
if len(last_date_range) == 2:
    last_start, last_end = map(pd.Timestamp, last_date_range)
    filtered_df = filtered_df[
        filtered_df["LastTransaction"].isna()
        | filtered_df["LastTransaction"].between(last_start, last_end)
    ]

if filtered_df.empty:
    st.info("No customer records match these filters. Adjust the selections above.")
    st.stop()

cust_df = compute_customer_lifecycle(filtered_df, snapshot_date=AS_OF)
cust_df = add_customer_names(cust_df)
cust_df["Tenure (years)"] = (cust_df["Tenure_Days"].clip(lower=0) / 365.25).round(1)
cust_df["As of"] = AS_OF.date()

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

class_counts = cust_df["Lifecycle_Status"].value_counts().reindex(LIFECYCLE_ORDER, fill_value=0)
class_stats = pd.DataFrame(
    {
        "Lifecycle class": LIFECYCLE_ORDER,
        "Records": class_counts.values,
        "Share": (class_counts / max(len(cust_df), 1) * 100).reindex(LIFECYCLE_ORDER).values,
    }
)
count_col, percent_col = st.columns(2)
with count_col:
    st.subheader("Records by lifecycle class")
    count_fig = px.bar(
        class_stats,
        x="Records",
        y="Lifecycle class",
        orientation="h",
        color="Lifecycle class",
        color_discrete_map=LIFECYCLE_COLORS,
        text="Records",
        category_orders={"Lifecycle class": list(reversed(LIFECYCLE_ORDER))},
    )
    count_fig.update_traces(
        texttemplate="%{text:,}",
        textposition="inside",
        insidetextanchor="end",
        textfont_color="#F1F3EF",
        showlegend=False,
    )
    chart_layout(count_fig, 300).update_layout(xaxis_title="Customers", yaxis_title="")
    st.plotly_chart(count_fig, use_container_width=True)
with percent_col:
    st.subheader("Records by lifecycle class (%)")
    percent_fig = px.bar(
        class_stats,
        x="Share",
        y="Lifecycle class",
        orientation="h",
        color="Lifecycle class",
        color_discrete_map=LIFECYCLE_COLORS,
        text="Share",
        category_orders={"Lifecycle class": list(reversed(LIFECYCLE_ORDER))},
    )
    percent_fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False, showlegend=False)
    chart_layout(percent_fig, 300).update_layout(xaxis_title="Share of records (%)", yaxis_title="", xaxis_range=[0, class_stats["Share"].max() * 1.18 if class_stats["Share"].max() else 1])
    st.plotly_chart(percent_fig, use_container_width=True)

st.divider()
recency_col, trend_col = st.columns(2)
with recency_col:
    st.subheader("Customer recency")
    recency_days = cust_df["Days_Since_Last_Success"]
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
    st.subheader("Customer segment trend by month")
    monthly = filtered_df.dropna(subset=["LastTransaction"]).copy()
    monthly["Month"] = monthly["LastTransaction"].dt.to_period("M").dt.to_timestamp()
    monthly_counts = (
        monthly.groupby(["Month", "CustomerType"], observed=True)["CustomerID"]
        .nunique()
        .reset_index(name="Customers")
    )
    if monthly_counts.empty:
        st.info("No dated customer records match the selected filters.")
    else:
        trend_fig = px.line(
            monthly_counts,
            x="Month",
            y="Customers",
            color="CustomerType",
            markers=True,
            color_discrete_map=LIFECYCLE_COLORS,
        )
        chart_layout(trend_fig, 340).update_layout(xaxis_title="Month", yaxis_title="Customers")
        st.plotly_chart(trend_fig, use_container_width=True)

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

value_col, volume_col = st.columns(2)
value_columns = ["Rank", "CustomerID", "Name", "BizSegment", "Success_Count", "Total_Value", "Lifecycle_Status"]
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

win_back_candidates = cust_df[
    active_mask & cust_df["Days_Since_Last_Success"].between(61, 90)
].nlargest(10, "Total_Value")
win_back_columns = [
    "CustomerID", "Name", "BizSegment", "Days_Since_Last_Success", "Success_Count", "Total_Value", "LastTransaction"
]
st.subheader("Top 10 win-back candidates")
st.caption("Currently active, 61–90 days since last transaction, ranked by value. This workbook has no transaction history to confirm a prior return.")
st.dataframe(
    win_back_candidates[win_back_columns].rename(
        columns={"Days_Since_Last_Success": "Days Since Last Transaction", "Success_Count": "Total Volume", "Total_Value": "Total Value"}
    ),
    use_container_width=True,
    hide_index=True,
)

not_active = cust_df[~active_mask].nlargest(10, "Total_Value")
st.subheader("Top 10 customers who are not active")
st.dataframe(
    not_active[["CustomerID", "Name", "BizSegment", "Lifecycle_Status", "Days_Since_Last_Success", "Success_Count", "Total_Value", "LastTransaction"]].rename(
        columns={"Lifecycle_Status": "Lifecycle", "Days_Since_Last_Success": "Days Since Last Transaction", "Success_Count": "Total Volume", "Total_Value": "Total Value"}
    ),
    use_container_width=True,
    hide_index=True,
)