import os
import tempfile
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

import db
import auth
import debt
import importer

app = Flask(__name__)
# Enable CORS for frontend integration
CORS(app)

# Ensure database is initialized and seed default users
def seed_data():
    db.init_db()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # Create default users if they don't exist
    flatmates = [
        {"name": "Aisha", "email": "aisha@splitright.com", "joined": "2026-02-01", "left": None},
        {"name": "Rohan", "email": "rohan@splitright.com", "joined": "2026-02-01", "left": None},
        {"name": "Priya", "email": "priya@splitright.com", "joined": "2026-02-01", "left": None},
        {"name": "Meera", "email": "meera@splitright.com", "joined": "2026-02-01", "left": "2026-03-31"},
        {"name": "Sam", "email": "sam@splitright.com", "joined": "2026-04-15", "left": None},
        {"name": "Dev", "email": "dev@splitright.com", "joined": "2026-02-01", "left": "2026-04-30"}
    ]
    
    user_ids = {}
    for fm in flatmates:
        cursor.execute("SELECT id FROM users WHERE name = ?", (fm["name"],))
        row = cursor.fetchone()
        if not row:
            p_hash = generate_password_hash("password123")
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, is_guest) VALUES (?, ?, ?, 0)",
                (fm["name"], fm["email"], p_hash)
            )
            user_ids[fm["name"]] = cursor.lastrowid
        else:
            user_ids[fm["name"]] = row["id"]
            
    # Create default group
    cursor.execute("SELECT id FROM groups WHERE name = 'Flatmates'")
    group_row = cursor.fetchone()
    if not group_row:
        cursor.execute("INSERT INTO groups (name, description) VALUES ('Flatmates', 'Shared household expenses since Feb 2026')")
        group_id = cursor.lastrowid
    else:
        group_id = group_row["id"]
        
    # Create group memberships
    for fm in flatmates:
        cursor.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_ids[fm["name"]])
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO group_members (group_id, user_id, joined_at, left_at) VALUES (?, ?, ?, ?)",
                (group_id, user_ids[fm["name"]], fm["joined"], fm["left"])
            )
            
    conn.commit()
    conn.close()

# ----------------- AUTH ENDPOINTS -----------------

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    if not name or not email or not password:
        return jsonify({'message': 'Missing required fields'}), 400
        
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # Check if user already exists
    cursor.execute("SELECT id FROM users WHERE email = ? OR name = ?", (email, name))
    if cursor.fetchone():
        conn.close()
        return jsonify({'message': 'User with this email or name already exists'}), 400
        
    p_hash = generate_password_hash(password)
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, is_guest) VALUES (?, ?, ?, 0)",
            (name, email, p_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()
        token = auth.generate_token(user_id)
        return jsonify({'token': token, 'user': {'id': user_id, 'name': name, 'email': email}}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'message': f'Registration failed: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'message': 'Missing email or password'}), 400
        
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'message': 'Invalid credentials'}), 401
        
    token = auth.generate_token(user['id'])
    return jsonify({
        'token': token,
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email']
        }
    })

