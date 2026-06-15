import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Plus, 
  Upload, 
  ArrowRight, 
  TrendingDown, 
  TrendingUp, 
  CheckCircle, 
  AlertTriangle, 
  Info, 
  LogOut, 
  DollarSign, 
  Calendar, 
  Filter, 
  RefreshCw, 
  UserPlus,
  FileSpreadsheet
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:5000/api';

function App() {
  // Authentication states
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [user, setUser] = useState(null);
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authName, setAuthName] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);
  const [authError, setAuthError] = useState('');

  // App core states
  const [groups, setGroups] = useState([]);
  const [activeGroup, setActiveGroup] = useState(null);
  const [members, setMembers] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [balances, setBalances] = useState({});
  const [minimizedDebts, setMinimizedDebts] = useState([]);
  const [ledgerBreakdown, setLedgerBreakdown] = useState({});
  
  // Modals & Panels
  const [isExpenseModalOpen, setIsExpenseModalOpen] = useState(false);
  const [isSettlementModalOpen, setIsSettlementModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importSummary, setImportSummary] = useState(null);
  const [importAnomalies, setImportAnomalies] = useState([]);
  const [anomalyFilter, setAnomalyFilter] = useState('ALL'); // ALL, CRITICAL, WARNING
  const [exchangeRateInput, setExchangeRateInput] = useState('84.5');
  
  // New Expense form state
  const [expDesc, setExpDesc] = useState('');
  const [expAmount, setExpAmount] = useState('');
  const [expCurrency, setExpCurrency] = useState('INR');
  const [expPayer, setExpPayer] = useState('');
  const [expDate, setExpDate] = useState(new Date().toISOString().split('T')[0]);
  const [expSplitType, setExpSplitType] = useState('equal');
  const [expSplitsDetail, setExpSplitsDetail] = useState({}); // user_id -> share_value (percent/share/unequal amount)
  const [expNotes, setExpNotes] = useState('');
  const [expenseError, setExpenseError] = useState('');

  // New Settlement form state
  const [setFrom, setSetFrom] = useState('');
  const [setTo, setSetTo] = useState('');
  const [setAmount, setSetAmount] = useState('');
  const [setDate, setSetDate] = useState(new Date().toISOString().split('T')[0]);
  const [settlementError, setSettlementError] = useState('');

  // Load user profile on launch
  useEffect(() => {
    if (token) {
      fetch(`${API_BASE}/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      .then(res => {
        if (res.status === 401) {
          handleLogout();
          throw new Error('Expired token');
        }
        return res.json();
      })
      .then(data => setUser(data))
      .catch(err => console.error(err));
    }
  }, [token]);

  // Load groups when user is logged in
  useEffect(() => {
    if (user) {
      fetchGroups();
    }
  }, [user]);

  // Load group details when group changes
  useEffect(() => {
    if (activeGroup) {
      fetchGroupDetails(activeGroup.id);
    }
  }, [activeGroup]);

  // Dynamic splits helper when payer/split selection or date changes
  useEffect(() => {
    if (members.length > 0) {
      // Filter out members who were not active on expDate
      const activeOnDate = members.filter(m => {
        const joined = m.joined_at;
        const left = m.left_at;
        return joined <= expDate && (!left || left >= expDate);
      });
      
      const initialSplits = {};
      activeOnDate.forEach(m => {
        // preserve existing input values if available
        initialSplits[m.id] = expSplitsDetail[m.id] || (expSplitType === 'percentage' ? (100 / activeOnDate.length).toFixed(1) : '1');
      });
      setExpSplitsDetail(initialSplits);
      
      // Default payer if not set or inactive
      if (!expPayer || !activeOnDate.some(m => m.id === parseInt(expPayer))) {
        if (activeOnDate.length > 0) {
          setExpPayer(activeOnDate[0].id.toString());
        }
      }
    }
  }, [members, expDate, expSplitType]);

  const fetchGroups = () => {
    fetch(`${API_BASE}/groups`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => {
      setGroups(data);
      if (data.length > 0) {
        // Auto-select flatmates group
        const flatmates = data.find(g => g.name === 'Flatmates') || data[0];
        setActiveGroup(flatmates);
      }
    })
    .catch(err => console.error(err));
  };

  const fetchGroupDetails = (groupId) => {
    const headers = { 'Authorization': `Bearer ${token}` };
    
    // Members
    fetch(`${API_BASE}/groups/${groupId}/members`, { headers })
      .then(res => res.json())
      .then(data => setMembers(data))
      .catch(err => console.error(err));

    // Expenses
    fetch(`${API_BASE}/groups/${groupId}/expenses`, { headers })
      .then(res => res.json())
      .then(data => setExpenses(data))
      .catch(err => console.error(err));

    // Settlements
    fetch(`${API_BASE}/groups/${groupId}/settlements`, { headers })
      .then(res => res.json())
      .then(data => setSettlements(data))
      .catch(err => console.error(err));

    // Balances
    fetch(`${API_BASE}/groups/${groupId}/balances`, { headers })
      .then(res => res.json())
      .then(data => {
        setBalances(data.balances || {});
        setMinimizedDebts(data.minimized_debts || []);
        setLedgerBreakdown(data.breakdown || {});
      })
      .catch(err => console.error(err));
  };

  const handleLogin = (e) => {
    e.preventDefault();
    setAuthError('');
    fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: authEmail, password: authPassword })
    })
    .then(res => {
      if (!res.ok) throw new Error('Invalid login credentials');
      return res.json();
    })
    .then(data => {
      localStorage.setItem('token', data.token);
      setToken(data.token);
      setUser(data.user);
    })
    .catch(err => setAuthError(err.message));
  };

  const handleRegister = (e) => {
    e.preventDefault();
    setAuthError('');
    fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: authName, email: authEmail, password: authPassword })
    })
    .then(res => {
      if (!res.ok) throw new Error('Registration failed. Name or email may be taken.');
      return res.json();
    })
    .then(data => {
      localStorage.setItem('token', data.token);
      setToken(data.token);
      setUser(data.user);
    })
    .catch(err => setAuthError(err.message));
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken('');
    setUser(null);
    setGroups([]);
    setActiveGroup(null);
  };

  const handleCreateExpense = (e) => {
    e.preventDefault();
    setExpenseError('');
    
    // Format splits payload
    const splitsPayload = Object.keys(expSplitsDetail).map(uid => ({
      user_id: parseInt(uid),
      share_value: parseFloat(expSplitsDetail[uid]) || 0
    }));

    const payload = {
      description: expDesc,
      amount: parseFloat(expAmount),
      currency: expCurrency,
      paid_by: parseInt(expPayer),
      expense_date: expDate,
      split_type: expSplitType,
      notes: expNotes,
      splits: splitsPayload
    };

    fetch(`${API_BASE}/groups/${activeGroup.id}/expenses`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    })
    .then(res => {
      if (!res.ok) return res.json().then(data => { throw new Error(data.message) });
      return res.json();
    })
    .then(() => {
      setIsExpenseModalOpen(false);
      fetchGroupDetails(activeGroup.id);
      // reset form
      setExpDesc('');
      setExpAmount('');
      setExpNotes('');
    })
    .catch(err => setExpenseError(err.message));
  };

  const handleCreateSettlement = (e) => {
    e.preventDefault();
    setSettlementError('');

    fetch(`${API_BASE}/groups/${activeGroup.id}/settlements`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        paid_by: parseInt(setFrom),
        paid_to: parseInt(setTo),
        amount: parseFloat(setAmount),
        settlement_date: setDate
      })
    })
    .then(res => {
      if (!res.ok) return res.json().then(data => { throw new Error(data.message) });
      return res.json();
    })
    .then(() => {
      setIsSettlementModalOpen(false);
      fetchGroupDetails(activeGroup.id);
      setSetAmount('');
    })
    .catch(err => setSettlementError(err.message));
  };

  const handleCSVImport = (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('csv-file-input');
    if (!fileInput || !fileInput.files[0]) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    fetch(`${API_BASE}/groups/${activeGroup.id}/import?rate=${exchangeRateInput}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    })
    .then(res => {
      if (!res.ok) return res.json().then(data => { throw new Error(data.message) });
      return res.json();
    })
    .then(summary => {
      setImportSummary(summary);
      // Fetch anomalies for this session
      fetchAnomalies(summary.session_id);
      fetchGroupDetails(activeGroup.id);
    })
    .catch(err => alert(err.message));
  };

  const fetchAnomalies = (sessionId) => {
    fetch(`${API_BASE}/import/anomalies/${sessionId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => setImportAnomalies(data))
    .catch(err => console.error(err));
  };

  const handleToggleResolveAnomaly = (anomalyId, currentStatus) => {
    fetch(`${API_BASE}/import/anomalies/${importSummary.session_id}/resolve/${anomalyId}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(() => {
      // Update local state
      setImportAnomalies(prev => prev.map(a => a.id === anomalyId ? { ...a, resolved: true } : a));
    })
    .catch(err => console.error(err));
  };

  // Helper to categorize anomalies as Critical or Warning
  const getAnomalyCategory = (type) => {
    const criticals = ['ZERO_AMOUNT', 'INVALID_AMOUNT', 'MISSING_PAYER', 'UNKNOWN_PERSON', 'EXACT_DUPLICATE'];
    if (criticals.includes(type)) return 'CRITICAL';
    return 'WARNING';
  };

  const filteredAnomalies = importAnomalies.filter(a => {
    if (anomalyFilter === 'ALL') return true;
    return getAnomalyCategory(a.anomaly_type) === anomalyFilter;
  });

  // Render Authentication Page
  if (!token || !user) {
    return (
      <div className="auth-wrapper">
        <div className="glass-card auth-card animated-in">
          <h1 className="auth-title">SplitRight</h1>
          <p className="auth-subtitle">Sleek shared expenses tracking with anomaly detection</p>
          
          <form onSubmit={isRegistering ? handleRegister : handleLogin}>
            {isRegistering && (
              <div className="form-group">
                <label>Name</label>
                <input 
                  type="text" 
                  className="form-control" 
                  value={authName} 
                  onChange={e => setAuthName(e.target.value)}
                  placeholder="e.g. Aisha" 
                  required
                />
              </div>
            )}
            <div className="form-group">
              <label>Email Address</label>
              <input 
                type="email" 
                className="form-control" 
                value={authEmail} 
                onChange={e => setAuthEmail(e.target.value)}
                placeholder="flatmate@splitright.com" 
                required
              />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input 
                type="password" 
                className="form-control" 
                value={authPassword} 
                onChange={e => setAuthPassword(e.target.value)}
                placeholder="••••••••" 
                required
              />
            </div>

            {authError && <p className="text-danger" style={{ marginBottom: 16, fontSize: '0.875rem' }}>{authError}</p>}
            
            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginBottom: 16 }}>
              {isRegistering ? 'Create Account' : 'Sign In'}
            </button>
          </form>

          <p style={{ textAlign: 'center', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            {isRegistering ? 'Already have an account? ' : "Don't have an account? "}
            <span 
              onClick={() => { setIsRegistering(!isRegistering); setAuthError(''); }}
              style={{ color: 'var(--color-primary)', cursor: 'pointer', fontWeight: 500 }}
            >
              {isRegistering ? 'Sign In' : 'Register'}
            </span>
          </p>
          
          <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-muted)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            <p style={{ textAlign: 'center' }}>Demo Accounts (Password: <code>password123</code>):</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
              <div>• aisha@splitright.com</div>
              <div>• rohan@splitright.com</div>
              <div>• priya@splitright.com</div>
              <div>• meera@splitright.com</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Active group members filtering
  const activeMembersOnDate = members.filter(m => {
    return m.joined_at <= expDate && (!m.left_at || m.left_at >= expDate);
  });

  return (
    <div className="dashboard-grid">
      {/* SIDEBAR */}
      <aside style={{ background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-muted)', padding: '24px 20px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
          <div style={{ background: 'var(--color-primary)', width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 'bold' }}>SR</div>
          <span style={{ fontSize: '1.25rem', fontWeight: 700 }}>SplitRight</span>
        </div>

        <div style={{ flex: 1 }}>
          <h4 style={{ textTransform: 'uppercase', fontSize: '0.75rem', color: 'var(--text-muted)', letterSpacing: '0.05em', marginBottom: 12 }}>My Groups</h4>
          {groups.map(g => (
            <div 
              key={g.id} 
              onClick={() => setActiveGroup(g)}
              className="animated-in"
              style={{ 
                padding: '12px 16px', 
                borderRadius: 'var(--radius-sm)', 
                background: activeGroup?.id === g.id ? 'var(--bg-input)' : 'transparent',
                border: '1px solid',
                borderColor: activeGroup?.id === g.id ? 'var(--border-muted)' : 'transparent',
                cursor: 'pointer',
                marginBottom: 8,
                transition: 'all var(--transition-fast)'
              }}
            >
              <div style={{ fontWeight: 500, fontSize: '0.925rem' }}>{g.name}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{g.description}</div>
            </div>
          ))}
        </div>

        {/* User Card */}
        <div style={{ borderTop: '1px solid var(--border-muted)', paddingTop: 16, marginTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{user.name}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{user.email}</div>
            </div>
            <button onClick={handleLogout} className="btn btn-secondary btn-sm" style={{ padding: 6 }}>
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* MAIN VIEW */}
      <main className="main-content">
        {activeGroup ? (
          <div className="animated-in" style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
            {/* Header Area */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
              <div>
                <h1 style={{ fontSize: '2rem', marginBottom: 4 }}>{activeGroup.name} Ledger</h1>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>{activeGroup.description}</p>
              </div>

              <div style={{ display: 'flex', gap: 12 }}>
                <button onClick={() => setIsExpenseModalOpen(true)} className="btn btn-primary">
                  <Plus size={18} /> Add Expense
                </button>
                <button onClick={() => setIsSettlementModalOpen(true)} className="btn btn-success">
                  <ArrowRight size={18} /> Record Settlement
                </button>
                <button onClick={() => { setIsImportModalOpen(true); setImportSummary(null); }} className="btn btn-secondary">
                  <Upload size={18} /> Import CSV
                </button>
              </div>
            </div>

            {/* Quick Balances Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 20 }}>
              {Object.keys(balances).map(name => {
                const bal = balances[name];
                const isNegative = bal.net < 0;
                return (
                  <div key={name} className="glass-card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{name} {bal.is_guest && <span className="badge badge-info" style={{fontSize: '0.6rem'}}>Guest</span>}</span>
                    <h3 style={{ fontSize: '1.75rem', color: isNegative ? 'var(--color-danger)' : 'var(--color-success)' }}>
                      {isNegative ? '-' : '+'}₹{Math.abs(bal.net).toFixed(2)}
                    </h3>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      <span>Paid: ₹{bal.paid.toFixed(2)}</span>
                      <span>Owed: ₹{bal.owed.toFixed(2)}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Debt Minimization Panel */}
            <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <TrendingDown size={20} className="text-warning" /> Suggested Settlements (Debt Minimization)
                </h2>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Minimum Transactions algorithm applied</span>
              </div>
              
              {minimizedDebts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)', fontSize: '0.95rem' }}>
                  <CheckCircle size={32} className="text-success" style={{ margin: '0 auto 8px', display: 'block' }} />
                  Everyone is fully settled up!
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
                  {minimizedDebts.map((tx, idx) => (
                    <div 
                      key={idx} 
                      style={{ 
                        background: 'var(--bg-secondary)', 
                        border: '1px solid var(--border-muted)', 
                        borderRadius: 'var(--radius-sm)', 
                        padding: '16px 20px', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'space-between' 
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>From {tx.from_user_name}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>To {tx.to_user_name}</div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontSize: '1.2rem', fontWeight: 'bold', color: 'var(--color-warning)' }}>₹{tx.amount.toFixed(2)}</span>
                        <button 
                          onClick={() => {
                            setSetFrom(tx.from_user_id.toString());
                            setSetTo(tx.to_user_id.toString());
                            setSetAmount(tx.amount.toString());
                            setIsSettlementModalOpen(true);
                          }}
                          className="btn btn-primary btn-sm"
                        >
                          Settle
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* CSV Import Report (if active) */}
            {importSummary && (
              <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: 20, borderColor: 'var(--color-primary)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h2 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <FileSpreadsheet size={20} className="text-success" /> CSV Import Anomaly Report
                  </h2>
                  <button onClick={() => setImportSummary(null)} className="btn btn-secondary btn-sm">Dismiss Report</button>
                </div>
                
                {/* Stats Summary Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
                  <div style={{ background: 'var(--bg-secondary)', padding: 12, borderRadius: 8, textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Processed</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{importSummary.rows_processed}</div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: 12, borderRadius: 8, textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Imported</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--color-success)' }}>{importSummary.rows_imported}</div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: 12, borderRadius: 8, textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Skipped</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--color-danger)' }}>{importSummary.rows_skipped}</div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: 12, borderRadius: 8, textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Anomalies</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--color-warning)' }}>{importSummary.anomalies_count}</div>
                  </div>
                </div>

                {/* Filters */}
                <div style={{ display: 'flex', justifyBetween: 'center', alignItems: 'center', gap: 16 }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Filter Anomalies:</span>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {['ALL', 'CRITICAL', 'WARNING'].map(filter => (
                      <button 
                        key={filter} 
                        onClick={() => setAnomalyFilter(filter)}
                        className={`btn btn-sm ${anomalyFilter === filter ? 'btn-primary' : 'btn-secondary'}`}
                      >
                        {filter}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Anomalies Table */}
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>CSV Row</th>
                        <th>Type</th>
                        <th>Description</th>
                        <th>Action Taken</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredAnomalies.map(anomaly => (
                        <tr key={anomaly.id} style={{ opacity: anomaly.resolved ? 0.6 : 1 }}>
                          <td>Row {anomaly.row_number}</td>
                          <td>
                            <span className={`badge ${
                              getAnomalyCategory(anomaly.anomaly_type) === 'CRITICAL' ? 'badge-danger' : 'badge-warning'
                            }`}>
                              {anomaly.anomaly_type}
                            </span>
                          </td>
                          <td style={{ fontSize: '0.85rem' }}>{anomaly.description}</td>
                          <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{anomaly.action_taken}</td>
                          <td>
                            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                              <input 
                                type="checkbox" 
                                checked={anomaly.resolved} 
                                disabled={anomaly.resolved}
                                onChange={() => handleToggleResolveAnomaly(anomaly.id, anomaly.resolved)}
                              />
                              <span style={{ fontSize: '0.75rem' }}>{anomaly.resolved ? 'Resolved' : 'Pending'}</span>
                            </label>
                          </td>
                        </tr>
                      ))}
                      {filteredAnomalies.length === 0 && (
                        <tr>
                          <td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No anomalies found for this filter.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Expenses & Ledger History Tabs */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 32, alignItems: 'start' }}>
              
              {/* Expense History */}
              <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                <h2 style={{ fontSize: '1.25rem' }}>Expenses History</h2>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Paid By</th>
                        <th>Amount</th>
                        <th>Splits</th>
                      </tr>
                    </thead>
                    <tbody>
                      {expenses.map(exp => (
                        <tr key={exp.id}>
                          <td style={{ whiteSpace: 'nowrap' }}>{exp.expense_date}</td>
                          <td>
                            <div style={{ fontWeight: 500 }}>{exp.description}</div>
                            {exp.notes && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{exp.notes}</div>}
                          </td>
                          <td>{exp.payer_name || <em className="text-danger">None (Missing)</em>}</td>
                          <td style={{ fontWeight: 600 }}>
                            {exp.currency !== 'INR' ? (
                              <div>
                                <div>₹{exp.amount_inr.toFixed(2)}</div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>({exp.amount} {exp.currency})</div>
                              </div>
                            ) : (
                              `₹${exp.amount.toFixed(2)}`
                            )}
                          </td>
                          <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            <div style={{ textTransform: 'capitalize', fontWeight: 'bold', fontSize: '0.7rem', marginBottom: 4 }}>
                              Type: {exp.split_type}
                            </div>
                            {exp.splits.map(sp => (
                              <div key={sp.user_id}>
                                {sp.member_name}: ₹{sp.amount_owed.toFixed(2)}
                              </div>
                            ))}
                          </td>
                        </tr>
                      ))}
                      {expenses.length === 0 && (
                        <tr>
                          <td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>No expenses recorded.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Individual Ledger Details */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
                
                {/* Settlements Log */}
                <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  <h2 style={{ fontSize: '1.25rem' }}>Payments / Settlements</h2>
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Details</th>
                          <th>Amount</th>
                        </tr>
                      </thead>
                      <tbody>
                        {settlements.map(set => (
                          <tr key={set.id}>
                            <td>{set.settlement_date}</td>
                            <td>
                              <div style={{ fontSize: '0.85rem' }}>
                                <strong>{set.from_user.name}</strong> paid <strong>{set.to_user.name}</strong>
                              </div>
                            </td>
                            <td style={{ fontWeight: 600, color: 'var(--color-success)' }}>₹{set.amount.toFixed(2)}</td>
                          </tr>
                        ))}
                        {settlements.length === 0 && (
                          <tr>
                            <td colSpan="3" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No settlements recorded.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Balance Breakdowns */}
                <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  <h2 style={{ fontSize: '1.25rem' }}>Individual Breakdown</h2>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {Object.keys(ledgerBreakdown).map(name => {
                      const breakdown = ledgerBreakdown[name];
                      return (
                        <details key={name} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-muted)', borderRadius: 'var(--radius-sm)', padding: 12 }}>
                          <summary style={{ cursor: 'pointer', fontWeight: 500, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>{name} Details</span>
                            <span style={{ color: breakdown.net_balance < 0 ? 'var(--color-danger)' : 'var(--color-success)' }}>
                              ₹{breakdown.net_balance.toFixed(2)}
                            </span>
                          </summary>
                          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8, fontSize: '0.85rem', borderTop: '1px solid var(--border-muted)', paddingTop: 12 }}>
                            {breakdown.details.map((item, idx) => (
                              <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', color: item.amount < 0 ? 'var(--text-muted)' : 'var(--text-primary)' }}>
                                <span>{item.date} • {item.description}</span>
                                <span style={{ fontWeight: 500, color: item.amount < 0 ? 'var(--color-danger)' : 'var(--color-success)' }}>
                                  {item.amount < 0 ? '-' : '+'}₹{Math.abs(item.amount).toFixed(2)}
                                </span>
                              </div>
                            ))}
                            {breakdown.details.length === 0 && (
                              <div style={{ color: 'var(--text-muted)' }}>No activities logged.</div>
                            )}
                          </div>
                        </details>
                      );
                    })}
                  </div>
                </div>

              </div>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: 100 }}>
            <h3>No groups available</h3>
            <p>Please register a group to get started</p>
          </div>
        )}
      </main>

      {/* ADD EXPENSE MODAL */}
      {isExpenseModalOpen && (
        <div className="modal-overlay">
          <div className="glass-card modal-content animated-in">
            <h2 style={{ marginBottom: 20 }}>Add New Expense</h2>
            <form onSubmit={handleCreateExpense}>
              <div className="form-group">
                <label>Description</label>
                <input 
                  type="text" 
                  className="form-control" 
                  value={expDesc} 
                  onChange={e => setExpDesc(e.target.value)}
                  placeholder="e.g. WiFi Bill" 
                  required 
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Amount</label>
                  <input 
                    type="number" 
                    step="0.01" 
                    className="form-control" 
                    value={expAmount} 
                    onChange={e => setExpAmount(e.target.value)}
                    placeholder="e.g. 1500" 
                    required 
                  />
                </div>
                <div className="form-group">
                  <label>Currency</label>
                  <select 
                    className="form-control" 
                    value={expCurrency} 
                    onChange={e => setExpCurrency(e.target.value)}
                  >
                    <option value="INR">INR (₹)</option>
                    <option value="USD">USD ($)</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Paid By</label>
                  <select 
                    className="form-control" 
                    value={expPayer} 
                    onChange={e => setExpPayer(e.target.value)}
                  >
                    {activeMembersOnDate.map(m => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Expense Date</label>
                  <input 
                    type="date" 
                    className="form-control" 
                    value={expDate} 
                    onChange={e => setExpDate(e.target.value)}
                    required 
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Split Type</label>
                <select 
                  className="form-control" 
                  value={expSplitType} 
                  onChange={e => setExpSplitType(e.target.value)}
                >
                  <option value="equal">Split Equally</option>
                  <option value="percentage">Split By Percentage (%)</option>
                  <option value="share">Split By Shares / Weights</option>
                  <option value="unequal">Split Unequally (Exact amounts)</option>
                </select>
              </div>

              {/* Dynamic split inputs based on type */}
              <div className="form-group" style={{ background: 'var(--bg-secondary)', padding: 16, borderRadius: 'var(--radius-sm)' }}>
                <label style={{ marginBottom: 10, display: 'block' }}>Split Details</label>
                
                {activeMembersOnDate.map(m => (
                  <div key={m.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span>{m.name}</span>
                    
                    {expSplitType === 'equal' ? (
                      <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Split equally</span>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <input 
                          type="number" 
                          step="any"
                          className="form-control" 
                          style={{ width: 100, padding: 6 }}
                          value={expSplitsDetail[m.id] || ''}
                          onChange={e => setExpSplitsDetail({ ...expSplitsDetail, [m.id]: e.target.value })}
                          required
                        />
                        <span>
                          {expSplitType === 'percentage' && '%'}
                          {expSplitType === 'share' && 'shares'}
                          {expSplitType === 'unequal' && 'INR'}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="form-group">
                <label>Notes</label>
                <textarea 
                  className="form-control" 
                  value={expNotes} 
                  onChange={e => setExpNotes(e.target.value)}
                  placeholder="Additional context..."
                />
              </div>

              {expenseError && <p className="text-danger" style={{ marginBottom: 16 }}>{expenseError}</p>}

              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => setIsExpenseModalOpen(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary">Save Expense</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* RECORD SETTLEMENT MODAL */}
      {isSettlementModalOpen && (
        <div className="modal-overlay">
          <div className="glass-card modal-content animated-in" style={{ maxWidth: 440 }}>
            <h2 style={{ marginBottom: 20 }}>Record Settlement</h2>
            <form onSubmit={handleCreateSettlement}>
              <div className="form-group">
                <label>Payer (Who paid)</label>
                <select 
                  className="form-control" 
                  value={setFrom} 
                  onChange={e => setSetFrom(e.target.value)}
                  required
                >
                  <option value="">-- Select member --</option>
                  {members.map(m => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Receiver (Who was paid)</label>
                <select 
                  className="form-control" 
                  value={setTo} 
                  onChange={e => setSetTo(e.target.value)}
                  required
                >
                  <option value="">-- Select member --</option>
                  {members.filter(m => m.id.toString() !== setFrom).map(m => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Amount (INR)</label>
                <input 
                  type="number" 
                  step="0.01" 
                  className="form-control" 
                  value={setAmount} 
                  onChange={e => setSetAmount(e.target.value)}
                  placeholder="e.g. 500" 
                  required 
                />
              </div>

              <div className="form-group">
                <label>Settlement Date</label>
                <input 
                  type="date" 
                  className="form-control" 
                  value={setDate} 
                  onChange={e => setSetDate(e.target.value)}
                  required 
                />
              </div>

              {settlementError && <p className="text-danger" style={{ marginBottom: 16 }}>{settlementError}</p>}

              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => setIsSettlementModalOpen(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-success">Record Payment</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CSV IMPORT MODAL */}
      {isImportModalOpen && (
        <div className="modal-overlay">
          <div className="glass-card modal-content animated-in" style={{ maxWidth: 440 }}>
            <h2 style={{ marginBottom: 12 }}>Import Expenses CSV</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 20 }}>
              Select your <code>expenses_export.csv</code> file. The importer will automatically detect and correct anomalies.
            </p>
            <form onSubmit={handleCSVImport}>
              <div className="form-group">
                <label>USD exchange rate (default ₹84.5)</label>
                <input 
                  type="number" 
                  step="0.01" 
                  className="form-control" 
                  value={exchangeRateInput} 
                  onChange={e => setExchangeRateInput(e.target.value)}
                  placeholder="84.5" 
                  required 
                />
              </div>

              <div className="form-group">
                <label>CSV File</label>
                <input 
                  type="file" 
                  id="csv-file-input"
                  className="form-control" 
                  accept=".csv"
                  required 
                />
              </div>

              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 24 }}>
                <button type="button" onClick={() => setIsImportModalOpen(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary">Start Import</button>
              </div>
            </form>

            {importSummary && (
              <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border-muted)' }}>
                <h4 style={{ color: 'var(--color-success)', marginBottom: 10 }}>Import Successful!</h4>
                <p style={{ fontSize: '0.85rem' }}>Anomalies found: {importSummary.anomalies_count}</p>
                <button 
                  onClick={() => setIsImportModalOpen(false)} 
                  className="btn btn-secondary btn-sm" 
                  style={{ marginTop: 10, width: '100%' }}
                >
                  View Anomaly Report Dashboard
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
