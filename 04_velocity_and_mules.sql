-- 04. Mule-account indicators: many senders into one account, quickly.

-- Top candidate mule accounts by number of distinct senders
SELECT nameDest,
       COUNT(*)                    AS incoming_transfers,
       COUNT(DISTINCT nameOrig)    AS distinct_senders,
       ROUND(SUM(amount), 0)       AS total_received,
       SUM(isFraud)                AS confirmed_fraud_txns
FROM transactions
WHERE type = 'TRANSFER'
GROUP BY nameDest
HAVING COUNT(DISTINCT nameOrig) >= 3
ORDER BY distinct_senders DESC, total_received DESC
LIMIT 15;

-- Velocity: incoming transfers to the same account in the trailing 24 hours (window function)
WITH t AS (
    SELECT nameDest, step, isFraud,
           COUNT(*) OVER (PARTITION BY nameDest
                          ORDER BY step
                          RANGE BETWEEN 23 PRECEDING AND CURRENT ROW) AS transfers_in_24h
    FROM transactions
    WHERE type = 'TRANSFER'
)
SELECT transfers_in_24h,
       COUNT(*)                                  AS txns,
       SUM(isFraud)                              AS fraud_txns,
       ROUND(100.0 * SUM(isFraud) / COUNT(*), 2) AS fraud_rate_pct
FROM t
GROUP BY transfers_in_24h
ORDER BY transfers_in_24h;
