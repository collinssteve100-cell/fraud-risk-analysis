"""
Generate a synthetic, PaySim-style transaction file so the project runs
end to end without downloading anything.

It mimics the fraud pattern documented for PaySim:
  * fraud occurs only in TRANSFER and CASH_OUT
  * a victim account is drained by a TRANSFER to a "mule" account
  * the mule then CASH_OUTs the same amount within a few hours
  * a small share of legitimate customers also empty their accounts (noise),
    and some fraud is partial, so no single rule is perfect

This is NOT real data. For your portfolio, run the analysis on the real
PaySim dataset (see data/README.md) and report those numbers.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "sample_transactions.csv"


def make(n_rows: int, fraud_pairs: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_pt, n_biz, biz_txns = 150, 25, 15            # legit noise: pass-through pairs, small businesses
    n_extra = 2 * n_pt + n_biz * biz_txns
    n_legit = n_rows - 2 * fraud_pairs - n_extra

    # ---------- legitimate traffic ----------
    types = rng.choice(
        ["PAYMENT", "CASH_OUT", "CASH_IN", "TRANSFER", "DEBIT"],
        size=n_legit, p=[0.34, 0.22, 0.22, 0.18, 0.04],
    )
    mu = {"PAYMENT": 8.5, "CASH_OUT": 11.0, "CASH_IN": 11.2, "TRANSFER": 11.3, "DEBIT": 8.0}
    amount = np.array([rng.lognormal(mu[t], 1.0) for t in types]).round(2)
    # some customers like round amounts
    round_mask = rng.random(n_legit) < 0.05
    amount[round_mask] = np.round(amount[round_mask], -3).clip(min=1000)

    outgoing = types != "CASH_IN"
    old_orig = np.where(outgoing, amount * (1 + rng.exponential(3, n_legit)), rng.lognormal(11, 1.5, n_legit))
    # ~2% of legit TRANSFER / CASH_OUT drain the account too (false-positive noise)
    risky = np.isin(types, ["TRANSFER", "CASH_OUT"])
    drain = risky & (rng.random(n_legit) < 0.02)
    old_orig[drain] = amount[drain]
    old_orig = old_orig.round(2)
    new_orig = np.where(outgoing, old_orig - amount, old_orig + amount).round(2)
    quirk = np.isin(types, ["PAYMENT", "DEBIT"]) & (rng.random(n_legit) < 0.03)
    new_orig[quirk] = old_orig[quirk]               # balance did not move: reconciliation break

    name_orig = ["C%07d" % i for i in rng.integers(1, 150_000, n_legit)]
    merchant_dest = np.isin(types, ["PAYMENT", "DEBIT"])
    name_dest = np.where(
        merchant_dest,
        ["M%07d" % i for i in rng.integers(1, 20_000, n_legit)],
        ["C%07d" % i for i in rng.integers(1, 150_000, n_legit)],
    )
    old_dest = np.where(merchant_dest, 0.0,
                        np.where(rng.random(n_legit) < 0.30, 0.0, rng.lognormal(11, 1.5, n_legit))).round(2)
    new_dest = np.where(merchant_dest, 0.0, old_dest + amount).round(2)

    legit = pd.DataFrame({
        "step": rng.integers(1, 744, n_legit), "type": types, "amount": amount,
        "nameOrig": name_orig, "oldbalanceOrg": old_orig, "newbalanceOrig": new_orig,
        "nameDest": name_dest, "oldbalanceDest": old_dest, "newbalanceDest": new_dest,
        "isFraud": 0,
    })


    # ---------- legit noise that looks a bit like fraud ----------
    # (a) people who receive a transfer and cash out the same amount soon after
    pt_amt = rng.lognormal(10.5, 0.8, n_pt).round(2)
    pt_step = rng.integers(1, 742, n_pt)
    recipients = ["C7%06d" % i for i in range(n_pt)]
    pt_full = rng.random(n_pt) < 0.30
    pt_old = np.where(pt_full, pt_amt, pt_amt * rng.uniform(1.0, 2.5, n_pt)).round(2)
    pt_transfer = pd.DataFrame({
        "step": pt_step, "type": "TRANSFER", "amount": pt_amt,
        "nameOrig": ["C%07d" % i for i in rng.integers(1, 150_000, n_pt)],
        "oldbalanceOrg": (pt_amt * 3).round(2), "newbalanceOrig": (pt_amt * 2).round(2),
        "nameDest": recipients, "oldbalanceDest": 0.0, "newbalanceDest": pt_amt, "isFraud": 0,
    })
    pt_cashout = pd.DataFrame({
        "step": pt_step + rng.integers(0, 3, n_pt), "type": "CASH_OUT", "amount": pt_amt,
        "nameOrig": recipients, "oldbalanceOrg": pt_old, "newbalanceOrig": (pt_old - pt_amt).round(2),
        "nameDest": ["C%07d" % i for i in rng.integers(1, 150_000, n_pt)],
        "oldbalanceDest": 0.0, "newbalanceDest": pt_amt, "isFraud": 0,
    })
    # (b) small businesses that legitimately receive many transfers from many customers
    n_b = n_biz * biz_txns
    b_amt = rng.lognormal(9.5, 0.8, n_b).round(2)
    b_old = (b_amt * rng.uniform(1.5, 6, n_b)).round(2)
    biz = pd.DataFrame({
        "step": rng.integers(1, 744, n_b), "type": "TRANSFER", "amount": b_amt,
        "nameOrig": ["C%07d" % i for i in rng.integers(1, 150_000, n_b)],
        "oldbalanceOrg": b_old, "newbalanceOrig": (b_old - b_amt).round(2),
        "nameDest": ["C8%06d" % i for i in rng.integers(0, n_biz, n_b)],
        "oldbalanceDest": rng.lognormal(11, 1.0, n_b).round(2), "isFraud": 0,
    })
    biz["newbalanceDest"] = (biz.oldbalanceDest + b_amt).round(2)

    # ---------- fraud: TRANSFER to mule, then CASH_OUT ----------
    n_mules = 200
    mules = ["C9%06d" % i for i in range(n_mules)]
    w = 1 / np.arange(1, n_mules + 1) ** 0.8          # a few mules receive most of the money
    mule_pick = rng.choice(mules, size=fraud_pairs, p=w / w.sum())

    f_amount = rng.lognormal(12.5, 1.0, fraud_pairs).clip(max=10_000_000).round(2)
    rmask = rng.random(fraud_pairs) < 0.20
    f_amount[rmask] = np.round(f_amount[rmask], -3).clip(min=1000)
    full_drain = rng.random(fraud_pairs) < 0.80       # 20% of fraud leaves a remainder
    f_old = np.where(full_drain, f_amount, f_amount * rng.uniform(1.2, 3.0, fraud_pairs)).round(2)
    f_step = rng.integers(1, 742, fraud_pairs)
    dest_zero = rng.random(fraud_pairs) < 0.70

    f_transfer = pd.DataFrame({
        "step": f_step, "type": "TRANSFER", "amount": f_amount,
        "nameOrig": ["C%07d" % i for i in rng.integers(1, 150_000, fraud_pairs)],
        "oldbalanceOrg": f_old, "newbalanceOrig": (f_old - f_amount).round(2),
        "nameDest": mule_pick,
        "oldbalanceDest": np.where(dest_zero, 0.0, rng.lognormal(10, 1.5, fraud_pairs)).round(2),
        "isFraud": 1,
    })
    f_transfer["newbalanceDest"] = (f_transfer.oldbalanceDest + f_amount).round(2)

    f_cashout = pd.DataFrame({
        "step": f_step + rng.integers(0, 3, fraud_pairs), "type": "CASH_OUT", "amount": f_amount,
        "nameOrig": mule_pick, "oldbalanceOrg": f_amount, "newbalanceOrig": 0.0,
        "nameDest": ["C%07d" % i for i in rng.integers(1, 150_000, fraud_pairs)],
        "oldbalanceDest": np.where(rng.random(fraud_pairs) < 0.6, 0.0, rng.lognormal(10, 1.5, fraud_pairs)).round(2),
        "isFraud": 1,
    })
    f_cashout["newbalanceDest"] = (f_cashout.oldbalanceDest + f_amount).round(2)

    df = pd.concat([legit, pt_transfer, pt_cashout, biz, f_transfer, f_cashout], ignore_index=True)
    # mimics PaySim's legacy business rule, which catches almost nothing
    df["isFlaggedFraud"] = ((df.type == "TRANSFER") & (df.amount > 5_000_000)).astype(int)
    df = df.sort_values("step", kind="stable").reset_index(drop=True)
    return df[["step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
               "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud", "isFlaggedFraud"]]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=200_000)
    ap.add_argument("--fraud-pairs", type=int, default=600)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    d = make(a.rows, a.fraud_pairs, a.seed)
    d.to_csv(OUT, index=False)
    print(f"Wrote {len(d):,} rows to {OUT}  |  fraud rate = {d.isFraud.mean():.3%}")
