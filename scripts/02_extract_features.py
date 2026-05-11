import pandas as pd
import numpy as np
from datetime import timedelta
import os

# Configuration
INPUT_FILE = 'data/raw/star_schema.xlsx'
OUTPUT_FILE = 'data/processed/transactions_with_features.xlsx'


def engineer_features(df_tx, df_acc):
    print("Initializing state dictionaries...")

    # 1. State Trackers
    account_balances = dict(zip(df_acc['account_id'], df_acc['initial_deposit']))
    last_credit_time = {}
    last_debit_time = {}
    known_payees = set()
    history_7d = {acc: [] for acc in df_acc['account_id']}

    # 2. Output lists
    sender_bal_before = []
    receiver_bal_before = []
    time_since_last_tx = []
    dwell_time = []
    is_first_payee = []
    in_out_ratios = []

    print("Processing chronological ledger to extract features...")

    df_tx['transaction_timestamp'] = pd.to_datetime(df_tx['transaction_timestamp'])
    df_tx = df_tx.sort_values('transaction_timestamp').reset_index(drop=True)

    for index, row in df_tx.iterrows():
        sender = row['sender_account_id']
        receiver = row['receiver_account_id']
        amt = row['amount']
        ts = row['transaction_timestamp']

        # A. Balances BEFORE transaction
        sender_bal_before.append(account_balances.get(sender, 0.0))
        receiver_bal_before.append(account_balances.get(receiver, 0.0))

        # B. Time since last outgoing tx (seconds)
        if sender in last_debit_time:
            time_since_last_tx.append((ts - last_debit_time[sender]).total_seconds())
        else:
            time_since_last_tx.append(-1)

        # C. Dwell time: time since sender last received funds (minutes)
        if sender in last_credit_time:
            dwell_time.append(round((ts - last_credit_time[sender]).total_seconds() / 60.0, 2))
        else:
            dwell_time.append(-1.0)

        # D. First time payee
        pair = (sender, receiver)
        is_first_payee.append(pair not in known_payees)
        known_payees.add(pair)

        # E. 7-day in/out ratio
        cutoff_time = ts - timedelta(days=7)
        if sender in history_7d:
            history_7d[sender] = [x for x in history_7d[sender] if x['time'] >= cutoff_time]
            credits_7d = sum(x['amount'] for x in history_7d[sender] if x['type'] == 'credit')
            debits_7d = sum(x['amount'] for x in history_7d[sender] if x['type'] == 'debit')
            in_out_ratios.append(round(credits_7d / debits_7d, 4) if debits_7d > 0 else 0.0)
        else:
            in_out_ratios.append(0.0)

        # F. Update states
        account_balances[sender] -= amt
        if receiver.startswith('ACC_'):
            account_balances[receiver] = account_balances.get(receiver, 0.0) + amt
            last_credit_time[receiver] = ts
            history_7d[receiver].append({'time': ts, 'type': 'credit', 'amount': amt})

        last_debit_time[sender] = ts
        if sender in history_7d:
            history_7d[sender].append({'time': ts, 'type': 'debit', 'amount': amt})

    df_tx['sender_balance_before_tx'] = sender_bal_before
    df_tx['receiver_balance_before_tx'] = receiver_bal_before
    df_tx['time_since_last_tx_seconds'] = time_since_last_tx
    df_tx['dwell_time_minutes'] = dwell_time
    df_tx['is_first_time_payee'] = is_first_payee
    df_tx['in_out_ratio_7d'] = in_out_ratios

    # -------------------------------------------------------------------------
    # FIX: Rolling window features — use transform() to avoid merge row explosion
    # The old approach merged on (sender_account_id, transaction_timestamp).
    # When multiple txns share the same sender+timestamp, the merge creates
    # duplicate rows, corrupting row count and all downstream calculations
    # (especially expanding z-score which depends on correct row order).
    # transform() operates in-place on the original index — no duplicates.
    # -------------------------------------------------------------------------
    print("Calculating rolling window aggregations (fixed — no merge)...")

    df_tx = df_tx.set_index('transaction_timestamp')

    df_tx['daily_tx_count_sender'] = (
        df_tx.groupby('sender_account_id')['amount']
        .transform(lambda x: x.rolling('24h').count())
    )

    df_tx['burst_score'] = (
        df_tx.groupby('sender_account_id')['amount']
        .transform(lambda x: x.rolling('1h').count())
        .fillna(1)
        .astype(int)
    )

    df_tx = df_tx.reset_index()

    # -------------------------------------------------------------------------
    # Account Age — sender's account age at moment of transaction
    # NOTE: For is_mule_tx=True Hop 1, sender is the VICTIM (normal account),
    # so account_age_days is high even though is_mule_tx=True.
    # Added 'sender_is_mule_account' flag to filter correctly in Tableau:
    #   use account_age_days WHERE sender_is_mule_account = True for Burner analysis.
    # -------------------------------------------------------------------------
    acc_creation = dict(zip(df_acc['account_id'], pd.to_datetime(df_acc['account_creation_date'])))
    acc_is_mule = dict(zip(df_acc['account_id'], df_acc['is_mule_flag']))

    df_tx['account_age_days'] = df_tx.apply(
        lambda r: (r['transaction_timestamp'] - acc_creation[r['sender_account_id']]).days
        if r['sender_account_id'] in acc_creation else -1,
        axis=1
    )

    # NEW: flag whether the SENDER is a mule account (not just whether the tx is mule-labeled)
    df_tx['sender_is_mule_account'] = df_tx['sender_account_id'].map(
        lambda x: acc_is_mule.get(x, False)
    )

    # -------------------------------------------------------------------------
    # Amount Z-Score — expanding mean/std per sender (no future leakage)
    # This is now correct because transform() above didn't duplicate rows.
    # -------------------------------------------------------------------------
    print("Calculating amount Z-Scores...")

    expanding_mean = (
        df_tx.groupby('sender_account_id')['amount']
        .expanding()
        .mean()
        .reset_index(level=0, drop=True)
    )
    expanding_std = (
        df_tx.groupby('sender_account_id')['amount']
        .expanding()
        .std()
        .reset_index(level=0, drop=True)
        .fillna(1)
    )

    df_tx['amount_z_score'] = ((df_tx['amount'] - expanding_mean) / expanding_std).round(2).fillna(0)

    # -------------------------------------------------------------------------
    # Derived bucket columns for Tableau binning
    # -------------------------------------------------------------------------
    df_tx['dwell_time_bin'] = pd.cut(
        df_tx['dwell_time_minutes'].clip(lower=0),
        bins=[-1, 0, 10, 60, 1440, float('inf')],
        labels=['First TX', '<10 min', '10–60 min', '1–24 hrs', '>24 hrs']
    )

    df_tx['burst_bucket'] = pd.cut(
        df_tx['burst_score'],
        bins=[0, 1, 3, 6, float('inf')],
        labels=['1', '2–3', '4–6', '7+']
    )

    df_tx['z_score_bucket'] = pd.cut(
        df_tx['amount_z_score'],
        bins=[-float('inf'), -1, 1, 2, 3, float('inf')],
        labels=['< -1σ', '-1–1σ', '1–2σ', '2–3σ', '> 3σ']
    )

    return df_tx


if __name__ == "__main__":
    print(f"Loading raw data from {INPUT_FILE}...")
    df_accounts = pd.read_excel(INPUT_FILE, sheet_name='dim_accounts')
    df_transactions = pd.read_excel(INPUT_FILE, sheet_name='fact_transactions')

    df_model_ready = engineer_features(df_transactions, df_accounts)

    directory = os.path.dirname(OUTPUT_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)

    print(f"Saving to {OUTPUT_FILE}...")
    df_model_ready.to_excel(OUTPUT_FILE, index=False)

    print("\n--- Validation: Mule vs Normal feature medians ---")
    cols = ['amount', 'is_mule_tx', 'dwell_time_minutes', 'in_out_ratio_7d',
            'burst_score', 'account_age_days', 'amount_z_score', 'sender_is_mule_account']
    summary = df_model_ready[cols].groupby('is_mule_tx').median(numeric_only=True)
    print(summary.T.to_string())
    print("\nDone.")
