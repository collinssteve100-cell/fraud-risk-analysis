-- Reference schema if you want to run this project in PostgreSQL instead of SQLite.
-- The numbered scripts (01-06) work on both. Only the load step differs.
CREATE TABLE transactions (
    step            INTEGER,          -- 1 step = 1 hour (743 steps = 30 days)
    type            VARCHAR(10),      -- PAYMENT, TRANSFER, CASH_OUT, CASH_IN, DEBIT
    amount          NUMERIC(14,2),
    nameOrig        VARCHAR(12),
    oldbalanceOrg   NUMERIC(14,2),
    newbalanceOrig  NUMERIC(14,2),
    nameDest        VARCHAR(12),
    oldbalanceDest  NUMERIC(14,2),
    newbalanceDest  NUMERIC(14,2),
    isFraud         SMALLINT,
    isFlaggedFraud  SMALLINT
);
-- \copy transactions FROM 'data/PS_20174392719_1491204439457_log.csv' CSV HEADER;
-- Postgres lowercases unquoted identifiers, so nameOrig becomes nameorig. That is fine.
-- The velocity query in 04 uses RANGE BETWEEN 23 PRECEDING, which Postgres 11+ supports.
-- For the pass-through query in 05, replace rowid with a serial id column.
CREATE INDEX idx_type ON transactions(type);
CREATE INDEX idx_orig ON transactions(nameOrig);
CREATE INDEX idx_dest ON transactions(nameDest);
