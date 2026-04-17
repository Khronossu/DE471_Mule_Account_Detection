import pandas as pd
import numpy as np
from datetime import timedelta
import os # Added for directory management

# Configuration
INPUT_FILE = 'data_ver2/ver_2_data.xlsx'
OUTPUT_FILE = 'data_ver2/ver_2_data_with_features.xlsx'

def engineer_features(df_tx, df_acc):
    print("Initializing state dictionaries...")
    
    # 1. State Trackers
    # Initialize balances with their starting deposits
    account_balances = dict(zip(df_acc['account_id'], df_acc['initial_deposit']))
    
    # Track the exact datetime an account last received money
    last_credit_time = {} 
    
    # Track time of last outgoing transfer for velocity
    last_debit_time = {}
    
    # Track sets of (sender, receiver) to check for first-time payees
    known_payees = set()
    
    # Track transaction history for 7-day rolling ratios
    # Format: {account_id: [{'time': datetime, 'type': 'credit'/'debit', 'amount': float}]}
    history_7d = {acc: [] for acc in df_acc['account_id']}

    # 2. Prepare output lists for the new columns
    sender_bal_before = []
    receiver_bal_before = []
    time_since_last_tx = []
    dwell_time = []
    is_first_payee = []
    in_out_ratios = []
    
    print("Processing chronological ledger to extract features...")
    
    # Ensure data is perfectly sorted by time before iterating
    df_tx['transaction_timestamp'] = pd.to_datetime(df_tx['transaction_timestamp'])
    df_tx = df_tx.sort_values('transaction_timestamp').reset_index(drop=True)
    
    # 3. Iterate through the ledger (Fast for 20k rows)
    for index, row in df_tx.iterrows():
        sender = row['sender_account_id']
        receiver = row['receiver_account_id']
        amt = row['amount']
        ts = row['transaction_timestamp']
        
        # --- A. Record Balances BEFORE the transaction ---
        s_bal = account_balances.get(sender, 0.0)
        r_bal = account_balances.get(receiver, 0.0)
        sender_bal_before.append(s_bal)
        receiver_bal_before.append(r_bal)
        
        # --- B. Velocity: Time Since Last Tx (Sender) ---
        if sender in last_debit_time:
            time_diff = (ts - last_debit_time[sender]).total_seconds()
        else:
            time_diff = -1 # -1 indicates this is their very first transaction
        time_since_last_tx.append(time_diff)
        
        # --- C. Dwell Time: Time since sender last received funds ---
        if sender in last_credit_time:
            dwell_mins = (ts - last_credit_time[sender]).total_seconds() / 60.0
        else:
            dwell_mins = -1.0 # -1 indicates they've never received a tracked credit
        dwell_time.append(dwell_mins)
        
        # --- D. First Time Payee ---
        pair = (sender, receiver)
        if pair in known_payees:
            is_first_payee.append(False)
        else:
            is_first_payee.append(True)
            known_payees.add(pair)
            
        # --- E. 7-Day In/Out Ratio ---
        # Clean up old history (older than 7 days) for the sender
        cutoff_time = ts - timedelta(days=7)
        if sender in history_7d:
            history_7d[sender] = [x for x in history_7d[sender] if x['time'] >= cutoff_time]
            
            credits_7d = sum(x['amount'] for x in history_7d[sender] if x['type'] == 'credit')
            debits_7d = sum(x['amount'] for x in history_7d[sender] if x['type'] == 'debit')
            
            # Avoid division by zero
            ratio = round(credits_7d / debits_7d, 4) if debits_7d > 0 else 0.0
        else:
            ratio = 0.0
        in_out_ratios.append(ratio)
        
        # --- F. Update States for the NEXT rows ---
        account_balances[sender] -= amt
        # Only update receiver balance if it's not an external wallet
        if receiver.startswith('ACC_'): 
            account_balances[receiver] += amt
            last_credit_time[receiver] = ts
            history_7d[receiver].append({'time': ts, 'type': 'credit', 'amount': amt})
            
        last_debit_time[sender] = ts
        if sender in history_7d:
            history_7d[sender].append({'time': ts, 'type': 'debit', 'amount': amt})

    # 4. Assign lists back to the dataframe
    df_tx['sender_balance_before_tx'] = sender_bal_before
    df_tx['receiver_balance_before_tx'] = receiver_bal_before
    df_tx['time_since_last_tx_seconds'] = time_since_last_tx
    df_tx['dwell_time_minutes'] = [round(x, 2) for x in dwell_time]
    df_tx['is_first_time_payee'] = is_first_payee
    df_tx['in_out_ratio_7d'] = in_out_ratios
    
    # 5. Pandas Native Vectorized Operations for the remaining features
    print("Calculating rolling window aggregations and Z-Scores...")
    
    # Daily Tx Count (Rolling 24h count per sender)
    df_indexed = df_tx.set_index('transaction_timestamp')
    rolling_counts_24h = df_indexed.groupby('sender_account_id')['transaction_id'].rolling('24h').count().reset_index()
    df_tx = pd.merge(df_tx, rolling_counts_24h, on=['sender_account_id', 'transaction_timestamp'], how='left')
    df_tx.rename(columns={'transaction_id_y': 'daily_tx_count_sender', 'transaction_id_x': 'transaction_id'}, inplace=True)

    # Burst Score — rolling 1h count per sender (detects sudden transfer bursts, e.g. Hop 2 split-transfers)
    rolling_counts_1h = df_indexed.groupby('sender_account_id')['transaction_id'].rolling('1h').count().reset_index()
    df_tx = pd.merge(df_tx, rolling_counts_1h, on=['sender_account_id', 'transaction_timestamp'], how='left')
    df_tx.rename(columns={'transaction_id_y': 'burst_score', 'transaction_id_x': 'transaction_id'}, inplace=True)
    df_tx['burst_score'] = df_tx['burst_score'].fillna(1).astype(int)

    # Account Age (days) at the moment of transaction — critical Burner indicator
    acc_creation = dict(zip(df_acc['account_id'], pd.to_datetime(df_acc['account_creation_date'])))
    df_tx['account_age_days'] = df_tx.apply(
        lambda r: (r['transaction_timestamp'] - acc_creation[r['sender_account_id']]).days
        if r['sender_account_id'] in acc_creation else -1,
        axis=1
    )
    
    # Amount Z-Score (Deviation from the sender's expanding historical mean)
    # Using expanding() ensures we only look at past transactions, avoiding data leakage from the future
    expanding_mean = df_tx.groupby('sender_account_id')['amount'].expanding().mean().reset_index(level=0, drop=True)
    expanding_std = df_tx.groupby('sender_account_id')['amount'].expanding().std().reset_index(level=0, drop=True)
    
    # Fill NaN std deviations (happens on the first transaction) with 1 to avoid division by zero
    expanding_std = expanding_std.fillna(1) 
    
    df_tx['amount_z_score'] = round((df_tx['amount'] - expanding_mean) / expanding_std, 2)
    # Fill NaN z-scores (happens on the first transaction) with 0
    df_tx['amount_z_score'] = df_tx['amount_z_score'].fillna(0)
    
    return df_tx

if __name__ == "__main__":
    # Load the data generated from Step 1
    print(f"Loading raw data from {INPUT_FILE}...")
    df_accounts = pd.read_excel(INPUT_FILE, sheet_name='dim_accounts')
    df_transactions = pd.read_excel(INPUT_FILE, sheet_name='fact_transactions')
    
    # Run the feature engineering
    df_model_ready = engineer_features(df_transactions, df_accounts)
    
    # Ensure the target directory exists before saving
    directory = os.path.dirname(OUTPUT_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)
        print(f"Verified directory '{directory}/' exists.")
    
    # Save to a new Excel file suitable for BI tools
    print(f"Saving final dataset to {OUTPUT_FILE}...")
    df_model_ready.to_excel(OUTPUT_FILE, index=False) # Changed from .to_csv to .to_excel
    
    print("\n--- Data Pipeline Complete. Sample of new features ---")
    columns_to_show = ['amount', 'is_mule_tx', 'dwell_time_minutes', 'in_out_ratio_7d', 'burst_score', 'account_age_days', 'amount_z_score']
    print(df_model_ready[columns_to_show].tail(10))