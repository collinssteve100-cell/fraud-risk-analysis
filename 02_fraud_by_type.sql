-- 02. Where does fraud live? Scope the problem before building rules.

SELECT type,
       COUNT(*)                                                    AS txns,
       SUM(isFraud)                                                AS fraud_txns,
       ROUND(100.0 * SUM(isFraud) / COUNT(*), 3)                   AS fraud_rate_pct,
       ROUND(SUM(CASE WHEN isFraud = 1 THEN amount ELSE 0 END), 0) AS fraud_amount
FROM transactions
GROUP BY type
ORDER BY fraud_txns DESC;

-- Fraud by day (24 steps = 1 day): is there a time pattern?
SELECT (step - 1) / 24 + 1 AS day,
       COUNT(*)            AS txns,
       SUM(isFraud)        AS fraud_txns
FROM transactions
GROUP BY day
ORDER BY day;
