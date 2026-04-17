import pandas as pd
import os

src = os.path.join(os.path.dirname(__file__), "..", "data", "mule_account_with_features.xlsx")
dst = os.path.join(os.path.dirname(__file__), "..", "data", "data_sample.csv")

df = pd.read_excel(src, nrows=1000)
df.to_csv(dst, index=False)

print(f"Saved {len(df)} rows to {dst}")
