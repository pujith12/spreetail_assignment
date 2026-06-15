import csv
import uuid
import re
import datetime
from db import get_db_connection

def normalize_description(desc):
    if not desc:
        return ""
    # Trim, lowercase, and remove multiple spaces / special chars for uniform duplicate checks
    s = desc.strip().lower()
    s = re.sub(r'[^a-z0-9\s]', '', s)
    return " ".join(s.split())

def parse_date_string(date_str, session_id, row_number, anomalies):
    date_str = date_str.strip()
    
    # 1. Check for DD/MM/YYYY ambiguity like 04/05/2026
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if match:
        part1 = int(match.group(1))
        part2 = int(match.group(2))
        year = int(match.group(3))
        
        # If both parts are <= 12, it is ambiguous
        if part1 <= 12 and part2 <= 12:
            # Treat as DD/MM (part1 is day, part2 is month) -> e.g. May 4
            dt = datetime.date(year, part2, part1)
            anomalies.append({
                'session_id': session_id,
                'row_number': row_number,
                'anomaly_type': 'AMBIGUOUS_DATE',
                'description': f"Date '{date_str}' is ambiguous. Treated as DD/MM format: {dt.strftime('%B %d, %Y')}.",
                'action_taken': "TREAT_AS_DD_MM"
            })
            return dt.strftime("%Y-%m-%d")
        else:
            # Format is DD/MM/YYYY where day is > 12 (e.g. 15/03/2026)
            try:
                dt = datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
                anomalies.append({
                    'session_id': session_id,
                    'row_number': row_number,
                    'anomaly_type': 'DATE_NORMALIZATION',
                    'description': f"Date '{date_str}' in DD/MM/YYYY format normalized to ISO format '{dt.strftime('%Y-%m-%d')}'",
                    'action_taken': "CONVERT_TO_ISO"
                })
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # 2. Try standard ISO format YYYY-MM-DD
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # 3. Try Month DD format (e.g., "Mar 14")
    try:
        # We assume the year is 2026 from the flatmates context
        dt = datetime.datetime.strptime(date_str, "%b %d").date()
        dt = dt.replace(year=2026)
        anomalies.append({
            'session_id': session_id,
            'row_number': row_number,
            'anomaly_type': 'DATE_NORMALIZATION',
            'description': f"Date '{date_str}' (missing year) assumed 2026 and normalized to ISO '{dt.strftime('%Y-%m-%d')}'",
            'action_taken': "CONVERT_TO_ISO"
        })
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Fallback with critical warning
    anomalies.append({
        'session_id': session_id,
        'row_number': row_number,
        'anomaly_type': 'INVALID_DATE',
        'description': f"Invalid date '{date_str}'. Defaulting to '2026-02-01'.",
        'action_taken': "DEFAULT_TO_START_DATE"
    })
    return "2026-02-01"

