-- 01. Data quality checks. Run these BEFORE any analysis.

-- Basic integrity: row count, impossible values, missing identifiers
SELECT COUNT(*)                                          AS total_rows,
       SUM(CASE WHEN amount <= 0 THEN 1 ELSE 0 END)      AS nonpositive_amounts,
       SUM(CASE WHEN nameOrig IS NULL OR nameDest IS NULL THEN 1 ELSE 0 END) AS missing_ids,
       SUM(CASE WHEN type NOT IN ('PAYMENT','TRANSFER','CASH_OUT','CASH_IN','DEBIT') THEN 1 ELSE 0 END) AS unknown_types
FROM transactions;

-- Exact duplicate rows
SELECT COUNT(*) - COUNT(DISTINCT step || '|' || type || '|' || amount || '|' || nameOrig || '|' || nameDest) AS duplicate_rows
FROM transactions;

-- Does the origin balance reconcile? old - amount = new for outgoing types
-- On real PaySim a large share of rows do NOT reconcile. Worth documenting.
SELECT type,
       COUNT(*) AS txns,
       SUM(CASE WHEN ABS(oldbalanceOrg - amount - newbalanceOrig) > 0.01 THEN 1 ELSE 0 END) AS orig_balance_mismatch,
       ROUND(100.0 * SUM(CASE WHEN ABS(oldbalanceOrg - amount - newbalanceOrig) > 0.01 THEN 1 ELSE 0 END) / COUNT(*), 2) AS mismatch_pct
FROM transactions
WHERE type <> 'CASH_IN'
GROUP BY type
ORDER BY type;
