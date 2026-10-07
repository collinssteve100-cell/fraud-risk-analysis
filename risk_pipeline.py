"""
Fraud & risk analysis pipeline.

    clean  ->  engineer risk indicators  ->  weighted rule score  ->  evaluate trade-offs

Usage:
    python src/risk_pipeline.py                         # uses the synthetic sample
    python src/risk_pipeline.py --data data/PS_20174392719_1491204439457_log.csv
    python src/risk_pipeline.py --review-cost 40        # change analyst cost per alert
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RISKY_TYPES = ["TRANSFER", "CASH_OUT"]

# Transparent, hand-set weights. Explainability is a feature in risk teams:
# an analyst must be able to say WHY a transaction was flagged.
RULE_WEIGHTS = {
    "pass_through": 4,       # received a transfer, cashed out the same amount within 2h
    "orig_emptied": 3,       # amount == full account balance
    "high_fanin": 2,         # account tied to many distinct senders
    "dest_new_account": 1,   # destination had a zero balance before
    "large_amount": 1,       # in the top 5% for its type
    "round_amount": 1,       # multiple of 1,000
}


# --------------------------------------------------------------------------- #
# 1. Cleaning
# --------------------------------------------------------------------------- #
def load_and_clean(path: Path):
    """Load the CSV, apply basic validation, and return (clean_df, cleaning_log)."""
    df = pd.read_csv(path)
    log = {"rows_raw": len(df)}

    log["duplicates_removed"] = int(df.duplicated().sum())
    df = df.drop_duplicates()

    log["nonpositive_amount_removed"] = int((df["amount"] <= 0).sum())
    df = df[df["amount"] > 0]

    log["missing_id_removed"] = int(df[["nameOrig", "nameDest"]].isna().any(axis=1).sum())
    df = df.dropna(subset=["nameOrig", "nameDest"])

    # Documented, not removed: balance fields that do not reconcile
    outgoing = df["type"] != "CASH_IN"
    mismatch = (df["oldbalanceOrg"] - df["amount"] - df["newbalanceOrig"]).abs() > 0.01
    log["orig_balance_mismatch_rows"] = int((outgoing & mismatch).sum())

    df = df.reset_index(drop=True)
    log["rows_clean"] = len(df)
    return df, log


# --------------------------------------------------------------------------- #
# 2. Risk indicators
# --------------------------------------------------------------------------- #
def add_risk_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_risky_type"] = df["type"].isin(RISKY_TYPES)

    df["orig_emptied"] = (
        (df["oldbalanceOrg"] > 0)
        & (df["newbalanceOrig"] == 0)
        & np.isclose(df["amount"], df["oldbalanceOrg"], atol=0.01)
    )
    df["dest_new_account"] = df["is_risky_type"] & (df["oldbalanceDest"] == 0)
    df["round_amount"] = (df["amount"] % 1000 == 0)
    p95 = df.groupby("type")["amount"].transform(lambda s: s.quantile(0.95))
    df["large_amount"] = df["amount"] > p95

    # Fan-in: distinct senders per receiving account.
    # NOTE: computed over the full period for simplicity. In production this must be
    # computed "as of" each transaction's timestamp, otherwise it leaks future information.
    senders = df.loc[df["type"] == "TRANSFER"].groupby("nameDest")["nameOrig"].nunique()
    fanin_dest = df["nameDest"].map(senders).fillna(0)   # relevant to TRANSFER rows
    fanin_orig = df["nameOrig"].map(senders).fillna(0)   # relevant to CASH_OUT rows
    df["account_fanin"] = np.where(df["type"] == "TRANSFER", fanin_dest, fanin_orig)
    df["high_fanin"] = df["is_risky_type"] & (df["account_fanin"] >= 5)

    # Pass-through: CASH_OUT matching an earlier TRANSFER into that account
    t = df.loc[df["type"] == "TRANSFER", ["nameDest", "amount", "step"]].rename(
        columns={"nameDest": "nameOrig", "step": "in_step"})
    c = df.loc[df["type"] == "CASH_OUT", ["nameOrig", "amount", "step"]].reset_index()
    m = c.merge(t, on=["nameOrig", "amount"])
    m = m[(m["step"] - m["in_step"]).between(0, 2)]
    df["pass_through"] = df.index.isin(m["index"])
    return df


# --------------------------------------------------------------------------- #
# 3. Scoring
# --------------------------------------------------------------------------- #
def score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    raw = sum(df[rule].astype(int) * w for rule, w in RULE_WEIGHTS.items())
    df["risk_score"] = np.where(df["is_risky_type"], raw, 0)   # only TRANSFER/CASH_OUT can score
    return df


# --------------------------------------------------------------------------- #
# 4. Evaluation
# --------------------------------------------------------------------------- #
def rule_table(df: pd.DataFrame) -> pd.DataFrame:
    """Stand-alone quality of each indicator: precision, recall, lift."""
    fraud = df["isFraud"] == 1
    base = fraud.mean()
    rows = []
    for rule in RULE_WEIGHTS:
        hit = df[rule]
        n, tp = int(hit.sum()), int((hit & fraud).sum())
        precision = tp / n if n else 0.0
        rows.append({"rule": rule, "alerts": n, "fraud_caught": tp,
                     "precision": precision, "recall": tp / fraud.sum(),
                     "lift": precision / base})
    legacy = df["isFlaggedFraud"] == 1
    n, tp = int(legacy.sum()), int((legacy & fraud).sum())
    rows.append({"rule": "legacy_isFlaggedFraud", "alerts": n, "fraud_caught": tp,
                 "precision": tp / n if n else 0.0, "recall": tp / fraud.sum(),
                 "lift": (tp / n if n else 0.0) / base})
    return pd.DataFrame(rows).sort_values("recall", ascending=False).reset_index(drop=True)


def threshold_sweep(df: pd.DataFrame, review_cost: float) -> pd.DataFrame:
    """For every score threshold: workload, precision, recall and net benefit.

    Loss is counted once per fraud FLOW. A drained account (TRANSFER) and the mule's
    CASH_OUT move the same money, so a flow counts as caught if EITHER leg is alerted,
    and its amount is counted once.
    """
    fraud = df["isFraud"] == 1
    total_fraud = int(fraud.sum())

    f = df.loc[fraud, ["type", "nameOrig", "nameDest", "amount"]]
    mule = np.where(f["type"] == "TRANSFER", f["nameDest"], f["nameOrig"])
    flow_key = pd.Series(mule + "|" + f["amount"].astype(str), index=f.index)
    flow_amount = f["amount"].groupby(flow_key).first()
    total_flows = len(flow_amount)

    rows = []
    for thr in range(1, int(df["risk_score"].max()) + 1):
        alert = df["risk_score"] >= thr
        n = int(alert.sum())
        if n == 0:
            continue
        tp = int((alert & fraud).sum())
        caught_flows = flow_key[alert[fraud]].unique()
        caught_amt = float(flow_amount.loc[caught_flows].sum())
        p, r = tp / n, tp / total_fraud
        rows.append({"threshold": thr, "alerts": n, "fraud_caught": tp,
                     "precision": p, "recall": r,
                     "f1": 2 * p * r / (p + r) if (p + r) else 0.0,
                     "flow_recall": len(caught_flows) / total_flows,
                     "fraud_amount_caught": caught_amt,
                     "review_cost": n * review_cost,
                     "net_benefit": caught_amt - n * review_cost})
    return pd.DataFrame(rows)


def cost_sensitivity(sweep: pd.DataFrame, costs=(25, 500, 2_000, 10_000, 50_000)) -> pd.DataFrame:
    """How does the best threshold move as the assumed cost per alert changes?"""
    rows = []
    for c in costs:
        nb = sweep["fraud_amount_caught"] - sweep["alerts"] * c
        b = sweep.loc[nb.idxmax()]
        rows.append({"cost_per_alert": c, "best_threshold": int(b["threshold"]),
                     "alerts": int(b["alerts"]), "precision": b["precision"],
                     "recall": b["recall"], "net_benefit": nb.max()})
    return pd.DataFrame(rows)


def capacity_view(df: pd.DataFrame, shares=(0.0025, 0.005, 0.01)) -> pd.DataFrame:
    """If analysts can only review the top K% of transactions, what do they catch?"""
    ranked = df.sort_values(["risk_score", "amount"], ascending=False)
    total_fraud = int(df["isFraud"].sum())
    rows = []
    for s in shares:
        k = int(len(df) * s)
        top = ranked.head(k)
        tp = int(top["isFraud"].sum())
        rows.append({"review_capacity": f"top {s:.2%}", "reviewed": k,
                     "fraud_caught": tp, "precision": tp / k, "recall": tp / total_fraud})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 5. Charts
# --------------------------------------------------------------------------- #
def make_charts(df, sweep, best, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)

    by_type = df.groupby("type")["isFraud"].mean().mul(100).sort_values()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    by_type.plot.barh(ax=ax)
    ax.set_xlabel("Fraud rate (%)")
    ax.set_title("Fraud is concentrated in TRANSFER and CASH_OUT")
    fig.tight_layout()
    fig.savefig(outdir / "01_fraud_rate_by_type.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(sweep["threshold"], sweep["precision"], marker="o", label="Precision")
    ax.plot(sweep["threshold"], sweep["recall"], marker="o", label="Recall")
    ax.set_xlabel("Score threshold (alert if score >= threshold)")
    ax.set_ylabel("Share")
    ax.set_title("Precision vs recall as the threshold moves")
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "02_precision_recall_by_threshold.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(sweep["threshold"], sweep["net_benefit"] / 1e6, marker="o")
    ax.axvline(best["threshold"], linestyle="--", color="grey")
    ax.set_xlabel("Score threshold")
    ax.set_ylabel("Net benefit (millions)")
    ax.set_title(f"Net benefit peaks at threshold {int(best['threshold'])}")
    fig.tight_layout()
    fig.savefig(outdir / "03_net_benefit_by_threshold.png", dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "sample_transactions.csv")
    ap.add_argument("--review-cost", type=float, default=2000.0,
                    help="Assumed all-in cost of one alert: analyst time + customer friction "
                         "(same units as amount; PaySim units are not real dollars)")
    ap.add_argument("--outdir", type=Path, default=ROOT / "reports")
    a = ap.parse_args()

    df, log = load_and_clean(a.data)
    print("\nCLEANING LOG")
    for k, v in log.items():
        print(f"  {k:<30}{v:>12,}")

    df = score(add_risk_indicators(df))
    print(f"\nFraud rate: {df['isFraud'].mean():.3%}  "
          f"({int(df['isFraud'].sum()):,} of {len(df):,} transactions)")

    rules = rule_table(df)
    sweep = threshold_sweep(df, a.review_cost)
    best = sweep.loc[sweep["net_benefit"].idxmax()]
    cap = capacity_view(df)
    sens = cost_sensitivity(sweep)

    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    print("\nINDICATOR QUALITY (stand-alone)\n", rules.to_string(index=False))
    print("\nTHRESHOLD SWEEP\n", sweep.to_string(index=False))
    print(f"\nBEST THRESHOLD by net benefit @ {a.review_cost:.0f} per alert: {int(best['threshold'])}  "
          f"(alerts={int(best['alerts']):,}, precision={best['precision']:.1%}, recall={best['recall']:.1%})")
    print("\nCOST SENSITIVITY: best threshold under different cost-per-alert assumptions\n",
          sens.to_string(index=False))
    print("\nIF ANALYSTS CAN ONLY REVIEW A FIXED SHARE\n", cap.to_string(index=False))

    a.outdir.mkdir(parents=True, exist_ok=True)
    rules.to_csv(a.outdir / "indicator_quality.csv", index=False)
    sweep.to_csv(a.outdir / "threshold_sweep.csv", index=False)
    sens.to_csv(a.outdir / "cost_sensitivity.csv", index=False)
    cols = ["step", "type", "amount", "nameOrig", "nameDest", "risk_score", "isFraud"]
    df[df["risk_score"] >= best["threshold"]].sort_values("risk_score", ascending=False)[cols] \
        .to_csv(a.outdir / "flagged_transactions.csv", index=False)
    make_charts(df, sweep, best, a.outdir / "figures")
    print(f"\nSaved tables and charts to {a.outdir}/")


if __name__ == "__main__":
    main()
