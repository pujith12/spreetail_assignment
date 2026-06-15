def minimize_debts(net_balances):
    """
    Minimize debts using a greedy algorithm.
    
    Parameters:
      net_balances (dict): A dictionary mapping user identifiers (like user ID or name) 
                           to their net balance (float). Positive values mean they are 
                           owed money (creditors), negative values mean they owe money (debtors).
                           
    Returns:
      list: A list of transactions in the format:
            [{'from': user_id, 'to': user_id, 'amount': float}]
    """
    # Round balances and exclude users who are already settled (balance ~ 0)
    balances = {k: round(v, 2) for k, v in net_balances.items()}
    
    debtors = []
    creditors = []
    
    for user, bal in balances.items():
        if bal < -0.005:
            debtors.append([user, bal])
        elif bal > 0.005:
            creditors.append([user, bal])
            
    # Sort: debtors ascending (most negative first), creditors descending (most positive first)
    debtors.sort(key=lambda x: x[1])
    creditors.sort(key=lambda x: x[1], reverse=True)
    
    transactions = []
    
    d_idx = 0
    c_idx = 0
    
    while d_idx < len(debtors) and c_idx < len(creditors):
        debtor_user, debtor_bal = debtors[d_idx]
        creditor_user, creditor_bal = creditors[c_idx]
        
        # Debtor owes debtor_bal (negative). Creditor is owed creditor_bal (positive).
        amount_to_settle = min(abs(debtor_bal), creditor_bal)
        amount_to_settle = round(amount_to_settle, 2)
        
        if amount_to_settle > 0:
            transactions.append({
                'from_user_id': debtor_user,
                'to_user_id': creditor_user,
                'amount': amount_to_settle
            })
            
            # Update balances
            debtors[d_idx][1] += amount_to_settle
            creditors[c_idx][1] -= amount_to_settle
            
        # Move pointers if balance is settled
        if abs(debtors[d_idx][1]) < 0.005:
            d_idx += 1
        if creditors[c_idx][1] < 0.005:
            c_idx += 1
            
        # Re-sort remaining to maintain optimal greedy match
        if d_idx < len(debtors):
            # Sort remaining from most negative to least negative
            debtors[d_idx:] = sorted(debtors[d_idx:], key=lambda x: x[1])
        if c_idx < len(creditors):
            # Sort remaining from most positive to least positive (descending)
            creditors[c_idx:] = sorted(creditors[c_idx:], key=lambda x: x[1], reverse=True)
            
    return transactions
