# Risk Memo: Transaction Fraud Flagging Recommendation

**To:** Head of Risk  **From:** _your name_  **Date:** _date_

## Recommendation
_One paragraph. Example: "Alert on transactions with a risk score of 7 or higher. This produces
X alerts per month (Y% of volume), with Z% precision, and stops N% of fraud flows."_

## Why this matters
- Total fraud in the period: _count, amount_
- Fraud sits entirely in TRANSFER and CASH_OUT, so everything else can be excluded from review
- The existing rule (`isFlaggedFraud`) catches _x%_ of fraud

## What the data shows
| Indicator | Alerts | Precision | Recall | Lift |
|---|---|---|---|---|
| _paste from reports/indicator_quality.csv_ | | | | |

_Insert figures/02 and figures/03._

## Trade-offs
- Lower threshold: more fraud caught, more analyst workload and customer friction
- Higher threshold: fewer alerts, higher precision, more fraud slips through
- Cost sensitivity: _paste from reports/cost_sensitivity.csv and say how stable the choice is_

## Risks and limitations
- Fraudsters adapt, so rules need monitoring and refresh
- Features computed over the full period, which must be as-of in production
- Cost per alert is an assumption

## Proposed next steps
1. Pilot the threshold on one queue for 2 weeks and track false-positive rate
2. Benchmark a model against the rule score
3. Set up weekly monitoring of precision and alert volume
