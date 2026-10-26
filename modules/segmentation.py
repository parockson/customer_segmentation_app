from datetime import datetime

import pandas as pd
import numpy as np
from pathlib import Path


# ── Column alias registries ────────────────────────────────────────────────────
# All keys MUST be pre-normalised: lowercase, NO spaces, NO underscores.
# They are matched against _normalise_key(col) which strips spaces & underscores.

ALIAS_ID     = {"senderwalletnumber", "clientid", "mobilenumber", "customerid"}
ALIAS_STATUS = {"transactionstatus", "status", "transstatus"}
ALIAS_AMOUNT = {"value", "amount", "totalvalue", "revenue"}
ALIAS_VOLUME = {"volume", "frequency", "count", "totalvolume", "txcount"}
ALIAS_LAST_DATE  = {"lasttransaction", "lasttx", "lastsuccessdate"}
ALIAS_FIRST_DATE = {"firsttransaction", "firsttx", "firstsuccessdate"}
ALIAS_SEGMENT    = {"customersegment", "customertype"}
ALIAS_CATEGORY   = {"category", "businesscategory", "productcategory"}
ALIAS_SNAPSHOT_DATE = {"recorddate", "snapshotdate"}
ALIAS_DAYS_SINCE = {"daysdifference", "dayssincelasttransaction", "dayssincelastsuccess"}


def _normalise_key(col: str) -> str:
    """Lowercase, remove spaces and underscores for fuzzy alias matching."""
    return col.strip().lower().replace(" ", "").replace("_", "")


def load_data(filepath=None):
    """
    Loads all sheets (Retail, Corporate, SMB) from the Excel workbook.

    Each sheet is already customer-level (one row per customer).
    Normalises heterogeneous column names to a canonical schema:

        CustomerID       – sender_wallet_number | client_id | mobile_number
        Status           – transaction_status   | status    | trans_status
        Amount           – Value
        Volume           – Volume  (transaction count / frequency)
        TransactionDate  – LastTransaction  (lifecycle anchor)
        FirstTransaction – FirstTransaction
        LastTransaction  – LastTransaction
        SnapshotDate     – RecordDate (workbook refresh date)
        DaysSinceLastTransaction – Days Difference
        CustomerType     – CustomerSegment
        BusinessCategory – Category
        BizSegment       – tagged from sheet name (Retail / Corporate / SMB)
    """
    if filepath is None:
        filepath = Path(__file__).resolve().parent.parent / "data" / "clients_dataset.xlsx"
    filepath = Path(filepath)
    if filepath.exists():
        with filepath.open("rb") as workbook_file:
            if workbook_file.read(100).startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise RuntimeError(
                    f"{filepath} is a Git LFS pointer, not the workbook. Run `git lfs pull` in the repository."
                )

    excel_file = pd.ExcelFile(filepath, engine="calamine")

    segment_dfs = []
    for sheet in excel_file.sheet_names:
        df_sheet = pd.read_excel(excel_file, sheet_name=sheet)

        col_map = {}
        mapped = set()   # tracks which canonical names are already assigned

        for col in df_sheet.columns:
            key = _normalise_key(col)   # normalised form to match alias sets

            if key in ALIAS_ID and "CustomerID" not in mapped:
                col_map[col] = "CustomerID";        mapped.add("CustomerID")
            elif key in ALIAS_STATUS and "Status" not in mapped:
                col_map[col] = "Status";            mapped.add("Status")
            elif key in ALIAS_AMOUNT and "Amount" not in mapped:
                col_map[col] = "Amount";            mapped.add("Amount")
            elif key in ALIAS_VOLUME and "Volume" not in mapped:
                col_map[col] = "Volume";            mapped.add("Volume")
            elif key in ALIAS_LAST_DATE and "LastTransaction" not in mapped:
                col_map[col] = "LastTransaction";   mapped.add("LastTransaction")
            elif key in ALIAS_FIRST_DATE and "FirstTransaction" not in mapped:
                col_map[col] = "FirstTransaction";  mapped.add("FirstTransaction")
            elif key in ALIAS_SNAPSHOT_DATE and "SnapshotDate" not in mapped:
                col_map[col] = "SnapshotDate";      mapped.add("SnapshotDate")
            elif key in ALIAS_DAYS_SINCE and "DaysSinceLastTransaction" not in mapped:
                col_map[col] = "DaysSinceLastTransaction"; mapped.add("DaysSinceLastTransaction")
            elif key in ALIAS_SEGMENT and "CustomerType" not in mapped:
                col_map[col] = "CustomerType";      mapped.add("CustomerType")
            elif key in ALIAS_CATEGORY and "BusinessCategory" not in mapped:
                col_map[col] = "BusinessCategory";  mapped.add("BusinessCategory")

        df_sheet = df_sheet.rename(columns=col_map)
        df_sheet["BizSegment"] = sheet.strip()
        segment_dfs.append(df_sheet)

    df = pd.concat(segment_dfs, ignore_index=True)

    # ── Validate mandatory columns exist after normalisation ──────────────
    required = ("CustomerID", "Amount", "LastTransaction")
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(
            f"Could not find columns {missing} after normalisation. "
            f"Available columns: {list(df.columns)}"
        )

    # ── Use LastTransaction as the universal date anchor ──────────────────
    df["LastTransaction"] = pd.to_datetime(df["LastTransaction"], errors="coerce")
    df.loc[df["LastTransaction"].dt.year <= 1900, "LastTransaction"] = pd.NaT
    df["TransactionDate"] = df["LastTransaction"]
    if "FirstTransaction" in df.columns:
        df["FirstTransaction"] = pd.to_datetime(df["FirstTransaction"], errors="coerce")
        df.loc[df["FirstTransaction"].dt.year <= 1900, "FirstTransaction"] = pd.NaT
    if "SnapshotDate" in df.columns:
        df["SnapshotDate"] = pd.to_datetime(df["SnapshotDate"], errors="coerce")
    if "DaysSinceLastTransaction" in df.columns:
        df["DaysSinceLastTransaction"] = pd.to_numeric(
            df["DaysSinceLastTransaction"], errors="coerce"
        )

    # ── Cast remaining types ──────────────────────────────────────────────
    df["Amount"]     = pd.to_numeric(df["Amount"],  errors="coerce").fillna(0)
    df["CustomerID"] = df["CustomerID"].astype(str).str.strip()

    if "Volume" in df.columns:
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int)

    if "Status" in df.columns:
        df["Status"] = df["Status"].astype(str).str.strip().str.upper()
    else:
        df["Status"] = "SUCCESS"

    for col in ("CustomerType", "BusinessCategory"):
        if col not in df.columns:
            df[col] = "Unknown"
        elif col == "BusinessCategory":
            df[col] = df[col].map(
                lambda value: pd.NA if isinstance(value, (datetime, pd.Timestamp)) else value
            )
        df[col] = df[col].astype("string")

    for col in ("Status", "name", "CustomerType", "BusinessCategory", "BizSegment"):
        if col in df.columns:
            df[col] = df[col].astype("category")

    return df


