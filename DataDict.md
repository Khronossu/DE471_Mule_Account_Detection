# Data Dictionary: Fraud Detection Pipeline

**Project:** Data Analysis & BI: Detecting Scam-Induced Transactions to Mule Accounts  
**Description:** This document outlines the Star Schema for the synthetic financial data mart, designed to support descriptive and diagnostic analytics in BI tools (e.g., Tableau, PowerBI). 

---

## 1. Dimension Table: `dim_customers`
**Description:** Static demographic and risk profile data for all banking customers.

| Field Name | Data Type | Key | Description | Allowed Values / Logic |
| :--- | :--- | :--- | :--- | :--- |
| `customer_id` | String | **PK** | Unique identifier for the customer. | e.g., `CUST_0001` |
| `age` | Integer | | Age of the customer in years. | `18` to `75` |
| `employment_status` | String | | Current employment profile. | `Salaried`, `Student`, `Unemployed`, `Self-Employed` |
| `kyc_status` | String | | Know Your Customer verification state. | `Verified`, `Pending`, `Rejected` |
| `risk_segment` | String | | Internal bank risk scoring tier. | `Low`, `Medium`, `High` |

---

## 2. Dimension Table: `dim_accounts`
**Description:** Core account details and ground-truth labels for fraudulent entities.

| Field Name | Data Type | Key | Description | Allowed Values / Logic |
| :--- | :--- | :--- | :--- | :--- |
| `account_id` | String | **PK** | Unique identifier for the bank account. | e.g., `ACC_0001` |
| `customer_id` | String | **FK** | Links to `dim_customers`. | Matches `CUST_XXXX` |
| `account_creation_date` | Timestamp | | Date and time the account was opened. | `YYYY-MM-DD HH:MM:SS` |
| `initial_deposit` | Float | | The starting balance of the account. | `$50.00` to `$5000.00` |
| `is_mule_flag` | Boolean | | **Ground Truth:** Is this a known mule? | `True`, `False` |
| `mule_type` | String | | Categorization of the mule behavior. | `Burner`, `Sleeper`, `None` |

---

## 3. Fact Table: `fact_transactions`
**Description:** The chronological, stateful ledger of all money movement, enriched with rolling-window behavioral features designed for machine learning.

### A. Raw Transaction Data
| Field Name | Data Type | Key | Description | Allowed Values / Logic |
| :--- | :--- | :--- | :--- | :--- |
| `transaction_id` | String | **PK** | Unique identifier for the transfer. | e.g., `TXN_000001` |
| `sender_account_id` | String | **FK** | Account originating the transfer. | Matches `ACC_XXXX` |
| `receiver_account_id` | String | **FK** | Account receiving the transfer. | `ACC_XXXX` or `EXT_CRYPTO_WALLET` |
| `amount` | Float | | The monetary value of the transfer. | `> 0.00` |
| `transaction_timestamp` | Timestamp | | Exact time the transfer occurred. | `YYYY-MM-DD HH:MM:SS` |
| `transfer_method` | String | | The channel used for the transfer. | `Mobile App`, `Web`, `API`, `ATM` |
| `is_mule_tx` | Boolean | | **Target Variable:** Is this a scam transfer? | `True`, `False` |

### B. Engineered Behavioral Features
| Field Name | Data Type | Description | Interpretation / Logic |
| :--- | :--- | :--- | :--- |
| `sender_balance_before_tx` | Float | Sender's available balance prior to transfer. | Derived from state-tracked running balance. |
| `receiver_balance_before_tx`| Float | Receiver's balance prior to transfer. | Derived from state-tracked running balance. |
| `time_since_last_tx_seconds`| Integer | Seconds since sender's last outgoing transfer. | Velocity metric. `-1` if first transaction. |
| `dwell_time_minutes` | Float | Minutes since sender last received a credit. | Extremely low for pass-through mules. |
| `is_first_time_payee` | Boolean | Has sender ever paid this receiver before? | High correlation with burner accounts. |
| `in_out_ratio_7d` | Float | Ratio of credits/debits over the last 7 days. | Approaches `1.0` for pass-through mules. |
| `daily_tx_count_sender` | Integer | Outgoing transaction count in the last 24h. | Rolling count to detect sudden spikes. |
| `burst_score` | Integer | Outgoing transaction count in the last 1 hour. | Short-window burst indicator — flags Hop 2 split-transfers in mule rings. |
| `account_age_days` | Integer | Age of the sender's account (in days) at the time of this transaction. | Burner indicator: freshly opened accounts transacting large sums are suspicious. |
| `amount_z_score` | Float | How unusual the amount is vs sender's history. | Calculated via expanding mean/std. `Z = (amount − μ_past) / σ_past`. `|Z|>2` = statistically unusual. |