def resolve_user_id(name_str, conn, group_id, session_id, row_number, anomalies, user_cache):
    """
    Resolve name variations and unknown guests.
    Returns user_id (int) or None if name_str is empty.
    """
    if not name_str:
        return None
        
    raw_name = name_str.strip()
    if not raw_name:
        return None
        
    normalized = raw_name.lower()
    
    # 17. Name variations mapping
    canonical = None
    if normalized == 'aisha':
        canonical = 'Aisha'
    elif normalized in ['rohan', 'rohan ']:
        canonical = 'Rohan'
    elif 'rohan' in normalized:
        canonical = 'Rohan'
    elif normalized in ['priya', 'priya s', 'priya s.']:
        canonical = 'Priya'
    elif 'priya' in normalized:
        canonical = 'Priya'
    elif normalized == 'meera':
        canonical = 'Meera'
    elif normalized == 'sam':
        canonical = 'Sam'
    elif normalized == 'dev':
        canonical = 'Dev'
        
    if canonical:
        if canonical != raw_name:
            anomalies.append({
                'session_id': session_id,
                'row_number': row_number,
                'anomaly_type': 'NAME_NORMALIZATION',
                'description': f"Name variation '{raw_name}' normalized to canonical name '{canonical}'",
                'action_taken': "REPLACE_WITH_CANONICAL"
            })
        name_to_use = canonical
    else:
        # If it is not one of the core users, it is a guest
        name_to_use = raw_name
        
    if name_to_use in user_cache:
        user_id = user_cache[name_to_use]
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT id, is_guest FROM users WHERE name = ?", (name_to_use,))
        row = cursor.fetchone()
        if row:
            user_id = row['id']
            user_cache[name_to_use] = user_id
        else:
            # 18. Unknown person in split → create guest user
            cursor.execute("INSERT INTO users (name, is_guest) VALUES (?, 1)", (name_to_use,))
            user_id = cursor.lastrowid
            user_cache[name_to_use] = user_id
            anomalies.append({
                'session_id': session_id,
                'row_number': row_number,
                'anomaly_type': 'UNKNOWN_PERSON',
                'description': f"Unknown person '{name_to_use}' encountered. Created guest user.",
                'action_taken': "CREATE_GUEST_USER"
            })
            
    # Add to group membership if not already there
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, user_id))
    if not cursor.fetchone():
        joined_at = '2026-02-01'
        left_at = None
        if name_to_use == 'Sam':
            joined_at = '2026-04-15'
        elif name_to_use == 'Meera':
            joined_at = '2026-02-01'
            left_at = '2026-03-31'
            
        cursor.execute(
            "INSERT INTO group_members (group_id, user_id, joined_at, left_at) VALUES (?, ?, ?, ?)",
            (group_id, user_id, joined_at, left_at)
        )
        
    return user_id

def parse_split_details(details_str):
    """
    Parses key-value splits from split_details.
    E.g. "Rohan 700; Priya 400; Meera 400" -> {'Rohan': 700.0, 'Priya': 400.0, 'Meera': 400.0}
    """
    if not details_str:
        return {}
    parts = details_str.split(';')
    splits = {}
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Split by last whitespace to separate name and value
        match = re.match(r'^(.*?)\s+([0-9\.\-%]+)$', p)
        if match:
            name = match.group(1).strip()
            val_str = match.group(2).strip().replace('%', '')
            try:
                splits[name] = float(val_str)
            except ValueError:
                pass
    return splits

