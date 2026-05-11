import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta
import os

# Initialize
fake = Faker()
Faker.seed(42)
np.random.seed(42)
random.seed(42)

# --- Configuration ---
TOTAL_CUSTOMERS = 1000
NUM_RINGS = 20
SLEEPERS_PER_RING = 1
BURNERS_PER_RING = 3
SLEEPER_COUNT = NUM_RINGS * SLEEPERS_PER_RING   # 20
BURNER_COUNT = NUM_RINGS * BURNERS_PER_RING     # 60
MULE_COUNT = SLEEPER_COUNT + BURNER_COUNT       # 80 — non-overlapping rings
TOTAL_TX = 20000
SIMULATION_DAYS = 180
EXCEL_FILENAME = 'data/raw/star_schema.xlsx'

MULE_HOUR_WEIGHTS = np.array([
    8, 9, 10, 10, 9, 7, 4, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 3, 4, 5, 6
], dtype=float)
MULE_HOUR_WEIGHTS = MULE_HOUR_WEIGHTS / MULE_HOUR_WEIGHTS.sum()


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

    mule_indices = np.random.choice(df_accounts.index, MULE_COUNT, replace=False)
    df_accounts.loc[mule_indices, 'is_mule_flag'] = True

    sleeper_indices = mule_indices[:SLEEPER_COUNT]
    burner_indices = mule_indices[SLEEPER_COUNT:]

    df_accounts.loc[sleeper_indices, 'mule_type'] = 'Sleeper'
    df_accounts.loc[burner_indices, 'mule_type'] = 'Burner'

    # Burners get placeholder dates here — overwritten per-ring in generate_transactions()
    placeholder_dates = [(datetime.now() - timedelta(days=1)) for _ in range(BURNER_COUNT)]
    df_accounts.loc[burner_indices, 'account_creation_date'] = placeholder_dates

    burner_customer_ids = df_accounts.loc[burner_indices, 'customer_id'].values
    df_customers.loc[df_customers['customer_id'].isin(burner_customer_ids), 'kyc_status'] = \
        np.random.choice(['Pending', 'Rejected'], size=BURNER_COUNT, p=[0.7, 0.3])
    df_accounts.loc[burner_indices, 'initial_deposit'] = np.round(
        np.random.uniform(50, 300, BURNER_COUNT), 2
    )

    return df_customers, df_accounts


def _mule_timestamp(start_date):
    base_day = start_date + timedelta(days=random.randint(30, SIMULATION_DAYS - 1))
    hour = int(np.random.choice(24, p=MULE_HOUR_WEIGHTS))
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return base_day.replace(hour=hour, minute=minute, second=second, microsecond=0)


