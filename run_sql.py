"""
Load the CSV into a local SQLite database and run every numbered script in /sql,
printing the result of each query. Usage:
    python scripts/run_sql.py [path/to/transactions.csv]
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def runnable(stmt: str) -> bool:
    body = "".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
    return bool(body)


def main(csv: Path) -> None:
    con = sqlite3.connect(ROOT / "data" / "fraud.db")
    pd.read_csv(csv).to_sql("transactions", con, if_exists="replace", index=False)
    for col in ("type", "nameOrig", "nameDest"):
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{col} ON transactions({col})")

    for script in sorted((ROOT / "sql").glob("0*.sql")):
        print(f"\n{'=' * 78}\n{script.name}\n{'=' * 78}")
        for stmt in script.read_text().split(";"):
            if runnable(stmt):
                print(pd.read_sql(stmt, con).to_string(index=False), "\n")
    con.close()


if __name__ == "__main__":
    default = ROOT / "data" / "sample_transactions.csv"
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else default)
