# Customer Segmentation App

A Streamlit dashboard for RFM-based customer segmentation and cohort analysis.

## Project Structure

```
customer_segmentation_app/
│
├── .gitattributes              # Git LFS tracking for large data files
├── .streamlit/
│   └── config.toml             # Brand theme (primary: #ED1944, dark mode)
│
├── assets/
│   └── styles.css              # KPI card, table & badge styling
│
├── data/
│   └── transactions.csv        # Transaction dataset (tracked via Git LFS)
│
├── modules/
│   ├── __init__.py
│   ├── segmentation.py         # Data loading, lifecycle rules & RFM engine
│   └── analytics.py            # Cohort logic (Champions, Reactivated, Churn Risk…)
│
├── app.py                      # Main Streamlit dashboard entry point
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd customer_segmentation_app
```

### 2. Create & activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your data

Place your transaction CSV at `data/transactions.csv`.

**Required columns:**

| Column             | Type     | Description                     |
|--------------------|----------|---------------------------------|
| `customer_id`      | string   | Unique customer identifier      |
| `transaction_date` | datetime | Date of the transaction         |
| `amount`           | float    | Transaction value (positive)    |
| `product_category` | string   | *(optional)* Category label     |

### 5. Run the dashboard

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

---

## Modules

### `modules/segmentation.py`

| Function              | Description                                           |
|-----------------------|-------------------------------------------------------|
| `load_transactions()` | Load & validate the CSV                               |
| `classify_lifecycle()`| Assign New / Active / At Risk / Dormant / Lost stages |
| `compute_rfm()`       | Compute R, F, M scores (quintile-based, 1–5)          |

### `modules/analytics.py`

| Function                | Description                                            |
|-------------------------|--------------------------------------------------------|
| `assign_cohorts()`      | Tag each customer with a primary cohort                |
| `cohort_summary()`      | Aggregate KPIs per cohort                              |
| `monthly_cohort_trend()`| Monthly revenue per cohort (long format)               |

---

## Cohort Definitions

| Cohort        | Rule                                                                 |
|---------------|----------------------------------------------------------------------|
| **Champion**  | Purchased in last 90 days AND ≥ 5 orders total                       |
| **Reactivated** | Was dormant (180-day gap) and returned in the last 60 days         |
| **Churn Risk**  | No purchase for 90–270 days with ≥ 2 historical orders             |
| **New Customer**| First and only purchase within the last 30 days                   |
| **High Value**  | Lifetime spend in the top 20 percentile                            |
| **Active**      | All remaining active customers                                     |

---

## Git LFS

Large CSV files in `data/` are tracked with [Git LFS](https://git-lfs.github.com/).

```bash
git lfs install
git lfs track "data/*.csv"
git add .gitattributes
```

---

## License

MIT
