# SplitRight 🚀

SplitRight is a full-stack shared expenses web application designed for housemates and groups. It features user authentication, time-based group membership tracking, flexible split types (equal, percentage, shares, unequal), debt minimization, and a robust CSV importer that automatically detects and resolves 20 different data anomalies.

## Technology Stack

- **Frontend:** React, Vite, CSS (vanilla dark theme, Outfit typography, Lucide React icons)
- **Backend:** Python Flask, SQLite database, PyJWT for authentication
- **Tests:** Pytest for automated CSV importer validation

---

## Getting Started

### Prerequisites

- Node.js (v18+)
- Python (v3.11+)

---

### Backend Setup

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - **Windows (PowerShell):**
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the database initializer:**
   ```bash
   python db.py
   ```
   This creates the database `splitright.db`, setups schemas, and seeds default exchange rates.

6. **Start the Flask server:**
   ```bash
   python app.py
   ```
   The server will run on `http://127.0.0.1:5000` and automatically seed a default group named `Flatmates` and flatmates users (Aisha, Rohan, Priya, Meera, Sam, Dev) with a default password of `password123`.

---

### Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install node dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```
   Open your browser at `http://localhost:5173` (or the URL output by Vite).

4. **Build for production:**
   ```bash
   npm run build
   ```

---

## Project Features

1. **Authentication:** Register and log in with JWT. Access demo accounts:
   - `aisha@splitright.com` / `password123`
   - `rohan@splitright.com` / `password123`
   - `priya@splitright.com` / `password123`
2. **Time-Based Group Memberships:** Add flatmates with specific join and leave dates. Splits are dynamically adjusted; individuals are excluded from splits of expenses logged outside their active dates.
3. **CSV Importer:** Drag/upload `expenses_export.csv` to run the anomaly detection engine. It reviews, corrects, and logs warnings or skips for 20 anomalies.
4. **Anomaly Report Dashboard:** An interactive ledger detailing all detected anomalies with badge types, row numbers, descriptions, and a toggle capability to resolve each one.
5. **Debt Minimization:** View a list of suggested settlements that balances the ledger using the minimum transactions. Direct "Settle" action pre-populates a settlement payment ledger.
