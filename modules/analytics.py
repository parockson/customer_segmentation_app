import pandas as pd
import numpy as np


def get_champions(cust_df, tenure_threshold_days=180):
    """Long-tenure active customers sorted by total value."""
    return cust_df[
        (cust_df["Lifecycle_Status"] == "Active") &
        (cust_df["Tenure_Days"] >= tenure_threshold_days)
    ].sort_values("Total_Value", ascending=False)


def get_inactive_and_returned(df):
    """
    Customers flagged as 'Reactivated' — those currently Active who
    previously had a recorded Inactive / Dormant / Churned spell.
    Since the dataset is customer-level (not raw transactions), we
    identify them as customers who are now Active but have a
    FirstTransaction date significantly earlier than LastTransaction,
    implying they had a gap (Days Difference >> 90).
    """
    if "Days_Since_Last_Success" not in df.columns:
        return df.iloc[0:0]   # empty frame

    # Use Days Difference column if present; otherwise derive from dates
    if "Days Difference" in df.columns:
        gap_col = "Days Difference"
    else:
        gap_col = "Days_Since_Last_Success"

    mask = (df["Lifecycle_Status"] == "Active") & (pd.to_numeric(df.get(gap_col, 0), errors="coerce").fillna(0) > 60)
    return df[mask]


def get_top_clients_dormant_30d(cust_df, top_percentile=0.8):
    """Top-value customers who have been silent for more than 30 days."""
    if cust_df.empty:
        return cust_df
    val_cutoff = cust_df["Total_Value"].quantile(top_percentile)
    return cust_df[
        (cust_df["Total_Value"] >= val_cutoff) &
        (cust_df["Days_Since_Last_Success"] > 30)
    ].sort_values("Days_Since_Last_Success", ascending=True)


def compute_month_over_month_trend(df):
    """
    Monthly unique-customer count per BusinessCategory.
    Uses LastTransaction as the date anchor (dataset is customer-level).
    """
    if "LastTransaction" not in df.columns or "BusinessCategory" not in df.columns:
        return pd.DataFrame()

    tmp = df.dropna(subset=["LastTransaction"]).copy()
    tmp["YearMonth"] = pd.to_datetime(tmp["LastTransaction"]).dt.to_period("M").astype(str)

    monthly = (
        tmp.groupby(["YearMonth", "BusinessCategory"])["CustomerID"]
        .nunique()
        .reset_index()
        .rename(columns={"CustomerID": "Customers"})
    )

    pivot = monthly.pivot(
        index="YearMonth", columns="BusinessCategory", values="Customers"
    ).fillna(0)

    return pivot


def get_cant_afford_to_lose(cust_df):
    """Union of top-15 by value and top-15 by volume, deduped."""
    top_val = cust_df.nlargest(15, "Total_Value")
    top_vol = cust_df.nlargest(15, "Success_Count")
    combined = pd.concat([top_val, top_vol]).drop_duplicates(subset=["CustomerID"])
    return combined.sort_values(["Total_Value", "Success_Count"], ascending=False)