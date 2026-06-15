# SplitRight Scope Documentation

This document defines how SplitRight's CSV importer detects and corrects all 20 specified anomalies without crashing. It also documents the complete SQLite database schema.

---

## 20 CSV Anomalies & Handlers

### 1. Exact Duplicate Rows
- **Detection:** Checked if a row has the exact same date, normalized description (lowercased, spaces stripped, non-alphanumeric removed), and amount as an already processed row in the current session or a record in the database.
- **Handling:** Skip the row, log a `EXACT_DUPLICATE` critical anomaly.

### 2. Near-Duplicate Rows
- **Detection:** Same date and normalized description, but different amount.
- **Handling:** Keep and import the second row, but log a `NEAR_DUPLICATE` warning for review.

### 3. Settlement Logged as Expense
- **Detection:** Split type is empty, or the description contains words like "paid back", "settle", or "repaid".
- **Handling:** Convert to a settlement record (stored in the `settlements` table) and log `SETTLEMENT_LOGGED_AS_EXPENSE` with action `CONVERT_TO_SETTLEMENT`.

### 4. Comma in Amount Field
- **Detection:** Amount string contains commas (e.g., `"1,200"`).
- **Handling:** Stripped commas, parsed as a float, logged `FORMAT_CORRECTION` with action `STRIP_COMMA`.

### 5. Leading/Trailing Spaces in Amount
- **Detection:** Spaces surrounding the amount digits (e.g., `" 1450 "`).
- **Handling:** Trimmed whitespace, parsed, logged `FORMAT_CORRECTION` with action `TRIM_AMOUNT`.

### 6. Missing `paid_by` Field
- **Detection:** Row has an empty or null `paid_by` column.
- **Handling:** Import with a `NULL` payer, log a `MISSING_PAYER` critical anomaly to flag for review.

### 7. Mixed Date Formats
- **Detection:** Dates formatted differently, e.g., `YYYY-MM-DD`, `DD/MM/YYYY`, or `"Mar 14"`.
- **Handling:** Parsed with multiple formats; if year is missing (e.g., `"Mar 14"`), assumed 2026. Normalized to ISO `YYYY-MM-DD` and logged `DATE_NORMALIZATION` with action `CONVERT_TO_ISO`.

### 8. Ambiguous Date
- **Detection:** Date formatted as `04/05/2026` where both day and month components are $\le 12$.
- **Handling:** Defaulted to `DD/MM/YYYY` (May 4, 2026), log a warning `AMBIGUOUS_DATE` with action `TREAT_AS_DD_MM`.

### 9. USD Expenses
- **Detection:** Currency field equals `'USD'`.
- **Handling:** Multiplied by a configurable rate (default 84.5), stored the original USD amount/currency, populated `amount_inr` and `exchange_rate` fields, logged `CURRENCY_CONVERSION` with action `CONVERT_TO_INR`.

### 10. Negative Amount
- **Detection:** Amount is less than 0.
- **Handling:** Treated as refund (splits are imported with negative values), added notes, logged `NEGATIVE_AMOUNT` with action `TREAT_AS_REFUND`.

### 11. Missing Currency
- **Detection:** Currency column is empty.
- **Handling:** Defaulted currency to `'INR'`, logged `MISSING_CURRENCY` warning with action `DEFAULT_TO_INR`.

### 12. Zero Amount
- **Detection:** Amount field is 0.
- **Handling:** Skipped row (placeholder/cancelled), logged `ZERO_AMOUNT` critical anomaly.

### 13. Meera Included in Splits After March 31, 2026
- **Detection:** Expense date is on/after `2026-04-01` and Meera is in the split list.
- **Handling:** Excluded Meera from that split, pro-rated splits among remaining active members, logged `MEMBERSHIP_OUT_OF_BOUNDS`.

### 14. Sam Included in Splits Before April 15, 2026
- **Detection:** Expense date is on/before `2026-04-14` and Sam is in the split list.
- **Handling:** Excluded Sam from that split, pro-rated splits among remaining active members, logged `MEMBERSHIP_OUT_OF_BOUNDS`.

### 15. Percentage Splits Not Summing to 100%
- **Detection:** Split type is `'percentage'` and the sum of percentages does not equal 100% (e.g., 110%).
- **Handling:** Normalized proportions to sum to exactly 100%, log `SPLIT_PERCENTAGE_MISMATCH` with action `NORMALIZE_TO_100`.

