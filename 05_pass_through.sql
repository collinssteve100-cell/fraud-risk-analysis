-- 05. Pass-through pattern: an account receives a TRANSFER and CASH_OUTs the
-- exact same amount within 2 hours. Classic mule behaviour.

WITH pt AS (
    SELECT DISTINCT c.rowid AS cashout_id
    FROM transactions c
    JOIN transactions t
      ON t.type = 'TRANSFER'
     AND t.nameDest = c.nameOrig
     AND t.amount   = c.amount
     AND c.step - t.step BETWEEN 0 AND 2
    WHERE c.type = 'CASH_OUT'
)
SELECT COUNT(*)                                                           AS alerts,
       SUM(x.isFraud)                                                     AS fraud_caught,
       ROUND(100.0 * SUM(x.isFraud) / COUNT(*), 2)                        AS precision_pct,
       ROUND(100.0 * SUM(x.isFraud) / (SELECT SUM(isFraud) FROM transactions WHERE type = 'CASH_OUT'), 2) AS cashout_recall_pct
FROM transactions x
JOIN pt ON x.rowid = pt.cashout_id;
