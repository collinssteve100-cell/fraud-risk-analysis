# Fraud & Risk Analysis: Transaction Flagging

**Business question:** *Which transactions should a risk team review first, and which rules catch the most fraud for the least review workload?*

An end-to-end analyst project: validate the data in SQL, engineer explainable risk indicators in Python, combine them into a transparent score, and choose an alert threshold by weighing fraud caught against review cost.

**Tools:** SQL (SQLite / PostgreSQL), Python, Pandas, NumPy, Matplotlib

---

## Headline results

> ⚠️ **Fill this in with your real-data numbers.** The figures below come from the *synthetic* sample that ships with the repo, so the pipeline runs out of the box. Re-run on the real PaySim dataset (see `data/README.md`) and replace them before showing this to anyone.

| Metric | Synthetic sample | Real PaySim |
|---|---|---|
| Transactions / fraud rate | 200,000 / 0.60% | _fill in_ |
| Share of fraud in TRANSFER + CASH_OUT | 100% | _fill in_ |
| Legacy `isFlaggedFraud` rule recall | 0.1% | _fill in_ |
| Best single indicator ("account emptied") | 39% precision, 89.5% recall | _fill in_ |
| Recommended threshold (score ≥ 7) | 94% precision, 59% txn recall, 747 alerts | _fill in_ |
| Fraud **flows** stopped at that threshold | 100% | _fill in_ |

## Approach

1. **Data quality (SQL, `sql/01`)**: duplicates, impossible values, and whether balances reconcile. Issues are logged, not silently dropped.
2. **Scope the problem (`sql/02`)**: fraud rate by type and by day. Fraud only occurs in TRANSFER and CASH_OUT, so scoring is restricted to those types, which cuts review volume by about 60%.
3. **Risk indicators (SQL `03`-`05`, mirrored in Python):**
   - *Account emptied*: amount equals the full origin balance
   - *Pass-through*: an account receives a transfer and cashes out the same amount within 2 hours (mule behaviour)
   - *High fan-in*: one account receiving from many distinct senders
   - *New destination*: destination balance was zero before the transaction
   - *Large / round amounts*
4. **Weighted rule score (`src/risk_pipeline.py`)**: hand-set, explainable weights. Every alert can be explained to an analyst in one sentence.
5. **Threshold selection**: precision/recall sweep, net benefit (loss prevented minus review cost), a cost-sensitivity table, and a fixed-capacity view ("if analysts can review only the top 0.5%...").

## Key design decisions

- **Rules over a black-box model.** Risk teams need explainability and auditability. A model is a natural extension, but rules are the right baseline.
- **Flow-level loss.** A fraud involves two linked transactions moving the same money. Loss is counted once per flow, and a flow is "stopped" if either leg is flagged.
- **Cost is an assumption, so it is shown as a sensitivity.** The best threshold is reported across a range of cost-per-alert values.

## Limitations (be upfront about these)

- Fan-in is computed over the full period. In production it must be computed *as of* each transaction's timestamp to avoid leaking future information.
- Weights are hand-set, not learned. A next step is a logistic regression or gradient-boosted model benchmarked against the rule score.
- PaySim is synthetic. Real fraud adapts to rules, so performance would decay without monitoring.
- The cost-per-alert figure is an assumption, not a measured value.

## Run it

```bash
pip install -r requirements.txt

python scripts/generate_sample_data.py     # synthetic data (skip if using real PaySim)
python scripts/run_sql.py                  # loads SQLite, runs sql/01-06, prints results
python src/risk_pipeline.py                # cleaning, indicators, score, charts, CSVs
python src/risk_pipeline.py --data data/PS_20174392719_1491204439457_log.csv --review-cost 2000
```

Outputs are written to `reports/`: `indicator_quality.csv`, `threshold_sweep.csv`, `cost_sensitivity.csv`, `flagged_transactions.csv`, and `figures/*.png`.

## Repo structure

```
├── sql/            numbered scripts: 01 quality -> 06 rule comparison (+ postgres_schema.sql)
├── src/            risk_pipeline.py: cleaning, indicators, scoring, evaluation, charts
├── scripts/        generate_sample_data.py, run_sql.py
├── reports/        generated tables and charts, plus risk_memo_template.md
├── data/           see data/README.md
└── INTERVIEW_TALKING_POINTS.md
```

## Next steps

- [ ] Train a logistic regression / gradient boosting model and compare against the rule score
- [ ] Compute time-aware (as-of) features
- [ ] Add a Power BI / Looker page: alerts by day, rule contribution, analyst queue
