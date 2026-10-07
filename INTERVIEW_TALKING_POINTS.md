# Interview Talking Points: Fraud & Risk Project

## 30-second pitch
"I analysed mobile-money transactions to find which ones a risk team should review first. I validated the
data in SQL, built explainable risk indicators like account-emptied and mule pass-through patterns,
combined them into a score, and chose the alert threshold by weighing fraud stopped against review cost.
At the recommended threshold, the alerts were [X]% precise and stopped [Y]% of fraud flows."

## Questions to be ready for

**Why rules instead of a model?**
Explainability and auditability. Analysts and regulators need to know why something was flagged. Rules are
also the baseline any model must beat. I'd extend with a model and compare.

**How did you pick the threshold?**
Three views: precision/recall, net benefit given a cost per alert, and a fixed-capacity view for what analysts
can actually review. I also showed how the choice moves as the cost assumption changes.

**What's the difference between precision and recall here, and which matters more?**
Precision = share of alerts that are real fraud (analyst workload and customer friction). Recall = share of fraud
caught (loss). Which matters more depends on fraud loss per case versus cost per alert, which is why I show the sensitivity.

**Why count loss per flow?**
A drained account and the mule's cash-out move the same money. Counting both double-counts the loss, and stopping
either leg prevents it. Transaction-level recall understates how well the rules protect customers.

**What data quality problems did you find?**
_Use your real-data findings: balance mismatches, how many, which types, how you handled them._

**What are the weaknesses?**
Features use the full period, so there is potential leakage and they must be as-of in production. Weights are
hand-set. PaySim is synthetic and real fraud adapts. The cost per alert is an assumption.

**What would you do with more time?**
Learned model benchmarked against the rule score, time-aware features, monitoring for rule decay, an analyst
feedback loop to retrain weights.

## SQL skills this project demonstrates
Window functions (`RANGE BETWEEN`), self-joins, CTEs, conditional aggregation, `HAVING`, data validation queries.

## Numbers to memorise (from your REAL run)
- Fraud rate: ___  |  Types affected: ___  |  Legacy rule recall: ___
- Best indicator: ___ (precision ___, recall ___)
- Recommended threshold: ___ (alerts ___, precision ___, recall ___)
