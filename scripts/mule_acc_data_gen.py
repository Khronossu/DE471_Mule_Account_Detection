import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta
import os # Added os module for directory management

# Initialize
fake = Faker()
Faker.seed(42)
np.random.seed(42)

# --- Configuration ---
TOTAL_CUSTOMERS = 1000
MULE_COUNT = 30
TOTAL_TX = 20000
SIMULATION_DAYS = 180
EXCEL_FILENAME = 'data/synthetic_fraud_dataset_before_feature_extraction.xlsx'

def generate_dimensions():
    print(f"Generating {TOTAL_CUSTOMERS} customers and accounts...")
    
    customers = []
    accounts = []
    
    employment_types = ['Salaried', 'Student', 'Unemployed', 'Self-Employed']
    kyc_statuses = ['Verified', 'Verified', 'Verified', 'Pending', 'Rejected'] 
    
    for i in range(TOTAL_CUSTOMERS):
        customer_id = f"CUST_{str(i).zfill(4)}"
        
        customers.append({
            'customer_id': customer_id,
            'age': np.random.randint(18, 75),
            'employment_status': np.random.choice(employment_types, p=[0.6, 0.2, 0.05, 0.15]),
            'kyc_status': np.random.choice(kyc_statuses),
            'risk_segment': np.random.choice(['Low', 'Medium', 'High'], p=[0.8, 0.15, 0.05])
        })
        
        account_id = f"ACC_{str(i).zfill(4)}"
        days_ago = np.random.randint(SIMULATION_DAYS + 1, SIMULATION_DAYS + 730) 
        creation_date = datetime.now() - timedelta(days=days_ago)
        
        accounts.append({
            'account_id': account_id,
            'customer_id': customer_id,
            'account_creation_date': creation_date,
            'initial_deposit': round(np.random.uniform(50, 5000), 2),
            'is_mule_flag': False,
            'mule_type': 'None'
        })
        
    df_customers = pd.DataFrame(customers)
    df_accounts = pd.DataFrame(accounts)
    
    # Inject Mule Ground Truth
    mule_indices = np.random.choice(df_accounts.index, MULE_COUNT, replace=False)
    df_accounts.loc[mule_indices, 'is_mule_flag'] = True
    
    # Split mules into Burners (new) and Sleepers (old)
    burner_indices = mule_indices[:15] 
    sleeper_indices = mule_indices[15:]
    
    df_accounts.loc[burner_indices, 'mule_type'] = 'Burner'
    df_accounts.loc[sleeper_indices, 'mule_type'] = 'Sleeper'
    
    # Overwrite Burner creation dates to be very recent
    recent_dates = [(datetime.now() - timedelta(days=np.random.randint(1, 10))) for _ in range(15)]
    df_accounts.loc[burner_indices, 'account_creation_date'] = recent_dates

    return df_customers, df_accounts

def generate_transactions(df_accounts):
    print(f"Generating {TOTAL_TX} transactions (Normal + Mule Rings)...")
    
    normal_accounts = df_accounts[df_accounts['is_mule_flag'] == False]['account_id'].tolist()
    sleeper_mules = df_accounts[df_accounts['mule_type'] == 'Sleeper']['account_id'].tolist()
    burner_mules = df_accounts[df_accounts['mule_type'] == 'Burner']['account_id'].tolist()
    
    transactions = []
    start_date = datetime.now() - timedelta(days=SIMULATION_DAYS)
    
    # 1. Generate Normal Transactions (Vectorized for speed)
    normal_tx_count = TOTAL_TX - 500 
    
    senders = np.random.choice(normal_accounts, normal_tx_count)
    receivers = np.random.choice(normal_accounts, normal_tx_count)
    
    # Prevent self-transfers
    for i in range(len(senders)):
        if senders[i] == receivers[i]:
            receivers[i] = np.random.choice(normal_accounts)
            
    amounts = np.round(np.random.uniform(10, 1500, normal_tx_count), 2)
    methods = np.random.choice(['Mobile App', 'Web', 'API', 'ATM'], normal_tx_count, p=[0.7, 0.2, 0.05, 0.05])
    
    random_seconds = np.random.randint(0, SIMULATION_DAYS * 24 * 3600, normal_tx_count)
    
    for i in range(normal_tx_count):
        transactions.append({
            'transaction_id': f"TXN_{str(i).zfill(6)}",
            'sender_account_id': senders[i],
            'receiver_account_id': receivers[i],
            'amount': amounts[i],
            'transaction_timestamp': start_date + timedelta(seconds=int(random_seconds[i])),
            'transfer_method': methods[i],
            'is_mule_tx': False
        })
    
    # 2. Generate Mule Rings
    tx_counter = normal_tx_count
    
    for _ in range(20):
        victim = random.choice(normal_accounts)
        sleeper = random.choice(sleeper_mules)
        burners = random.sample(burner_mules, 3) 
        
        attack_time = start_date + timedelta(seconds=random.randint(30 * 24 * 3600, SIMULATION_DAYS * 24 * 3600))
        scam_amount = round(random.uniform(8000, 15000), 2)
        
        # Hop 1
        transactions.append({
            'transaction_id': f"TXN_{str(tx_counter).zfill(6)}",
            'sender_account_id': victim,
            'receiver_account_id': sleeper,
            'amount': scam_amount,
            'transaction_timestamp': attack_time,
            'transfer_method': 'Web',
            'is_mule_tx': True
        })
        tx_counter += 1
        
        # Hop 2
        split_amount = round(scam_amount / 3, 2)
        for burner in burners:
            hop2_time = attack_time + timedelta(minutes=random.randint(5, 15))
            transactions.append({
                'transaction_id': f"TXN_{str(tx_counter).zfill(6)}",
                'sender_account_id': sleeper,
                'receiver_account_id': burner,
                'amount': split_amount,
                'transaction_timestamp': hop2_time,
                'transfer_method': 'API', 
                'is_mule_tx': True
            })
            tx_counter += 1
            
            # Hop 3
            hop3_time = hop2_time + timedelta(minutes=random.randint(2, 5))
            transactions.append({
                'transaction_id': f"TXN_{str(tx_counter).zfill(6)}",
                'sender_account_id': burner,
                'receiver_account_id': 'EXT_CRYPTO_WALLET',
                'amount': split_amount,
                'transaction_timestamp': hop3_time,
                'transfer_method': 'API',
                'is_mule_tx': True
            })
            tx_counter += 1

    df_transactions = pd.DataFrame(transactions)
    df_transactions = df_transactions.sort_values(by='transaction_timestamp').reset_index(drop=True)
    return df_transactions

def save_to_excel(df_cust, df_acc, df_tx):
    # Ensure the target directory exists before saving
    directory = os.path.dirname(EXCEL_FILENAME)
    if directory: # Checks if the path actually has a directory structure (like 'data/')
        os.makedirs(directory, exist_ok=True)
        print(f"Verified directory '{directory}/' exists.")

    print(f"Saving data to {EXCEL_FILENAME}...")
    
    with pd.ExcelWriter(EXCEL_FILENAME, engine='openpyxl') as writer:
        df_cust.to_excel(writer, sheet_name='dim_customers', index=False)
        df_acc.to_excel(writer, sheet_name='dim_accounts', index=False)
        df_tx.to_excel(writer, sheet_name='fact_transactions', index=False)
        
    print("Export complete! You can now open the .xlsx file.")

if __name__ == "__main__":
    dim_customers, dim_accounts = generate_dimensions()
    fact_transactions = generate_transactions(dim_accounts)
    save_to_excel(dim_customers, dim_accounts, fact_transactions)