### 16. `split_type=equal` But `split_details` Provided
- **Detection:** Split type is equal, but the details column is not empty.
- **Handling:** Ignored split details, split equally among split members, logged `SPLIT_DETAILS_CONFLICT` warning.

### 17. Name Variations
- **Detection:** Encountered casing or spacing variations of names (e.g., `"priya s"`, `"rohan "`, `"ROHAN"`).
- **Handling:** Standardized to canonical names (`Aisha`, `Rohan`, `Priya`, `Meera`, `Sam`, `Dev`), logged `NAME_NORMALIZATION`.

### 18. Unknown Person in Split
- **Detection:** Encountered name not matching any regular flatmate or guest (e.g., `"Dev's friend Kabir"`).
- **Handling:** Created a guest user with `is_guest = 1` in the database, added them to the group, logged `UNKNOWN_PERSON` warning with action `CREATE_GUEST_USER`.

### 19. Invalid `split_type`
- **Detection:** Split type is not `equal`, `percentage`, `share`, or `unequal`.
- **Handling:** Defaulted to `equal` split, logged `INVALID_SPLIT_TYPE` warning.

### 20. Sam's Deposit (Row 38)
- **Detection:** Explicit row 38 or description "Sam deposit share".
- **Handling:** Converted from expense to a settlement from Sam to Aisha of 15000 INR, logged `DEPOSIT_AS_SETTLEMENT` with action `CONVERT_TO_SETTLEMENT`.

---

## Database Schema

SplitRight utilizes a SQLite database with the following tables:

### 1. `users`
Tracks both registered users and temporary guests.
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `name` TEXT NOT NULL
- `email` TEXT UNIQUE (can be NULL for guests)
- `password_hash` TEXT (can be NULL for guests)
- `is_guest` INTEGER DEFAULT 0 (1 = guest user, 0 = registered flatmate)

### 2. `groups`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `name` TEXT NOT NULL
- `description` TEXT

### 3. `group_members`
Implements time-based membership.
- `group_id` INTEGER NOT NULL, FK -> `groups(id)`
- `user_id` INTEGER NOT NULL, FK -> `users(id)`
- `joined_at` TEXT NOT NULL (ISO Date `YYYY-MM-DD`)
- `left_at` TEXT (ISO Date `YYYY-MM-DD`, NULL if active)
- PRIMARY KEY (`group_id`, `user_id`)

### 4. `expenses`
Stores transaction details.
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `group_id` INTEGER NOT NULL, FK -> `groups(id)`
- `description` TEXT NOT NULL
- `amount` REAL NOT NULL
- `currency` TEXT NOT NULL
- `amount_inr` REAL NOT NULL
- `exchange_rate` REAL NOT NULL
- `paid_by` INTEGER, FK -> `users(id)` (can be NULL for review anomalies)
- `expense_date` TEXT NOT NULL (ISO Date `YYYY-MM-DD`)
- `split_type` TEXT NOT NULL
- `notes` TEXT
- `is_settlement` INTEGER DEFAULT 0
- `import_row` INTEGER (CSV row index for tracing)

### 5. `expense_splits`
Stores individual share liabilities.
- `expense_id` INTEGER NOT NULL, FK -> `expenses(id)`
- `user_id` INTEGER NOT NULL, FK -> `users(id)`
- `amount_owed` REAL NOT NULL
- `share_value` REAL (Stores raw share value input: percentage, weight, or amount)
- PRIMARY KEY (`expense_id`, `user_id`)

### 6. `settlements`
Logs payments between flatmates.
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `group_id` INTEGER NOT NULL, FK -> `groups(id)`
- `paid_by` INTEGER NOT NULL, FK -> `users(id)`
- `paid_to` INTEGER NOT NULL, FK -> `users(id)`
- `amount` REAL NOT NULL
- `settlement_date` TEXT NOT NULL (ISO Date `YYYY-MM-DD`)
- `import_row` INTEGER

### 7. `import_anomalies`
Audit log of CSV importer checks.
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `session_id` TEXT NOT NULL
- `row_number` INTEGER NOT NULL
- `anomaly_type` TEXT NOT NULL
- `description` TEXT NOT NULL
- `action_taken` TEXT NOT NULL
- `resolved` INTEGER DEFAULT 0

### 8. `exchange_rates`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `currency` TEXT UNIQUE NOT NULL
- `rate` REAL NOT NULL
