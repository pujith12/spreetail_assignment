import os
import sqlite3
import pytest
import db
import importer

# Override the database path in the db module to use a test database
TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_splitright.db')

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    # Override DATABASE_PATH in db module
    monkeypatch.setattr(db, "DATABASE_PATH", TEST_DB_PATH)
    
    # Remove test DB if it exists from a previous crash
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass
            
    # Initialize the test database
    db.init_db()
    
    yield
    
    # Clean up test database
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass

def test_csv_import_anomalies():
    # 1. Create a group first
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO groups (name, description) VALUES ('Flatmates', 'Our shared apartment expenses')")
    group_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # 2. Get path to the CSV file
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'expenses export.csv')
    assert os.path.exists(csv_path), f"CSV file not found at {csv_path}"
    
    # 3. Perform the import
    session_id = "test-session-123"
    result = importer.import_csv_data(csv_path, group_id, session_id=session_id)
    
    print("\nImport Summary:")
    print(f"Processed: {result['rows_processed']}")
    print(f"Imported:  {result['rows_imported']}")
    print(f"Skipped:   {result['rows_skipped']}")
    print(f"Anomalies: {result['anomalies_count']}")
    
    # 4. Open connection to verify database contents
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # Get all logged anomalies
    cursor.execute("SELECT row_number, anomaly_type, description, action_taken FROM import_anomalies WHERE session_id = ?", (session_id,))
    anomalies = cursor.fetchall()
    
    print("\nLogged Anomalies:")
    for a in anomalies:
        print(f"Row {a['row_number']} | {a['anomaly_type']} | Action: {a['action_taken']} | {a['description'][:60]}")
        
    # Check total anomalies count
    assert len(anomalies) > 0, "No anomalies were logged!"
    
    # Check some specific rows & anomalies:
    
    # Anomaly 4 & 5: Comma in amount & Leading/Trailing spaces
    # Row 7 (Electricity Feb) has amount "1,200". Check it was stripped to 1200.0
    cursor.execute("SELECT amount_inr FROM expenses WHERE import_row = 7")
    row_7 = cursor.fetchone()
    assert row_7 is not None
    assert row_7['amount_inr'] == 1200.0
    
    # Row 29 (Electricity Mar) has amount " 1450 ". Check spaces trimmed and parsed.
    cursor.execute("SELECT amount_inr FROM expenses WHERE import_row = 29")
    row_29 = cursor.fetchone()
    assert row_29 is not None
    assert row_29['amount_inr'] == 1450.0

    # Anomaly 3 & 20: Settlements converted
    # Row 14 (Rohan paid Aisha back) -> Settlement of 5000 INR
    cursor.execute("SELECT amount, paid_by, paid_to FROM settlements WHERE import_row = 14")
    set_14 = cursor.fetchone()
    assert set_14 is not None
    assert set_14['amount'] == 5000.0
    
    # Row 38 (Sam deposit share) -> Settlement of 15000 INR from Sam to Aisha
    cursor.execute("""
        SELECT s.amount, u_from.name as from_name, u_to.name as to_name 
        FROM settlements s
        JOIN users u_from ON s.paid_by = u_from.id
        JOIN users u_to ON s.paid_to = u_to.id
        WHERE s.import_row = 38
    """)
    set_38 = cursor.fetchone()
    assert set_38 is not None
    assert set_38['amount'] == 15000.0
    assert set_38['from_name'] == 'Sam'
    assert set_38['to_name'] == 'Aisha'

    # Anomaly 6: Missing paid_by
    # Row 13 (House cleaning supplies) has empty paid_by
    cursor.execute("SELECT paid_by, description FROM expenses WHERE import_row = 13")
    exp_13 = cursor.fetchone()
    assert exp_13 is not None
    assert exp_13['paid_by'] is None
    
    # Anomaly 9: USD expenses converted
    # Row 20 (Goa villa booking) has 540 USD
    cursor.execute("SELECT amount, currency, amount_inr, exchange_rate FROM expenses WHERE import_row = 20")
    exp_20 = cursor.fetchone()
    assert exp_20 is not None
    assert exp_20['amount'] == 540.0
    assert exp_20['currency'] == 'USD'
    assert exp_20['amount_inr'] == 540.0 * 84.5
    assert exp_20['exchange_rate'] == 84.5

    # Anomaly 10: Negative amount (refund)
    # Row 26 (Parasailing refund) has -30 USD
    cursor.execute("SELECT amount, amount_inr FROM expenses WHERE import_row = 26")
    exp_26 = cursor.fetchone()
    assert exp_26 is not None
    assert exp_26['amount'] == -30.0
    assert exp_26['amount_inr'] == -30.0 * 84.5

    # Anomaly 11: Missing currency
    # Row 28 (Groceries DMart) has missing currency
    cursor.execute("SELECT currency FROM expenses WHERE import_row = 28")
    exp_28 = cursor.fetchone()
    assert exp_28 is not None
    assert exp_28['currency'] == 'INR'

    # Anomaly 12: Zero amount skipped
    # Row 31 (Swiggy order) has 0 INR. Should not be in expenses table.
    cursor.execute("SELECT 1 FROM expenses WHERE import_row = 31")
    assert cursor.fetchone() is None
    
    # Anomaly 13: Meera included after March 31
    # Row 36 (Groceries BigBasket) is on 2026-04-02 and split includes Meera. Meera should be removed from split.
    # Check that Meera (user_id for Meera) is NOT in the split for Row 36.
    cursor.execute("SELECT id FROM users WHERE name = 'Meera'")
    meera_id = cursor.fetchone()['id']
    cursor.execute("""
        SELECT count(*) as cnt FROM expense_splits es
        JOIN expenses e ON es.expense_id = e.id
        WHERE e.import_row = 36 AND es.user_id = ?
    """, (meera_id,))
    assert cursor.fetchone()['cnt'] == 0
    
    # Anomaly 14: Sam included before April 15
    # Row 39 (Housewarming drinks) is on 2026-04-10 and split includes Sam. Sam should be removed from split.
    cursor.execute("SELECT id FROM users WHERE name = 'Sam'")
    sam_id = cursor.fetchone()['id']
    cursor.execute("""
        SELECT count(*) as cnt FROM expense_splits es
        JOIN expenses e ON es.expense_id = e.id
        WHERE e.import_row = 39 AND es.user_id = ?
    """, (sam_id,))
    assert cursor.fetchone()['cnt'] == 0

    # Anomaly 18: Unknown guest created
    # Row 23 (Parasailing) includes Kabir ("Dev's friend Kabir").
    cursor.execute("SELECT id, is_guest FROM users WHERE name = 'Dev''s friend Kabir'")
    kabir_row = cursor.fetchone()
    assert kabir_row is not None
    assert kabir_row['is_guest'] == 1

    # Check exact duplicates skipped
    # Row 6 (dinner - marina bites, Dev, 3200) vs Row 5 (Dinner at Marina Bites, Dev, 3200)
    # Wait, Row 6 and Row 5 have different descriptions, so they are not exact duplicates.
    # Wait, check if there are exact duplicate warnings.
    # If there were any, they would be logged.
    
    conn.close()