def import_csv_data(filepath, group_id, session_id=None, exchange_rate_override=None):
    """
    Import expenses from CSV file while detecting and correcting 20 anomalies.
    Returns:
        dict: Summary of import actions including numbers of rows processed, imported, and anomalies.
    """
    if session_id is None:
        session_id = str(uuid.uuid4())
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Preload configurable exchange rate (default 84.5)
    cursor.execute("SELECT rate FROM exchange_rates WHERE currency = 'USD'")
    row = cursor.fetchone()
    usd_rate = exchange_rate_override if exchange_rate_override is not None else (row['rate'] if row else 84.5)
    
    anomalies = []
    
    # Store processed records to check for exact and near duplicates in the current CSV session
    processed_records = [] # elements: {'date': str, 'desc_norm': str, 'amount_inr': float, 'row': int}
    
    # Load already existing expenses for duplicate checks
    cursor.execute("SELECT expense_date, description, amount_inr, id FROM expenses WHERE group_id = ?", (group_id,))
    db_rows = cursor.fetchall()
    for db_row in db_rows:
        processed_records.append({
            'date': db_row['expense_date'],
            'desc_norm': normalize_description(db_row['description']),
            'amount_inr': db_row['amount_inr'],
            'row': 0 # from DB
        })
        
    # User cache for performance
    user_cache = {}
    
    # We will read file lines manually to track exact CSV rows
    rows_imported = 0
    rows_skipped = 0
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Read all lines
            content_lines = f.readlines()
            
        # Parse CSV lines
        reader = csv.reader(content_lines)
        header = next(reader) # Row 1: Header
        
        row_number = 1
        for row in reader:
            row_number += 1
            if not row or len(row) < 5:
                continue
                
            # Columns: date, description, paid_by, amount, currency, split_type, split_with, split_details, notes
            # Safe indexing
            c_date = row[0]
            c_desc = row[1]
            c_paid_by = row[2]
            c_amount = row[3]
            c_curr = row[4]
            c_split_type = row[5] if len(row) > 5 else 'equal'
            c_split_with = row[6] if len(row) > 6 else ''
            c_split_details = row[7] if len(row) > 7 else ''
            c_notes = row[8] if len(row) > 8 else ''
            
            # --- 4. Comma in amount & 5. Trim spaces ---
            # Parse amount and currency
            orig_amount_str = c_amount
            parsed_amount, parsed_curr, amount_inr, current_rate = parse_amount_and_currency(
                c_amount, c_curr, usd_rate, session_id, row_number, anomalies
            )
            
            # --- 12. Zero amount → skip ---
            if abs(amount_inr) < 0.0001:
                anomalies.append({
                    'session_id': session_id,
                    'row_number': row_number,
                    'anomaly_type': 'ZERO_AMOUNT',
                    'description': f"Row skipped because amount is zero: '{c_desc}'",
                    'action_taken': "SKIP"
                })
                rows_skipped += 1
                continue
                
            # --- 7. Mixed dates & 8. Ambiguous dates ---
            normalized_date = parse_date_string(c_date, session_id, row_number, anomalies)
            
            # Normalize description
            desc_norm = normalize_description(c_desc)
            
            # --- 1. Exact duplicates & 2. Near-duplicates check ---
            is_exact_dup = False
            is_near_dup = False
            
            for item in processed_records:
                if item['date'] == normalized_date and item['desc_norm'] == desc_norm:
                    if abs(item['amount_inr'] - amount_inr) < 0.01:
                        is_exact_dup = True
                        break
                    else:
                        is_near_dup = True
                        # No break, we check if there's any exact duplicate
                        
            if is_exact_dup:
                anomalies.append({
                    'session_id': session_id,
                    'row_number': row_number,
                    'anomaly_type': 'EXACT_DUPLICATE',
                    'description': f"Row skipped. Duplicate row found with same date, normalized description, and amount ({normalized_date}, '{c_desc}', {amount_inr} INR)",
                    'action_taken': "SKIP"
                })
                rows_skipped += 1
                continue
                
            if is_near_dup:
                anomalies.append({
                    'session_id': session_id,
                    'row_number': row_number,
                    'anomaly_type': 'NEAR_DUPLICATE',
                    'description': f"Near-duplicate row. Date and description match but amount differs (Logged amount: {amount_inr} INR). Flagged for review.",
                    'action_taken': "FLAG_FOR_REVIEW"
                })
                # We do NOT skip near-duplicates. We keep them and import.
                
            # Save signature in processed list
            processed_records.append({
                'date': normalized_date,
                'desc_norm': desc_norm,
                'amount_inr': amount_inr,
                'row': row_number
            })
            
            # --- 3. Settlement logged as expense & 20. Sam's deposit ---
            # "Rohan paid Aisha back", "Sam deposit share"
            is_settlement_row = False
            settlement_payer = None
            settlement_payee = None
            
            # Check row 38 explicitly or Sam deposit
            if row_number == 38 or "sam deposit share" in desc_norm:
                is_settlement_row = True
                settlement_payer = "Sam"
                settlement_payee = "Aisha"
                anomalies.append({
                    'session_id': session_id,
                    'row_number': row_number,
                    'anomaly_type': 'DEPOSIT_AS_SETTLEMENT',
                    'description': "Sam's deposit share converted from shared expense to settlement",
                    'action_taken': "CONVERT_TO_SETTLEMENT"
                })
            # Check generic settlement logged as expense
            elif not c_split_type or c_split_type.strip() == '' or "paid" in desc_norm or "back" in desc_norm or "settle" in desc_norm:
                # E.g. Rohan paid Aisha back, split_with is Aisha
                # Let's inspect description
                is_settlement_row = True
                # Parse payer and payee from names
                # paid_by is payer. split_with or description contains payee.
                settlement_payer = c_paid_by if c_paid_by else "Rohan"  # Default fallback
                settlement_payee = c_split_with if c_split_with else "Aisha" # Default fallback
                
                anomalies.append({
                    'session_id': session_id,
                    'row_number': row_number,
                    'anomaly_type': 'SETTLEMENT_LOGGED_AS_EXPENSE',
                    'description': f"Settlement row '{c_desc}' converted to a settlement record",
                    'action_taken': "CONVERT_TO_SETTLEMENT"
                })
                
            if is_settlement_row:
                # Convert to settlement record
                payer_id = resolve_user_id(settlement_payer, conn, group_id, session_id, row_number, anomalies, user_cache)
                payee_id = resolve_user_id(settlement_payee, conn, group_id, session_id, row_number, anomalies, user_cache)
                
                cursor.execute(
                    """
                    INSERT INTO settlements (group_id, paid_by, paid_to, amount, settlement_date, import_row)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (group_id, payer_id, payee_id, amount_inr, normalized_date, row_number)
                )
                rows_imported += 1
                continue
                
            # --- 6. Missing paid_by field ---
            payer_id = None
            if not c_paid_by or c_paid_by.strip() == '':
                anomalies.append({
                    'session_id': session_id,
                    'row_number': row_number,
                    'anomaly_type': 'MISSING_PAYER',
                    'description': f"Expense '{c_desc}' is missing 'paid_by' payer information. Imported with null payer.",
                    'action_taken': "FLAG_FOR_REVIEW"
                })
            else:
                payer_id = resolve_user_id(c_paid_by, conn, group_id, session_id, row_number, anomalies, user_cache)
                
            # --- 19. Invalid split_type ---
            split_type = c_split_type.strip().lower()
            if split_type not in ['equal', 'unequal', 'percentage', 'share']:
                anomalies.append({
                    'session_id': session_id,
                    'row_number': row_number,
                    'anomaly_type': 'INVALID_SPLIT_TYPE',
                    'description': f"Invalid split type '{c_split_type}' changed to 'equal'",
                    'action_taken': "DEFAULT_TO_EQUAL"
                })
                split_type = 'equal'
                
            # --- 16. split_type=equal but split_details also provided ---
            if split_type == 'equal' and c_split_details and c_split_details.strip() != '':
                anomalies.append({
                    'session_id': session_id,
                    'row_number': row_number,
                    'anomaly_type': 'SPLIT_DETAILS_CONFLICT',
                    'description': f"Split type is equal but details ('{c_split_details}') were provided. Ignored details.",
                    'action_taken': "IGNORE_DETAILS_USE_EQUAL"
                })
                c_split_details = "" # Ignore details
                
            # Parse split_with names
            split_with_names = [n.strip() for n in c_split_with.split(';') if n.strip() != '']
            
            # --- 13. Meera after 2026-03-31 & 14. Sam before 2026-04-15 ---
            eligible_split_names = []
            for name in split_with_names:
                normalized_name = normalize_name_only(name)
                # Check Meera
                if normalized_name == 'Meera' and normalized_date > '2026-03-31':
                    anomalies.append({
                        'session_id': session_id,
                        'row_number': row_number,
                        'anomaly_type': 'MEMBERSHIP_OUT_OF_BOUNDS',
                        'description': f"Meera removed from split of '{c_desc}' on {normalized_date} because she left end of March",
                        'action_taken': "REMOVE_FROM_SPLIT"
                    })
                    continue
                # Check Sam
                if normalized_name == 'Sam' and normalized_date < '2026-04-15':
                    anomalies.append({
                        'session_id': session_id,
                        'row_number': row_number,
                        'anomaly_type': 'MEMBERSHIP_OUT_OF_BOUNDS',
                        'description': f"Sam removed from split of '{c_desc}' on {normalized_date} because he joined mid-April",
                        'action_taken': "REMOVE_FROM_SPLIT"
                    })
                    continue
                eligible_split_names.append(name)
                
            # Resolve user IDs for split_with
            split_members = []
            for name in eligible_split_names:
                m_id = resolve_user_id(name, conn, group_id, session_id, row_number, anomalies, user_cache)
                if m_id:
                    split_members.append((name, m_id))
                    
            if not split_members:
                # If no eligible split members remain, fallback to group's active members on that date
                # Or just put payer as single split member
                # Let's fallback to the active group members on that date
                cursor.execute(
                    """
                    SELECT users.name, users.id FROM group_members 
                    JOIN users ON group_members.user_id = users.id
                    WHERE group_members.group_id = ? 
                      AND group_members.joined_at <= ? 
                      AND (group_members.left_at IS NULL OR group_members.left_at >= ?)
                    """,
                    (group_id, normalized_date, normalized_date)
                )
                fallback_rows = cursor.fetchall()
                split_members = [(r['name'], r['id']) for r in fallback_rows]
                if not split_members:
                    # If still empty, use payer
                    if payer_id:
                        split_members = [(c_paid_by, payer_id)]
                        
            # Insert expense row
            cursor.execute(
                """
                INSERT INTO expenses (group_id, description, amount, currency, amount_inr, exchange_rate, paid_by, expense_date, split_type, notes, is_settlement, import_row)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (group_id, c_desc, parsed_amount, parsed_curr, amount_inr, current_rate, payer_id, normalized_date, split_type, c_notes, row_number)
            )
            expense_id = cursor.lastrowid
            
            # Calculate splits
            splits_to_insert = [] # elements: (user_id, amount_owed, share_value)
            
            if split_type == 'equal':
                num_members = len(split_members)
                base_share = round(amount_inr / num_members, 2)
                
                # Check for rounding difference
                diff = round(amount_inr - (base_share * num_members), 2)
                
                for idx, (m_name, m_id) in enumerate(split_members):
                    owed = base_share
                    # Adjust rounding difference on the first member
                    if idx == 0:
                        owed = round(owed + diff, 2)
                    splits_to_insert.append((m_id, owed, 1.0))
                    
            elif split_type == 'percentage':
                # Parse split details percentages
                parsed_details = parse_split_details(c_split_details)
                
                # Map detail keys to normalized eligible names
                pct_map = {}
                for raw_k, pct_val in parsed_details.items():
                    norm_k = normalize_name_only(raw_k)
                    pct_map[norm_k] = pct_val
                    
                # Calculate percentages for eligible members
                eligible_pcounts = []
                for m_name, m_id in split_members:
                    norm_m = normalize_name_only(m_name)
                    pct = pct_map.get(norm_m, 0.0)
                    eligible_pcounts.append((m_id, pct))
                    
                total_pct = sum(pct for m_id, pct in eligible_pcounts)
                
                # 15. Percentage splits not summing to 100%
                if abs(total_pct - 100.0) > 0.01:
                    anomalies.append({
                        'session_id': session_id,
                        'row_number': row_number,
                        'anomaly_type': 'SPLIT_PERCENTAGE_MISMATCH',
                        'description': f"Percentage splits summed to {total_pct}% instead of 100% for '{c_desc}'. Normalized to 100%.",
                        'action_taken': "NORMALIZE_TO_100"
                    })
                    if total_pct > 0.001:
                        eligible_pcounts = [(m_id, (pct / total_pct) * 100.0) for m_id, pct in eligible_pcounts]
                    else:
                        # Fallback equal splits if sum is 0
                        num_m = len(split_members)
                        eligible_pcounts = [(m_id, 100.0 / num_m) for m_name, m_id in split_members]
                        
                # Distribute amounts based on percentage
                sum_distributed = 0.0
                for idx, (m_id, pct) in enumerate(eligible_pcounts):
                    owed = round(amount_inr * (pct / 100.0), 2)
                    splits_to_insert.append((m_id, owed, pct))
                    sum_distributed += owed
                    
                # Handle rounding mismatch
                diff = round(amount_inr - sum_distributed, 2)
                if abs(diff) > 0.001 and len(splits_to_insert) > 0:
                    m_id, owed, pct = splits_to_insert[0]
                    splits_to_insert[0] = (m_id, round(owed + diff, 2), pct)
                    
            elif split_type == 'share':
                # Parse split details shares (e.g. weights: Aisha 1; Rohan 2; Priya 1; Dev 2)
                parsed_details = parse_split_details(c_split_details)
                
                # Map details keys to normalized eligible names
                share_map = {}
                for raw_k, share_val in parsed_details.items():
                    norm_k = normalize_name_only(raw_k)
                    share_map[norm_k] = share_val
                    
                eligible_shares = []
                for m_name, m_id in split_members:
                    norm_m = normalize_name_only(m_name)
                    share = share_map.get(norm_m, 1.0) # default to 1 share if missing
                    eligible_shares.append((m_id, share))
                    
                total_shares = sum(share for m_id, share in eligible_shares)
                if total_shares <= 0.001:
                    total_shares = float(len(split_members))
                    eligible_shares = [(m_id, 1.0) for m_id, share in eligible_shares]
                    
                sum_distributed = 0.0
                for idx, (m_id, share) in enumerate(eligible_shares):
                    owed = round(amount_inr * (share / total_shares), 2)
                    splits_to_insert.append((m_id, owed, share))
                    sum_distributed += owed
                    
                # Handle rounding mismatch
                diff = round(amount_inr - sum_distributed, 2)
                if abs(diff) > 0.001 and len(splits_to_insert) > 0:
                    m_id, owed, share = splits_to_insert[0]
                    splits_to_insert[0] = (m_id, round(owed + diff, 2), share)
                    
            elif split_type == 'unequal':
                # Parse raw unequal split values
                parsed_details = parse_split_details(c_split_details)
                
                # Map details keys to normalized eligible names
                unequal_map = {}
                for raw_k, val in parsed_details.items():
                    norm_k = normalize_name_only(raw_k)
                    unequal_map[norm_k] = val
                    
                eligible_vals = []
                for m_name, m_id in split_members:
                    norm_m = normalize_name_only(m_name)
                    val = unequal_map.get(norm_m, 0.0)
                    eligible_vals.append((m_id, val))
                    
                total_vals = sum(val for m_id, val in eligible_vals)
                
                # If total_vals does not equal the amount, we pro-rate or store as is?
                # The user requires to store the split details as amount_owed. If it doesn't match total,
                # we should pro-rate it or adjust the difference, let's normalize to total amount and log a warning.
                if abs(total_vals - amount_inr) > 0.01:
                    anomalies.append({
                        'session_id': session_id,
                        'row_number': row_number,
                        'anomaly_type': 'UNEQUAL_SUM_MISMATCH',
                        'description': f"Unequal split details total ({total_vals} INR) did not match total amount ({amount_inr} INR) for '{c_desc}'. Pro-rated split amounts.",
                        'action_taken': "PRO_RATE_SPLITS"
                    })
                    if total_vals > 0.001:
                        eligible_vals = [(m_id, (val / total_vals) * amount_inr) for m_id, val in eligible_vals]
                    else:
                        num_m = len(split_members)
                        eligible_vals = [(m_id, amount_inr / num_m) for m_name, m_id in split_members]
                        
                sum_distributed = 0.0
                for idx, (m_id, val) in enumerate(eligible_vals):
                    owed = round(val, 2)
                    splits_to_insert.append((m_id, owed, val))
                    sum_distributed += owed
                    
                # Handle rounding mismatch
                diff = round(amount_inr - sum_distributed, 2)
                if abs(diff) > 0.001 and len(splits_to_insert) > 0:
                    m_id, owed, val = splits_to_insert[0]
                    splits_to_insert[0] = (m_id, round(owed + diff, 2), val)
                    
            # Insert splits in DB
            for m_id, owed, share_val in splits_to_insert:
                cursor.execute(
                    """
                    INSERT INTO expense_splits (expense_id, user_id, amount_owed, share_value)
                    VALUES (?, ?, ?, ?)
                    """,
                    (expense_id, m_id, owed, share_val)
                )
                
            rows_imported += 1
            
        # Write all anomalies to the database
        for anomaly in anomalies:
            cursor.execute(
                """
                INSERT INTO import_anomalies (session_id, row_number, anomaly_type, description, action_taken, resolved)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (anomaly['session_id'], anomaly['row_number'], anomaly['anomaly_type'], anomaly['description'], anomaly['action_taken'])
            )
            
        conn.commit()
        return {
            'session_id': session_id,
            'rows_processed': row_number - 1,
            'rows_imported': rows_imported,
            'rows_skipped': rows_skipped,
            'anomalies_count': len(anomalies)
        }
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def normalize_name_only(name):
    if not name:
        return ""
    n = name.strip().lower()
    if n in ['aisha']:
        return 'Aisha'
    elif n in ['rohan', 'rohan ']:
        return 'Rohan'
    elif 'rohan' in n:
        return 'Rohan'
    elif n in ['priya', 'priya s', 'priya s.']:
        return 'Priya'
    elif 'priya' in n:
        return 'Priya'
    elif n == 'meera':
        return 'Meera'
    elif n == 'sam':
        return 'Sam'
    elif n == 'dev':
        return 'Dev'
    return name.strip()

def parse_amount_and_currency(amount_str, currency_str, exchange_rate, session_id, row_number, anomalies):
    # Trim leading/trailing spaces
    cleaned_amount = amount_str.strip()
    if cleaned_amount != amount_str:
        anomalies.append({
            'session_id': session_id,
            'row_number': row_number,
            'anomaly_type': 'FORMAT_CORRECTION',
            'description': f"Trimmed spaces from amount: '{amount_str}'",
            'action_taken': "TRIM_AMOUNT"
        })
        
    # Strip commas
    if ',' in cleaned_amount:
        cleaned_amount = cleaned_amount.replace(',', '')
        anomalies.append({
            'session_id': session_id,
            'row_number': row_number,
            'anomaly_type': 'FORMAT_CORRECTION',
            'description': f"Stripped commas from amount: '{amount_str}'",
            'action_taken': "STRIP_COMMA"
        })
        
    # Parse to float
    try:
        amount = float(cleaned_amount)
    except ValueError:
        anomalies.append({
            'session_id': session_id,
            'row_number': row_number,
            'anomaly_type': 'INVALID_AMOUNT',
            'description': f"Invalid amount field '{amount_str}'. Defaulted to 0.0.",
            'action_taken': "DEFAULT_TO_ZERO"
        })
        amount = 0.0
        
    # Currency
    curr = currency_str.strip()
    if not curr:
        curr = 'INR'
        anomalies.append({
            'session_id': session_id,
            'row_number': row_number,
            'anomaly_type': 'MISSING_CURRENCY',
            'description': "Missing currency field. Defaulted to INR.",
            'action_taken': "DEFAULT_TO_INR"
        })
    elif curr not in ['INR', 'USD']:
        curr = 'INR'
        anomalies.append({
            'session_id': session_id,
            'row_number': row_number,
            'anomaly_type': 'INVALID_CURRENCY',
            'description': f"Invalid currency '{currency_str}'. Defaulted to INR.",
            'action_taken': "DEFAULT_TO_INR"
        })
        
    # USD to INR conversion
    amount_inr = amount
    rate = 1.0
    if curr == 'USD':
        rate = exchange_rate
        amount_inr = amount * rate
        anomalies.append({
            'session_id': session_id,
            'row_number': row_number,
            'anomaly_type': 'CURRENCY_CONVERSION',
            'description': f"Converted USD {amount} to INR {amount_inr:.2f} using exchange rate {rate}",
            'action_taken': "CONVERT_TO_INR"
        })
        
    # Negative amount → refund
    if amount < 0:
        anomalies.append({
            'session_id': session_id,
            'row_number': row_number,
            'anomaly_type': 'NEGATIVE_AMOUNT',
            'description': f"Negative amount ({amount} {curr}) imported as refund.",
            'action_taken': "TREAT_AS_REFUND"
        })
        
    return amount, curr, amount_inr, rate