def compute_customer_lifecycle(df, snapshot_date=None):
    """
    This dataset is already customer-level (one row per customer).
    Derives lifecycle stage and value segment from the existing columns.

    Lifecycle rules (days since LastTransaction / last known activity):
        Idle     – Amount == 0 or no date
        Active   – <= 90 days
        Inactive – 91 – 180 days
        Dormant  – 181 – 364 days
        Churned  – >= 365 days
    """
    if snapshot_date is None:
        snapshot_date = df["TransactionDate"].max()

    cust = df.copy()

    # ── Timing columns ────────────────────────────────────────────────────
    reference_date = snapshot_date
    if "SnapshotDate" in cust.columns:
        reference_date = cust["SnapshotDate"].fillna(snapshot_date)
    calculated_recency = (reference_date - cust["LastTransaction"]).dt.days
    if "DaysSinceLastTransaction" in cust.columns:
        source_recency = pd.to_numeric(cust["DaysSinceLastTransaction"], errors="coerce")
        cust["Days_Since_Last_Success"] = source_recency.fillna(calculated_recency)
    else:
        cust["Days_Since_Last_Success"] = calculated_recency

    if "FirstTransaction" in cust.columns:
        cust["Tenure_Days"] = (reference_date - cust["FirstTransaction"]).dt.days
    else:
        cust["Tenure_Days"] = cust["Days_Since_Last_Success"]

    # Canonical aliases for downstream analytics
    cust["Total_Value"]   = cust["Amount"]
    cust["Success_Count"] = cust["Volume"] if "Volume" in cust.columns else 1

    # ── Lifecycle assignment ──────────────────────────────────────────────
    days_since_last = cust["Days_Since_Last_Success"]
    idle = cust["Total_Value"].eq(0) | cust["LastTransaction"].isna() | days_since_last.isna()
    cust["Lifecycle_Status"] = np.select(
        [idle, days_since_last.le(90), days_since_last.le(180), days_since_last.le(364)],
        ["Idle", "Active", "Inactive", "Dormant"],
        default="Churned",
    )

    # ── Value segment assignment ──────────────────────────────────────────
    active = cust[cust["Total_Value"] > 0]
    if len(active) > 0:
        val_q75  = active["Total_Value"].quantile(0.75)
        freq_q75 = active["Success_Count"].quantile(0.75)

        is_high_value = cust["Total_Value"].ge(val_q75)
        is_high_frequency = cust["Success_Count"].ge(freq_q75)
        recently_active = days_since_last.le(90)
        cust["Value_Segment"] = np.select(
            [
                cust["Lifecycle_Status"].eq("Idle"),
                is_high_value & is_high_frequency & recently_active,
                is_high_frequency & recently_active,
                is_high_value & days_since_last.gt(90),
                is_high_value & recently_active,
                recently_active,
            ],
            [
                "Unconverted Lead",
                "Champions",
                "Loyal Accounts",
                "At Risk High Rollers",
                "Big Spenders",
                "Recent Performers",
            ],
            default="Needs Attention",
        )
    else:
        cust["Value_Segment"] = "Unconverted Lead"

    return cust