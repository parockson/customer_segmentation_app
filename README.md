# Customer Segmentation App

A Streamlit dashboard for customer lifecycle, recency, retention opportunities,
and segment performance.

## Data source

The app reads `data/clients_dataset.xlsx`. The workbook contains customer-level
records in the `Retail`, `SMB`, and `Corporate` sheets. Each sheet may use a
different customer ID and status column name; the loader maps those to a
common schema.

The workbook should include:

| Data | Supported column names |
| --- | --- |
| Customer ID | `sender_wallet_number`, `mobile_number`, `client_id`, or `customer_id` |
| Customer value | `Value` or `Amount` |
| Last transaction | `LastTransaction` |
| First transaction | `FirstTransaction` (optional) |
| Transaction count | `Volume` (optional) |
| Status | `transaction_status` or `status` (optional) |
| Customer segment | `CustomerSegment` (optional) |
| Business category | `Category` (optional) |
| Workbook refresh date | `RecordDate` (optional) |
| Days since last transaction | `Days Difference` (optional) |

When present, `Days Difference` is used for recency so records from sheets
refreshed on different dates are evaluated using their own source snapshot.
`RecordDate` provides the dashboard's “as of” date. Older workbooks without
these fields continue to use the transaction dates as a fallback.

## Run locally

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

If the workbook is stored as a Git LFS pointer, install Git LFS and run
`git lfs pull` after cloning.

## Project structure

```text
app.py                      # Streamlit dashboard
assets/styles.css           # Dashboard styles
data/clients_dataset.xlsx   # Customer data workbook
modules/segmentation.py     # Workbook loading and lifecycle calculations
modules/analytics.py        # Supporting customer analytics
```

## License

MIT
