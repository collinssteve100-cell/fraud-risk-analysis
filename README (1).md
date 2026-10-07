# Data

## Option A: real data (recommended for your portfolio)

Download **PaySim** (synthetic mobile money transactions, ~6.3M rows) from Kaggle:
search "PaySim1" / "Synthetic Financial Datasets For Fraud Detection".
Place the CSV here as `PS_20174392719_1491204439457_log.csv`, then run:

    python scripts/run_sql.py data/PS_20174392719_1491204439457_log.csv
    python src/risk_pipeline.py --data data/PS_20174392719_1491204439457_log.csv

Notes for the full file:
- 6.3M rows will make the pandas pipeline slow and memory heavy. Start with a 500k-row sample
  (for example `df.sample(500_000, random_state=1)`) or run the SQL scripts on the full table.
- The pass-through and fan-in logic assume `nameOrig` / `nameDest` identifiers repeat. Check
  that on the real file and report what you find.
- The real file has far more balance mismatches than the synthetic sample. Document them in the
  data-quality section.

## Option B: synthetic sample

    python scripts/generate_sample_data.py

Creates `sample_transactions.csv` with the same columns. It is generated, not real, so label any
results from it as synthetic.

CSV and DB files are gitignored. Do not commit large data files.
