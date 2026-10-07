-- 03. Risk indicator: "account emptied" (amount equals the full origin balance).

WITH flagged AS (
    SELECT *,
           CASE WHEN type IN ('TRANSFER','CASH_OUT')
                 AND oldbalanceOrg > 0
                 AND newbalanceOrig = 0
                 AND ABS(amount - oldbalanceOrg) < 0.01
                THEN 1 ELSE 0 END AS emptied
    FROM transactions
)
SELECT type, emptied,
       COUNT(*)                                 AS txns,
       SUM(isFraud)                             AS fraud_txns,
       ROUND(100.0 * SUM(isFraud) / COUNT(*), 2) AS fraud_rate_pct
FROM flagged
WHERE type IN ('TRANSFER','CASH_OUT')
GROUP BY type, emptied
ORDER BY type, emptied;

-- Rule quality: precision and recall of "emptied" as a stand-alone alert
WITH flagged AS (
    SELECT *,
           CASE WHEN type IN ('TRANSFER','CASH_OUT')
                 AND oldbalanceOrg > 0
                 AND newbalanceOrig = 0
                 AND ABS(amount - oldbalanceOrg) < 0.01
                THEN 1 ELSE 0 END AS emptied
    FROM transactions
)
SELECT SUM(emptied)                                              AS alerts,
       SUM(emptied * isFraud)                                    AS fraud_caught,
       ROUND(100.0 * SUM(emptied * isFraud) / SUM(emptied), 2)   AS precision_pct,
       ROUND(100.0 * SUM(emptied * isFraud) / SUM(isFraud), 2)   AS recall_pct
FROM flagged;
