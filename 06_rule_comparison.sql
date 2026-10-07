-- 06. Compare candidate rules side by side: alerts, precision, recall.
-- Review workload (alerts) vs fraud caught is the core trade-off in risk.

WITH f AS (
    SELECT *,
           CASE WHEN type IN ('TRANSFER','CASH_OUT') AND oldbalanceOrg > 0 AND newbalanceOrig = 0
                 AND ABS(amount - oldbalanceOrg) < 0.01 THEN 1 ELSE 0 END AS emptied,
           CASE WHEN type IN ('TRANSFER','CASH_OUT') AND oldbalanceDest = 0 THEN 1 ELSE 0 END AS dest_new,
           CASE WHEN type IN ('TRANSFER','CASH_OUT') AND amount >= 100000 THEN 1 ELSE 0 END AS large
    FROM transactions
),
rules AS (
    SELECT 'Legacy isFlaggedFraud'          AS rule, isFlaggedFraud AS hit, isFraud FROM f
    UNION ALL SELECT 'Risky type only',       CASE WHEN type IN ('TRANSFER','CASH_OUT') THEN 1 ELSE 0 END, isFraud FROM f
    UNION ALL SELECT 'Emptied',               emptied, isFraud FROM f
    UNION ALL SELECT 'Emptied + dest new',    emptied * dest_new, isFraud FROM f
    UNION ALL SELECT 'Emptied + dest new + large', emptied * dest_new * large, isFraud FROM f
)
SELECT rule,
       SUM(hit)                                                        AS alerts,
       SUM(hit * isFraud)                                              AS fraud_caught,
       ROUND(100.0 * SUM(hit * isFraud) / NULLIF(SUM(hit), 0), 2)      AS precision_pct,
       ROUND(100.0 * SUM(hit * isFraud) / SUM(isFraud), 2)             AS recall_pct
FROM rules
GROUP BY rule
ORDER BY alerts DESC;
