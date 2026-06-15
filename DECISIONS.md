# SplitRight Design Decisions

This document outlines key technical decisions made during the development of SplitRight.

---

## 1. Why Python Flask instead of Node.js?

- **Built-in Data Processing Utilities:** Python's standard library has exceptional support for file processing (`csv` modules, `re` regular expressions, robust `datetime` parsing). This made implementing 20 complex anomaly detections simple and extremely readable.
- **Lightweight Framework:** Flask provides a minimal boilerplate setup. We can construct modular routing, database interactions, and middleware validations without complex configuration.
- **Python Ecosystem compatibility:** Perfect for data handling, scripting, and unit testing via `pytest`.

---

## 2. Why SQLite?

- **Zero-Configuration & Portability:** SQLite is a serverless, self-contained relational database. It is stored as a single file (`backend/splitright.db`), which eliminates the need to configure separate database servers (PostgreSQL/MySQL) locally or in basic staging environments.
- **Relational Integrity:** SplitRight requires structured tables (foreign keys, cascade deletes, indices) to link users, expenses, splits, and settlements. SQLite supports standard ANSI SQL constraints and runs queries with extremely low latency.
- **Perfect for Local Development:** Matches the scope of a single-group flatmate assignment.

---

## 3. Debt Minimization Algorithm

The Suggested Settlements feature applies a **greedy minimization algorithm**:

1. **Net Balance Calculation:** 
   $$\text{Net Balance} = \text{Total Paid} - \text{Total Owed}$$
   - Total Paid includes all expenses paid by the user plus settlements they sent.
   - Total Owed includes all splits they owe plus settlements they received.
2. **Debtors & Creditors Separation:**
   - Users with negative net balances are added to a `debtors` list.
   - Users with positive net balances are added to a `creditors` list.
3. **Greedy Matching:**
   - Sort debtors in ascending order (most negative first) and creditors in descending order (most positive first).
   - Match the largest debtor $D$ (owes $-W$) with the largest creditor $C$ (owed $O$).
   - Execute a settlement transaction of $T = \min(|W|, O)$.
   - Subtract $T$ from $D$'s debt and $C$'s credit.
   - If either is fully settled (balance within a threshold of 0.005), remove them from the active list.
   - Re-sort remaining active lists and repeat until all debts are settled.

This greedy choice minimizes the total number of transactions to resolve the group debt.

---

## 4. Rounding Strategy

- **Financial standard rounding:** All amounts are processed and stored using 2 decimal places.
- **Splits Mismatch Adjustment:** When splitting an amount (e.g., splitting ₹100.00 equally among 3 people, yielding ₹33.33 each), a rounding difference arises (₹100.00 - ₹99.99 = ₹0.01).
- **Resolution:** We calculate the difference between the total expense amount and the sum of splits:
  $$\text{Difference} = \text{Amount} - \sum \text{Splits}$$
  We apply the difference directly to the first active split member's share (e.g., Person 1 owes ₹33.34, while Person 2 and 3 owe ₹33.33). This ensures that the sum of splits matches the total expense amount to the exact paisa.

---

## 5. How Membership Dates Affect Splits

- **Dynamic Membership Boundary Enforcing:** Flatmates enter and exit the shared household over time (Meera left March 31, Sam joined April 15).
- **Automatic Exclusions:**
  - When importing or creating an expense on date $D$, SplitRight checks:
    $$\text{joined\_at} \le D \le \text{left\_at}$$
  - If a group member's active dates do not cover the expense date, they are excluded from the split.
  - The remaining active members divide the expense.
  - This ensures that Meera is never charged for April expenses, and Sam is never charged for February/March expenses, while guest Dev is only charged for expenses during his stay.
