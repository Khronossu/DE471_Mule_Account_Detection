import os
import pandas as pd

RAW_FILE = 'data/raw/star_schema.xlsx'
PROCESSED_FILE = 'data/processed/transactions_with_features.xlsx'
OUTPUT_FILE = 'data/final/obt_final.xlsx'

df_tx = pd.read_excel(PROCESSED_FILE)
df_acc = pd.read_excel(RAW_FILE, sheet_name='dim_accounts')
df_cust = pd.read_excel(RAW_FILE, sheet_name='dim_customers')

df_acc = df_acc.rename(columns={'account_id': 'sender_account_id'})
df = df_tx.merge(
    df_acc[['sender_account_id', 'customer_id', 'is_mule_flag', 'mule_type']],
    on='sender_account_id', how='left'
)
df = df.merge(
    df_cust[['customer_id', 'age', 'employment_status', 'kyc_status', 'risk_segment']],
    on='customer_id', how='left'
)

print(f"Final row count: {len(df)}")  # Must be 20,000

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
df.to_excel(OUTPUT_FILE, index=False)
print(f"Wrote {OUTPUT_FILE}")
