# Legacy v1 Artifacts

This folder contains the **v1 dataset and helper scripts**, kept for traceability only. They are **superseded** by the current pipeline:

| v1 (here) | v2 (production) |
|---|---|
| `data/mule_account_with_features.xlsx` | `data/processed/transactions_with_features.xlsx` |
| `data/synthetic_fraud_dataset_before_feature_extraction.xlsx` | `data/raw/star_schema.xlsx` |
| `data/data_sample.csv`, `data/hw4.xlsx` | (no equivalent — exploratory only) |
| `extract_sample.py` | (deleted — v2 doesn't need a sampler) |

Do not use any of these for the final submission. The canonical pipeline is `python run_pipeline.py` from the repo root.

**Why v1 was retired:**
1. Mule rings shared accounts → First-Time Payee signal was washed out
2. No time-of-day bias in mule txns → WHEN question was untestable
3. Normal transaction amounts were uniformly distributed (unrealistic)
4. `burst_score` and `account_age_days` features did not exist