def generate_transactions(df_accounts):
    print(f"Generating {TOTAL_TX} transactions (Normal + {NUM_RINGS} Non-overlapping Mule Rings)...")

    normal_accounts = df_accounts[df_accounts['is_mule_flag'] == False]['account_id'].tolist()
    sleeper_mules = df_accounts[df_accounts['mule_type'] == 'Sleeper']['account_id'].tolist()
    burner_mules = df_accounts[df_accounts['mule_type'] == 'Burner']['account_id'].tolist()

    assert len(sleeper_mules) == SLEEPER_COUNT
    assert len(burner_mules) == BURNER_COUNT

    transactions = []
    start_date = datetime.now() - timedelta(days=SIMULATION_DAYS)

    mule_tx_total = NUM_RINGS * (1 + BURNERS_PER_RING + BURNERS_PER_RING)
    normal_tx_count = TOTAL_TX - mule_tx_total

    senders = np.random.choice(normal_accounts, normal_tx_count)
    receivers = np.random.choice(normal_accounts, normal_tx_count)
    for i in range(len(senders)):
        if senders[i] == receivers[i]:
            receivers[i] = np.random.choice(normal_accounts)

    amounts = np.round(np.random.lognormal(mean=5.7, sigma=0.9, size=normal_tx_count), 2)
    amounts = np.clip(amounts, 10, 50000)
    methods = np.random.choice(
        ['Mobile App', 'Web', 'API', 'ATM'], normal_tx_count, p=[0.7, 0.2, 0.05, 0.05]
    )
    random_seconds = np.random.randint(0, SIMULATION_DAYS * 24 * 3600, normal_tx_count)

    for i in range(normal_tx_count):
        transactions.append({
            'transaction_id': f"TXN_{str(i).zfill(6)}",
            'sender_account_id': senders[i],
            'receiver_account_id': receivers[i],
            'amount': float(amounts[i]),
            'transaction_timestamp': start_date + timedelta(seconds=int(random_seconds[i])),
            'transfer_method': methods[i],
            'is_mule_tx': False
        })

    tx_counter = normal_tx_count
    random.shuffle(sleeper_mules)
    random.shuffle(burner_mules)
    sleeper_iter = iter(sleeper_mules)
    burner_iter = iter(burner_mules)

    for ring_idx in range(NUM_RINGS):
        victim = random.choice(normal_accounts)
        sleeper = next(sleeper_iter)
        burners = [next(burner_iter) for _ in range(BURNERS_PER_RING)]

        attack_time = _mule_timestamp(start_date)
        scam_amount = round(random.uniform(8000, 15000), 2)

        # FIX: burner creation date set 1-29 days BEFORE attack — inside ring loop
        for burner in burners:
            burner_creation = attack_time - timedelta(days=random.randint(1, 29))
            df_accounts.loc[df_accounts['account_id'] == burner, 'account_creation_date'] = burner_creation

        # Hop 1: Victim → Sleeper
        transactions.append({
            'transaction_id': f"TXN_{str(tx_counter).zfill(6)}",
            'sender_account_id': victim,
            'receiver_account_id': sleeper,
            'amount': scam_amount,
            'transaction_timestamp': attack_time,
            'transfer_method': random.choice(['Web', 'Mobile App']),
            'is_mule_tx': True
        })
        tx_counter += 1

        # Hop 2: Sleeper → Burners (burst window 2-15 min)
        split_amount = round(scam_amount / BURNERS_PER_RING, 2)
        for burner in burners:
            hop2_time = attack_time + timedelta(minutes=random.randint(2, 15))
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

            # Hop 3: Burner → Crypto Wallet (fast dwell 1-5 min)
            hop3_time = hop2_time + timedelta(minutes=random.randint(1, 5))
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
    df_transactions['transaction_id'] = [f"TXN_{str(i).zfill(6)}" for i in range(len(df_transactions))]
    return df_transactions, df_accounts


def save_to_excel(df_cust, df_acc, df_tx):
    directory = os.path.dirname(EXCEL_FILENAME)
    if directory:
        os.makedirs(directory, exist_ok=True)
        print(f"Verified directory '{directory}/' exists.")

    print(f"Saving data to {EXCEL_FILENAME}...")
    with pd.ExcelWriter(EXCEL_FILENAME, engine='openpyxl') as writer:
        df_cust.to_excel(writer, sheet_name='dim_customers', index=False)
        df_acc.to_excel(writer, sheet_name='dim_accounts', index=False)
        df_tx.to_excel(writer, sheet_name='fact_transactions', index=False)

    print("Export complete!")
    print(f"  Customers: {len(df_cust)} | Accounts: {len(df_acc)} "
          f"(Sleepers: {SLEEPER_COUNT}, Burners: {BURNER_COUNT}) | Transactions: {len(df_tx)}")


if __name__ == "__main__":
    dim_customers, dim_accounts = generate_dimensions()
    fact_transactions, dim_accounts = generate_transactions(dim_accounts)  # dim_accounts returned with fixed dates
    save_to_excel(dim_customers, dim_accounts, fact_transactions)