@app.route('/api/auth/me', methods=['GET'])
@auth.token_required
def get_me(current_user_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, is_guest FROM users WHERE id = ?", (current_user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
        
    return jsonify({
        'id': user['id'],
        'name': user['name'],
        'email': user['email'],
        'is_guest': bool(user['is_guest'])
    })

# ----------------- GROUP ENDPOINTS -----------------

@app.route('/api/groups', methods=['GET'])
@auth.token_required
def get_groups(current_user_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    # Get all groups that current user belongs to
    cursor.execute(
        """
        SELECT g.id, g.name, g.description FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = ?
        """,
        (current_user_id,)
    )
    rows = cursor.fetchall()
    groups_list = [{'id': r['id'], 'name': r['name'], 'description': r['description']} for r in rows]
    conn.close()
    return jsonify(groups_list)

@app.route('/api/groups', methods=['POST'])
@auth.token_required
def create_group(current_user_id):
    data = request.get_json() or {}
    name = data.get('name')
    description = data.get('description', '')
    
    if not name:
        return jsonify({'message': 'Group name is required'}), 400
        
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO groups (name, description) VALUES (?, ?)", (name, description))
        group_id = cursor.lastrowid
        # Add creator as group member since today
        today = datetime.date.today().strftime('%Y-%m-%d')
        cursor.execute(
            "INSERT INTO group_members (group_id, user_id, joined_at, left_at) VALUES (?, ?, ?, NULL)",
            (group_id, current_user_id, today)
        )
        conn.commit()
        return jsonify({'id': group_id, 'name': name, 'description': description}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/groups/<int:group_id>', methods=['GET'])
@auth.token_required
def get_group(current_user_id, group_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # Check membership
    cursor.execute("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, current_user_id))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'message': 'Access denied'}), 403
        
    cursor.execute("SELECT id, name, description FROM groups WHERE id = ?", (group_id,))
    group = cursor.fetchone()
    conn.close()
    
    if not group:
        return jsonify({'message': 'Group not found'}), 404
        
    return jsonify({'id': group['id'], 'name': group['name'], 'description': group['description']})

@app.route('/api/groups/<int:group_id>/members', methods=['GET'])
@auth.token_required
def get_group_members(current_user_id, group_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT u.id, u.name, u.email, u.is_guest, gm.joined_at, gm.left_at 
        FROM group_members gm
        JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id = ?
        """,
        (group_id,)
    )
    rows = cursor.fetchall()
    members = [{
        'id': r['id'],
        'name': r['name'],
        'email': r['email'],
        'is_guest': bool(r['is_guest']),
        'joined_at': r['joined_at'],
        'left_at': r['left_at']
    } for r in rows]
    conn.close()
    return jsonify(members)

@app.route('/api/groups/<int:group_id>/members', methods=['POST'])
@auth.token_required
def add_group_member(current_user_id, group_id):
    data = request.get_json() or {}
    name = data.get('name')
    email = data.get('email') # nullable
    joined_at = data.get('joined_at') or datetime.date.today().strftime('%Y-%m-%d')
    left_at = data.get('left_at') # nullable
    is_guest = bool(data.get('is_guest', False))
    
    if not name:
        return jsonify({'message': 'Member name is required'}), 400
        
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if user already exists
        user_id = None
        if email:
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                user_id = row['id']
        else:
            cursor.execute("SELECT id FROM users WHERE name = ? AND is_guest = ?", (name, 1 if is_guest else 0))
            row = cursor.fetchone()
            if row:
                user_id = row['id']
                
        if not user_id:
            # Create user
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, is_guest) VALUES (?, ?, NULL, ?)",
                (name, email, 1 if is_guest else 0)
            )
            user_id = cursor.lastrowid
            
        # Add to group membership
        cursor.execute(
            "INSERT OR REPLACE INTO group_members (group_id, user_id, joined_at, left_at) VALUES (?, ?, ?, ?)",
            (group_id, user_id, joined_at, left_at)
        )
        conn.commit()
        return jsonify({'user_id': user_id, 'name': name, 'joined_at': joined_at, 'left_at': left_at}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()

# ----------------- EXPENSE ENDPOINTS -----------------

@app.route('/api/groups/<int:group_id>/expenses', methods=['GET'])
@auth.token_required
def get_expenses(current_user_id, group_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # Verify membership
    cursor.execute("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, current_user_id))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'message': 'Access denied'}), 403
        
    # Get expenses
    cursor.execute(
        """
        SELECT e.id, e.description, e.amount, e.currency, e.amount_inr, e.exchange_rate, 
               e.paid_by, e.expense_date, e.split_type, e.notes, e.is_settlement, e.import_row,
               u.name as payer_name
        FROM expenses e
        LEFT JOIN users u ON e.paid_by = u.id
        WHERE e.group_id = ?
        ORDER BY e.expense_date DESC, e.id DESC
        """,
        (group_id,)
    )
    exp_rows = cursor.fetchall()
    
    expenses_list = []
    for er in exp_rows:
        # Get splits for this expense
        cursor.execute(
            """
            SELECT es.user_id, es.amount_owed, es.share_value, u.name as member_name
            FROM expense_splits es
            JOIN users u ON es.user_id = u.id
            WHERE es.expense_id = ?
            """,
            (er['id'],)
        )
        split_rows = cursor.fetchall()
        splits = [{
            'user_id': sr['user_id'],
            'member_name': sr['member_name'],
            'amount_owed': sr['amount_owed'],
            'share_value': sr['share_value']
        } for sr in split_rows]
        
        expenses_list.append({
            'id': er['id'],
            'description': er['description'],
            'amount': er['amount'],
            'currency': er['currency'],
            'amount_inr': er['amount_inr'],
            'exchange_rate': er['exchange_rate'],
            'paid_by': er['paid_by'],
            'payer_name': er['payer_name'],
            'expense_date': er['expense_date'],
            'split_type': er['split_type'],
            'notes': er['notes'],
            'is_settlement': bool(er['is_settlement']),
            'import_row': er['import_row'],
            'splits': splits
        })
        
    conn.close()
    return jsonify(expenses_list)

@app.route('/api/groups/<int:group_id>/expenses', methods=['POST'])
@auth.token_required
def create_expense(current_user_id, group_id):
    data = request.get_json() or {}
    description = data.get('description')
    amount = data.get('amount')
    currency = data.get('currency', 'INR')
    paid_by = data.get('paid_by', current_user_id) # default to creator
    expense_date = data.get('expense_date') or datetime.date.today().strftime('%Y-%m-%d')
    split_type = data.get('split_type', 'equal')
    notes = data.get('notes', '')
    
    # splits data format: [{'user_id': int, 'share_value': float}]
    splits_data = data.get('splits', []) 
    
    if not description or amount is None:
        return jsonify({'message': 'Description and amount are required'}), 400
        
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check exchange rate
        exchange_rate = 1.0
        if currency == 'USD':
            cursor.execute("SELECT rate FROM exchange_rates WHERE currency = 'USD'")
            usd_row = cursor.fetchone()
            exchange_rate = usd_row['rate'] if usd_row else 84.5
        amount_inr = float(amount) * exchange_rate
        
        # Enforce membership dates: check who is active on this expense date
        cursor.execute(
            """
            SELECT user_id, joined_at, left_at FROM group_members
            WHERE group_id = ?
            """,
            (group_id,)
        )
        members = cursor.fetchall()
        
        active_member_ids = []
        for m in members:
            # Check joined_at <= date and (left_at IS NULL or left_at >= date)
            if m['joined_at'] <= expense_date and (m['left_at'] is None or m['left_at'] >= expense_date):
                active_member_ids.append(m['user_id'])
                
        # Filter splits_data for active members
        if not splits_data:
            # Default to splitting equally among all active members
            splits_data = [{'user_id': uid, 'share_value': 1.0} for uid in active_member_ids]
        else:
            # Keep only splits for active members
            splits_data = [s for s in splits_data if s['user_id'] in active_member_ids]
            
        if not splits_data:
            return jsonify({'message': 'No eligible group members active on this date to split with!'}), 400
            
        # Calculate splits
        splits_to_insert = []
        
        if split_type == 'equal':
            num_splits = len(splits_data)
            share = round(amount_inr / num_splits, 2)
            diff = round(amount_inr - (share * num_splits), 2)
            for idx, s in enumerate(splits_data):
                owed = share
                if idx == 0:
                    owed = round(owed + diff, 2)
                splits_to_insert.append((s['user_id'], owed, 1.0))
                
        elif split_type == 'percentage':
            total_pct = sum(s['share_value'] for s in splits_data)
            # Normalize if sum != 100
            if abs(total_pct - 100.0) > 0.01 and total_pct > 0:
                splits_data = [{'user_id': s['user_id'], 'share_value': (s['share_value'] / total_pct) * 100.0} for s in splits_data]
            elif total_pct <= 0:
                # Fallback to equal percentage
                num_splits = len(splits_data)
                splits_data = [{'user_id': s['user_id'], 'share_value': 100.0 / num_splits} for s in splits_data]
                
            sum_owed = 0.0
            for idx, s in enumerate(splits_data):
                owed = round(amount_inr * (s['share_value'] / 100.0), 2)
                splits_to_insert.append((s['user_id'], owed, s['share_value']))
                sum_owed += owed
                
            diff = round(amount_inr - sum_owed, 2)
            if abs(diff) > 0.001 and splits_to_insert:
                uid, owed, val = splits_to_insert[0]
                splits_to_insert[0] = (uid, round(owed + diff, 2), val)
                
        elif split_type == 'share':
            total_shares = sum(s['share_value'] for s in splits_data)
            if total_shares <= 0:
                total_shares = float(len(splits_data))
                splits_data = [{'user_id': s['user_id'], 'share_value': 1.0} for s in splits_data]
                
            sum_owed = 0.0
            for idx, s in enumerate(splits_data):
                owed = round(amount_inr * (s['share_value'] / total_shares), 2)
                splits_to_insert.append((s['user_id'], owed, s['share_value']))
                sum_owed += owed
                
            diff = round(amount_inr - sum_owed, 2)
            if abs(diff) > 0.001 and splits_to_insert:
                uid, owed, val = splits_to_insert[0]
                splits_to_insert[0] = (uid, round(owed + diff, 2), val)
                
        elif split_type == 'unequal':
            total_val = sum(s['share_value'] for s in splits_data)
            # Check if sum matches total amount, otherwise pro-rate
            if abs(total_val - amount_inr) > 0.01 and total_val > 0:
                splits_data = [{'user_id': s['user_id'], 'share_value': (s['share_value'] / total_val) * amount_inr} for s in splits_data]
            elif total_val <= 0:
                num_splits = len(splits_data)
                splits_data = [{'user_id': s['user_id'], 'share_value': amount_inr / num_splits} for s in splits_data]
                
            sum_owed = 0.0
            for idx, s in enumerate(splits_data):
                owed = round(s['share_value'], 2)
                splits_to_insert.append((s['user_id'], owed, s['share_value']))
                sum_owed += owed
                
            diff = round(amount_inr - sum_owed, 2)
            if abs(diff) > 0.001 and splits_to_insert:
                uid, owed, val = splits_to_insert[0]
                splits_to_insert[0] = (uid, round(owed + diff, 2), val)
                
        # Insert expense
        cursor.execute(
            """
            INSERT INTO expenses (group_id, description, amount, currency, amount_inr, exchange_rate, paid_by, expense_date, split_type, notes, is_settlement, import_row)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            """,
            (group_id, description, amount, currency, amount_inr, exchange_rate, paid_by, expense_date, split_type, notes)
        )
        expense_id = cursor.lastrowid
        
        # Insert splits
        for uid, owed, val in splits_to_insert:
            cursor.execute(
                """
                INSERT INTO expense_splits (expense_id, user_id, amount_owed, share_value)
                VALUES (?, ?, ?, ?)
                """,
                (expense_id, uid, owed, val)
            )
            
        conn.commit()
        return jsonify({'id': expense_id, 'message': 'Expense created successfully'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()

# ----------------- SETTLEMENT ENDPOINTS -----------------

@app.route('/api/groups/<int:group_id>/settlements', methods=['GET'])
@auth.token_required
def get_settlements(current_user_id, group_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.id, s.amount, s.settlement_date, s.import_row,
               u_from.name as from_name, u_from.id as from_id,
               u_to.name as to_name, u_to.id as to_id
        FROM settlements s
        JOIN users u_from ON s.paid_by = u_from.id
        JOIN users u_to ON s.paid_to = u_to.id
        WHERE s.group_id = ?
        ORDER BY s.settlement_date DESC, s.id DESC
        """,
        (group_id,)
    )
    rows = cursor.fetchall()
    settlements_list = [{
        'id': r['id'],
        'amount': r['amount'],
        'settlement_date': r['settlement_date'],
        'import_row': r['import_row'],
        'from_user': {'id': r['from_id'], 'name': r['from_name']},
        'to_user': {'id': r['to_id'], 'name': r['to_name']}
    } for r in rows]
    conn.close()
    return jsonify(settlements_list)

@app.route('/api/groups/<int:group_id>/settlements', methods=['POST'])
@auth.token_required
def create_settlement(current_user_id, group_id):
    data = request.get_json() or {}
    paid_by = data.get('paid_by')
    paid_to = data.get('paid_to')
    amount = data.get('amount')
    settlement_date = data.get('settlement_date') or datetime.date.today().strftime('%Y-%m-%d')
    
    if paid_by is None or paid_to is None or amount is None:
        return jsonify({'message': 'Missing required fields'}), 400
        
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO settlements (group_id, paid_by, paid_to, amount, settlement_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (group_id, paid_by, paid_to, amount, settlement_date)
        )
        conn.commit()
        return jsonify({'message': 'Settlement recorded successfully'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()

# ----------------- BALANCES & DEBT MINIMIZATION -----------------

@app.route('/api/groups/<int:group_id>/balances', methods=['GET'])
@auth.token_required
def get_group_balances(current_user_id, group_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch all members of the group
    cursor.execute(
        """
        SELECT u.id, u.name, u.is_guest 
        FROM group_members gm
        JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id = ?
        """,
        (group_id,)
    )
    member_rows = cursor.fetchall()
    members = {r['id']: {'name': r['name'], 'is_guest': bool(r['is_guest']), 'paid': 0.0, 'owed': 0.0, 'net': 0.0} for r in member_rows}
    
    if not members:
        conn.close()
        return jsonify({'balances': {}, 'settlements': []})
        
    # 2. Add total paid in expenses
    cursor.execute(
        """
        SELECT paid_by, SUM(amount_inr) as total_paid FROM expenses
        WHERE group_id = ? AND paid_by IS NOT NULL
        GROUP BY paid_by
        """,
        (group_id,)
    )
    paid_rows = cursor.fetchall()
    for pr in paid_rows:
        if pr['paid_by'] in members:
            members[pr['paid_by']]['paid'] += pr['total_paid']
            
    # 3. Add total owed from splits
    cursor.execute(
        """
        SELECT es.user_id, SUM(es.amount_owed) as total_owed 
        FROM expense_splits es
        JOIN expenses e ON es.expense_id = e.id
        WHERE e.group_id = ?
        GROUP BY es.user_id
        """,
        (group_id,)
    )
    owed_rows = cursor.fetchall()
    for orow in owed_rows:
        if orow['user_id'] in members:
            members[orow['user_id']]['owed'] += orow['total_owed']
            
    # 4. Include settlements:
    # A settlement from A to B:
    # A paid (so they get a credit: + amount)
    # B received (so they owe / reduce credit: - amount)
    cursor.execute(
        """
        SELECT paid_by, paid_to, SUM(amount) as total_amount 
        FROM settlements
        WHERE group_id = ?
        GROUP BY paid_by, paid_to
        """,
        (group_id,)
    )
    settlement_rows = cursor.fetchall()
    for sr in settlement_rows:
        p_by = sr['paid_by']
        p_to = sr['paid_to']
        amt = sr['total_amount']
        if p_by in members:
            members[p_by]['paid'] += amt
        if p_to in members:
            members[p_to]['owed'] += amt
            
    # 5. Calculate net balance
    net_balances_for_algo = {}
    for m_id, m_data in members.items():
        m_data['net'] = round(m_data['paid'] - m_data['owed'], 2)
        net_balances_for_algo[m_id] = m_data['net']
        
    # 6. Minimize debts
    minimized_txs = debt.minimize_debts(net_balances_for_algo)
    
    # Map user IDs back to names
    user_names = {m_id: m_data['name'] for m_id, m_data in members.items()}
    
    formatted_txs = []
    for tx in minimized_txs:
        formatted_txs.append({
            'from_user_id': tx['from_user_id'],
            'from_user_name': user_names.get(tx['from_user_id'], f"User {tx['from_user_id']}"),
            'to_user_id': tx['to_user_id'],
            'to_user_name': user_names.get(tx['to_user_id'], f"User {tx['to_user_id']}"),
            'amount': tx['amount']
        })
        
    # 7. Formulate individual breakdown: which expenses/settlements make up each person's balances
    # We will list expenses where they paid, and splits they owe
    cursor.execute(
        """
        SELECT e.id, e.description, e.amount_inr, e.paid_by, e.expense_date
        FROM expenses e
        WHERE e.group_id = ?
        ORDER BY e.expense_date DESC
        """,
        (group_id,)
    )
    group_expenses = cursor.fetchall()
    
    breakdown = {}
    for m_id, m_data in members.items():
        breakdown[m_id] = {
            'user_name': m_data['name'],
            'total_paid': m_data['paid'],
            'total_owed': m_data['owed'],
            'net_balance': m_data['net'],
            'details': []
        }
        
    for exp in group_expenses:
        # If user paid for this expense
        p_by = exp['paid_by']
        if p_by in breakdown:
            breakdown[p_by]['details'].append({
                'type': 'payment_made',
                'description': exp['description'],
                'amount': exp['amount_inr'],
                'date': exp['expense_date']
            })
            
        # Get splits for this expense
        cursor.execute(
            "SELECT user_id, amount_owed FROM expense_splits WHERE expense_id = ?",
            (exp['id'],)
        )
        splits = cursor.fetchall()
        for sp in splits:
            u_id = sp['user_id']
            if u_id in breakdown:
                breakdown[u_id]['details'].append({
                    'type': 'share_owed',
                    'description': f"Share of: {exp['description']}",
                    'amount': -sp['amount_owed'],
                    'date': exp['expense_date']
                })
                
    # Add settlements details
    cursor.execute(
        """
        SELECT s.paid_by, s.paid_to, s.amount, s.settlement_date,
               u_from.name as from_name, u_to.name as to_name
        FROM settlements s
        JOIN users u_from ON s.paid_by = u_from.id
        JOIN users u_to ON s.paid_to = u_to.id
        WHERE s.group_id = ?
        ORDER BY s.settlement_date DESC
        """,
        (group_id,)
    )
    group_settlements = cursor.fetchall()
    for s in group_settlements:
        p_by = s['paid_by']
        p_to = s['paid_to']
        amt = s['amount']
        date = s['settlement_date']
        
        if p_by in breakdown:
            breakdown[p_by]['details'].append({
                'type': 'settlement_paid',
                'description': f"Settled with {s['to_name']}",
                'amount': amt,
                'date': date
            })
        if p_to in breakdown:
            breakdown[p_to]['details'].append({
                'type': 'settlement_received',
                'description': f"Received settlement from {s['from_name']}",
                'amount': -amt,
                'date': date
            })
            
    conn.close()
    
    # Convert breakdown keys to string names for easy frontend processing
    readable_breakdown = {members[m_id]['name']: b_data for m_id, b_data in breakdown.items()}
    readable_balances = {members[m_id]['name']: m_data for m_id, m_data in members.items()}
    
    return jsonify({
        'balances': readable_balances,
        'minimized_debts': formatted_txs,
        'breakdown': readable_breakdown
    })

# ----------------- CSV UPLOAD & ANOMALIES -----------------

@app.route('/api/groups/<int:group_id>/import', methods=['POST'])
@auth.token_required
def upload_csv(current_user_id, group_id):
    if 'file' not in request.files:
        return jsonify({'message': 'No file part in the request'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No file selected'}), 400
        
    if not file.filename.endswith('.csv'):
        return jsonify({'message': 'Only CSV files are allowed'}), 400
        
    # Read rate parameter from query parameter if customized
    custom_rate = request.args.get('rate', type=float)
    
    # Save file to a temporary location
    temp_dir = tempfile.gettempdir()
    temp_filepath = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")
    file.save(temp_filepath)
    
    session_id = str(uuid.uuid4())
    
    try:
        import_summary = importer.import_csv_data(
            temp_filepath, group_id, session_id=session_id, exchange_rate_override=custom_rate
        )
        return jsonify(import_summary), 200
    except Exception as e:
        return jsonify({'message': f'CSV import failed: {str(e)}'}), 500
    finally:
        # Cleanup file
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

@app.route('/api/import/anomalies/<session_id>', methods=['GET'])
@auth.token_required
def get_anomalies(current_user_id, session_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, row_number, anomaly_type, description, action_taken, resolved 
        FROM import_anomalies
        WHERE session_id = ?
        ORDER BY row_number ASC, id ASC
        """,
        (session_id,)
    )
    rows = cursor.fetchall()
    anomalies_list = [{
        'id': r['id'],
        'row_number': r['row_number'],
        'anomaly_type': r['anomaly_type'],
        'description': r['description'],
        'action_taken': r['action_taken'],
        'resolved': bool(r['resolved'])
    } for r in rows]
    conn.close()
    return jsonify(anomalies_list)

@app.route('/api/import/anomalies/<session_id>/resolve/<int:anomaly_id>', methods=['POST'])
@auth.token_required
def resolve_anomaly(current_user_id, session_id, anomaly_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE import_anomalies SET resolved = 1 WHERE id = ? AND session_id = ?",
            (anomaly_id, session_id)
        )
        conn.commit()
        return jsonify({'message': 'Anomaly marked as resolved'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    seed_data()
    # Running locally on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
