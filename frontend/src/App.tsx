import React, { useState, useEffect, useRef } from 'react';
import {
  AlertCircle, CheckCircle, Clock, Lock, Send, Wifi, WifiOff,
  ChevronLeft, ChevronRight, Activity, Sliders, ShieldCheck, Fingerprint,
} from 'lucide-react';
import axios from 'axios';
import './App.css';

// ── Interfaces ────────────────────────────────────────────────────────────────

interface AuthState {
  token: string | null;
  userId: string;
  isAuthenticated: boolean;
}

interface TransactionRequest {
  amount: number;
  merchant: string;
  description: string;
  timestamp: string;
}

interface TransactionResponse {
  status: string;
  transaction_id: string;
  message: string;
}

interface Result {
  transaction_id: string;
  status: string;
  timestamp: string;
}

interface PipelineStep {
  step: number;
  name: string;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  status: 'completed' | 'skipped';
}

interface ToleranceComponents {
  habit_score:    number;
  seasonal_score: number;
  merchant_score: number;
}

interface Performance {
  pipeline_total_ms: number;
  kafka_latency_ms:  number;
  cpu_before_pct:    number;
  cpu_after_pct:     number;
  memory_before_mb:  number;
  memory_after_mb:   number;
}

interface FraudResult {
  transaction_id:       string;
  decision:             string;
  fraud_score:          number;
  layer1_score:         number;
  layer2_score?:        number;
  amount?:              number;
  merchant?:            string;
  timestamp:            string;
  decision_reason?:     string;
  tolerance_components?: ToleranceComponents;
  pipeline_steps?:      PipelineStep[];
  performance?:         Performance;
  user_balance?:        number;
}

interface ToleranceConfig {
  layer1_threshold: number;
  layer2_threshold: number;
  anomaly_ratio:    number;
  habit_weight:     number;
  seasonal_weight:  number;
  merchant_weight:  number;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const API_BASE_URL = 'http://localhost:8000';

const DEFAULT_TOLERANCE: ToleranceConfig = {
  layer1_threshold: 0.4,
  layer2_threshold: 0.7,
  anomaly_ratio:    3.0,
  habit_weight:     0.4,
  seasonal_weight:  0.2,
  merchant_weight:  0.4,
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const scoreColor = (v: number) =>
  v < 0.3 ? '#10b981' : v < 0.7 ? '#f59e0b' : '#ef4444';

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

// ── App ───────────────────────────────────────────────────────────────────────

const STORAGE_KEY = 'payguard_auth';

const App: React.FC = () => {
  // Auth — restore from localStorage on mount
  const [auth, setAuth] = useState<AuthState>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.token && parsed.isAuthenticated) return parsed;
      }
    } catch {}
    return { token: null, userId: 'user_' + Math.random().toString(36).substr(2, 9), isAuthenticated: false };
  });
  const [pin, setPin]               = useState('');
  const [authMethod, setAuthMethod] = useState<'pin' | 'fingerprint' | 'face'>('pin');
  const [userBalance, setUserBalance] = useState<number | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) { const p = JSON.parse(saved); return p.balance ?? null; }
    } catch {}
    return null;
  });

  // Transaction form
  const [transaction, setTransaction] = useState<TransactionRequest>({
    amount: 100,
    merchant: 'Starbucks Coffee',
    description: 'Normal transaction',
    timestamp: new Date().toLocaleString(),
  });

  // Results
  const [results, setResults]               = useState<Result[]>([]);
  const [consumerStatus, setConsumerStatus] = useState<FraudResult | null>(null);
  const [wsConnected, setWsConnected]       = useState(false);

  // Tolerance config
  const [toleranceConfig, setToleranceConfig]   = useState<ToleranceConfig>(DEFAULT_TOLERANCE);
  const [toleranceDirty, setToleranceDirty]     = useState(false);
  const [toleranceSaving, setToleranceSaving]   = useState(false);

  // UI state
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [success, setSuccess]   = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize]       = useState(25);

  const wsRef              = useRef<WebSocket | null>(null);
  const reconnectRef       = useRef<ReturnType<typeof setTimeout> | null>(null);
  const authRef            = useRef(auth);
  useEffect(() => { authRef.current = auth; }, [auth]);

  // ── WebSocket ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket('ws://localhost:8000/ws/fraud-results');
      ws.onopen    = () => setWsConnected(true);
      ws.onmessage = (e) => {
        // Drop messages that arrive before the user has authenticated
        if (!authRef.current.isAuthenticated) return;
        try {
          const data = JSON.parse(e.data) as FraudResult;
          setConsumerStatus(data);
          // Keep displayed balance in sync with backend deductions
          if (data.user_balance !== undefined && data.user_balance !== null) {
            setUserBalance(data.user_balance);
            try {
              const saved = localStorage.getItem(STORAGE_KEY);
              if (saved) {
                const parsed = JSON.parse(saved);
                localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...parsed, balance: data.user_balance }));
              }
            } catch {}
          }
        } catch {}
      };
      ws.onerror   = () => setWsConnected(false);
      ws.onclose   = () => {
        setWsConnected(false);
        reconnectRef.current = setTimeout(connect, 4000);
      };
      wsRef.current = ws;
    };
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, []);

  // ── Load tolerance config on mount ───────────────────────────────────────
  useEffect(() => {
    axios.get(`${API_BASE_URL}/tolerance`)
      .then(r => { setToleranceConfig(r.data); setToleranceDirty(false); })
      .catch(() => {});
  }, []);

  // ── Auth ──────────────────────────────────────────────────────────────────
  const authenticate = async () => {
    try {
      setLoading(true); setError(null);

      // If PIN auth: verify PIN first (mock)
      if (authMethod === 'pin') {
        if (!pin || !/^\d{4,6}$/.test(pin)) {
          setError('Please enter a 4–6 digit PIN');
          return;
        }
        const pinRes = await axios.post(`${API_BASE_URL}/auth/pin`, null, {
          params: { user_id: auth.userId, pin },
        });
        if (!pinRes.data.verified) {
          setError('PIN verification failed');
          return;
        }
      }
      // Fingerprint / face: instant mock approval (no server call needed)

      const tokenRes = await axios.post(`${API_BASE_URL}/token`, null, {
        params: { user_id: auth.userId },
      });
      const newAuth = { ...auth, token: tokenRes.data.access_token, isAuthenticated: true };
      const balance = tokenRes.data.balance ?? null;
      setAuth(newAuth);
      setUserBalance(balance);
      // Persist to localStorage
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...newAuth, balance }));
      // Clear any stale results from a previous session
      setResults([]);
      setConsumerStatus(null);
      setSuccess(`Authenticated as ${auth.userId}`);
      setTimeout(() => setSuccess(null), 3000);
    } catch {
      setError('Authentication failed. Is the API running on localhost:8000?');
    } finally {
      setLoading(false);
    }
  };

  // ── Logout ────────────────────────────────────────────────────────────────
  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setAuth({ token: null, userId: 'user_' + Math.random().toString(36).substr(2, 9), isAuthenticated: false });
    setUserBalance(null);
    setResults([]);
    setConsumerStatus(null);
    setPin('');
    setError(null);
    setSuccess(null);
  };

  // ── Tolerance ─────────────────────────────────────────────────────────────
  const saveTolerance = async () => {
    try {
      setToleranceSaving(true);
      await axios.put(`${API_BASE_URL}/tolerance`, toleranceConfig);
      setToleranceDirty(false);
      setSuccess('Tolerance settings saved');
      setTimeout(() => setSuccess(null), 3000);
    } catch {
      setError('Failed to save tolerance settings');
    } finally {
      setToleranceSaving(false);
    }
  };

  const updateTolerance = (key: keyof ToleranceConfig, value: number) => {
    setToleranceConfig(prev => ({ ...prev, [key]: value }));
    setToleranceDirty(true);
  };

  // ── Submit transaction ────────────────────────────────────────────────────
  const submitTransaction = async () => {
    if (!auth.token) { setError('Please authenticate first'); return; }
    try {
      setLoading(true); setError(null);
      const res = await axios.post<TransactionResponse>(
        `${API_BASE_URL}/transaction`,
        { amount: transaction.amount, merchant: transaction.merchant, description: transaction.description },
        { headers: { Authorization: `Bearer ${auth.token}` } },
      );
      setResults(prev => [
        { transaction_id: res.data.transaction_id, status: res.data.status, timestamp: new Date().toLocaleString() },
        ...prev,
      ]);
      setSuccess(`Submitted: ${res.data.transaction_id.substring(0, 8)}…`);
      setTransaction({ amount: 100, merchant: 'Starbucks Coffee', description: 'Normal transaction', timestamp: new Date().toLocaleString() });
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit transaction');
    } finally {
      setLoading(false);
    }
  };

  // ── Scenarios ─────────────────────────────────────────────────────────────
  const scenarios = [
    { name: 'Normal',      amount: 75.5,   merchant: 'Starbucks Coffee',              description: 'Regular coffee' },
    { name: 'Suspicious',  amount: 8500,   merchant: 'unknown_offshore_merchant.biz', description: 'Large offshore' },
    { name: 'Grocery',     amount: 120,    merchant: 'Target Retail',                 description: 'Weekly groceries' },
    { name: 'Online',      amount: 299.99, merchant: 'Amazon.com',                    description: 'Online shopping' },
    { name: 'Gas Station', amount: 45.2,   merchant: 'Shell Gas Station',             description: 'Fuel purchase' },
  ];

  // ── Pagination ────────────────────────────────────────────────────────────
  const totalPages      = Math.ceil(results.length / pageSize);
  const paginatedResults = results.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="app">
      <div className="header">
        <h1>🛡️ PayGuard Fraud Detection</h1>
        <p>Real-time transaction fraud analysis · tolerance testing · pipeline observability</p>
      </div>

      <div className="container">

        {/* ── AUTHENTICATION ─────────────────────────────────────────────── */}
        <section className="card auth-card">
          <div className="card-header">
            <Lock size={20} />
            <h2>Authentication</h2>
          </div>
          <div className="auth-content">
            <div className="auth-info">
              <label>User ID</label>
              <input
                type="text"
                value={auth.userId}
                onChange={e => setAuth({ ...auth, userId: e.target.value })}
                disabled={auth.isAuthenticated}
                placeholder="user_id"
              />
            </div>

            {!auth.isAuthenticated && (
              <>
                <div className="auth-method-tabs">
                  {(['pin', 'fingerprint', 'face'] as const).map(m => (
                    <button
                      key={m}
                      className={`auth-tab ${authMethod === m ? 'active' : ''}`}
                      onClick={() => setAuthMethod(m)}
                    >
                      {m === 'pin' ? '🔢 PIN' : m === 'fingerprint' ? '👆 Fingerprint' : '😊 Face ID'}
                    </button>
                  ))}
                </div>

                {authMethod === 'pin' && (
                  <div className="auth-info">
                    <label>Enter PIN (4–6 digits)</label>
                    <input
                      type="password"
                      inputMode="numeric"
                      maxLength={6}
                      value={pin}
                      onChange={e => setPin(e.target.value.replace(/\D/g, ''))}
                      placeholder="••••"
                    />
                  </div>
                )}

                {authMethod === 'fingerprint' && (
                  <div className="biometric-mock">
                    <Fingerprint size={48} style={{ color: '#6366f1' }} />
                    <p>Touch the sensor to authenticate</p>
                    <p className="biometric-hint">(demo: click Authenticate to proceed)</p>
                  </div>
                )}

                {authMethod === 'face' && (
                  <div className="biometric-mock">
                    <span style={{ fontSize: 48 }}>😊</span>
                    <p>Look at the camera to authenticate</p>
                    <p className="biometric-hint">(demo: click Authenticate to proceed)</p>
                  </div>
                )}
              </>
            )}

            {auth.isAuthenticated && (
              <div className="token-display">
                <p>Token: {auth.token?.substring(0, 50)}…</p>
                <p className="status-badge" style={{ color: '#10b981' }}>✓ Authenticated via {authMethod.toUpperCase()}</p>
              </div>
            )}

            {userBalance !== null && (
              <div className="balance-display">
                <span className="balance-label">💳 Available Balance</span>
                <span className="balance-amount">${userBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
              </div>
            )}

            <div className="auth-actions">
              <button onClick={authenticate} disabled={loading || auth.isAuthenticated} className="btn btn-primary">
                {loading ? 'Authenticating…' : auth.isAuthenticated ? '✓ Authenticated' : 'Authenticate'}
              </button>
              {auth.isAuthenticated && (
                <button onClick={logout} className="btn btn-logout">
                  🚪 Log Out
                </button>
              )}
            </div>
          </div>
        </section>

        {/* ── TOLERANCE SETTINGS ─────────────────────────────────────────── */}
        <section className="card tolerance-card">
          <div className="card-header">
            <Sliders size={20} />
            <h2>Tolerance Settings</h2>
            <span className="card-sub">Tune when transactions get escalated or blocked</span>
          </div>

          <div className="tolerance-grid">
            <div className="tolerance-section">
              <h4>🚦 Decision Thresholds</h4>
              <div className="tolerance-hint">
                Lower = stricter (more declines) · Higher = more permissive
              </div>

              {([
                { key: 'layer1_threshold' as const, label: 'Layer 1 escalation threshold', min: 0.1, max: 0.9, step: 0.05,
                  hint: 'Score above this → sent to Layer 2 deep analysis' },
                { key: 'layer2_threshold' as const, label: 'Layer 2 block threshold', min: 0.1, max: 0.99, step: 0.05,
                  hint: 'Layer 2 score above this → transaction blocked' },
                { key: 'anomaly_ratio' as const, label: 'Amount anomaly ratio', min: 1.0, max: 10.0, step: 0.5,
                  hint: 'Purchase exceeds X× avg spending → flagged as anomaly' },
              ]).map(({ key, label, min, max, step, hint }) => (
                <div className="slider-row" key={key}>
                  <div className="slider-label-row">
                    <label>{label}</label>
                    <span className="slider-value">{toleranceConfig[key].toFixed(2)}</span>
                  </div>
                  <input
                    type="range" min={min} max={max} step={step}
                    value={toleranceConfig[key]}
                    onChange={e => updateTolerance(key, parseFloat(e.target.value))}
                    className="tolerance-slider"
                  />
                  <p className="slider-hint">{hint}</p>
                </div>
              ))}
            </div>

            <div className="tolerance-section">
              <h4>⚖️ Component Weights</h4>
              <div className="tolerance-hint">
                How much each factor contributes to the risk assessment
              </div>

              {([
                { key: 'habit_weight'    as const, label: '🛍️ Purchase habit weight',   hint: 'Deviation from user\'s typical spending pattern' },
                { key: 'seasonal_weight' as const, label: '🕐 Time/seasonal weight',    hint: 'Late night, weekends → higher risk' },
                { key: 'merchant_weight' as const, label: '🏪 Merchant risk weight',    hint: 'Unknown or high-risk merchants' },
              ]).map(({ key, label, hint }) => (
                <div className="slider-row" key={key}>
                  <div className="slider-label-row">
                    <label>{label}</label>
                    <span className="slider-value">{pct(toleranceConfig[key])}</span>
                  </div>
                  <input
                    type="range" min={0} max={1} step={0.05}
                    value={toleranceConfig[key]}
                    onChange={e => updateTolerance(key, parseFloat(e.target.value))}
                    className="tolerance-slider"
                  />
                  <p className="slider-hint">{hint}</p>
                </div>
              ))}
            </div>
          </div>

          {toleranceDirty && (
            <button onClick={saveTolerance} disabled={toleranceSaving} className="btn btn-primary" style={{ marginTop: '1rem' }}>
              {toleranceSaving ? 'Saving…' : '💾 Save Tolerance Settings'}
            </button>
          )}
        </section>

        {/* ── TRANSACTION FORM ───────────────────────────────────────────── */}
        <section className="card transaction-card">
          <div className="card-header">
            <Send size={20} />
            <h2>Submit Transaction</h2>
          </div>

          <div className="scenarios">
            <p className="scenarios-label">Quick Scenarios:</p>
            <div className="scenario-buttons">
              {scenarios.map((s, i) => (
                <button key={i} onClick={() => setTransaction({ ...transaction, ...s, timestamp: new Date().toLocaleString() })} className="btn btn-scenario">
                  {s.name}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label>Amount ($)</label>
            <input type="number" step="0.01" value={transaction.amount}
              onChange={e => setTransaction({ ...transaction, amount: parseFloat(e.target.value) })} />
          </div>
          <div className="form-group">
            <label>Merchant</label>
            <input type="text" value={transaction.merchant}
              onChange={e => setTransaction({ ...transaction, merchant: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Description</label>
            <input type="text" value={transaction.description}
              onChange={e => setTransaction({ ...transaction, description: e.target.value })} />
          </div>

          <button onClick={submitTransaction} disabled={loading || !auth.isAuthenticated} className="btn btn-submit">
            {loading ? 'Processing…' : 'Submit Transaction'}
          </button>
        </section>

        {/* ── CONSUMER / PIPELINE PANEL ──────────────────────────────────── */}
        <section className="card consumer-card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {wsConnected
                ? <Wifi size={20} style={{ color: '#10b981' }} />
                : <WifiOff size={20} style={{ color: '#ef4444' }} />}
              <h2>Real-Time Consumer Pipeline</h2>
            </div>
          </div>

          <div className="connection-status">
            <span className={`status-badge ${wsConnected ? 'connected' : 'disconnected'}`}>
              {wsConnected ? '● Connected' : '● Disconnected'}
            </span>
          </div>

          {consumerStatus ? (
            <div className="pipeline-result">

              {/* ── Decision summary ── */}
              <div className={`decision-banner ${consumerStatus.decision === 'blocked' ? 'blocked' : 'approved'}`}>
                <span className="decision-icon">{consumerStatus.decision === 'blocked' ? '✗' : '✓'}</span>
                <div>
                  <div className="decision-label">{consumerStatus.decision.toUpperCase()}</div>
                  {consumerStatus.decision_reason && (
                    <div className="decision-reason">{consumerStatus.decision_reason}</div>
                  )}
                </div>
              </div>

              {/* ── Key metrics row ── */}
              <div className="metrics-row">
                {consumerStatus.amount && (
                  <div className="metric-chip">
                    <span className="metric-label">Amount</span>
                    <span className="metric-value">${consumerStatus.amount.toFixed(2)}</span>
                  </div>
                )}
                {consumerStatus.merchant && (
                  <div className="metric-chip">
                    <span className="metric-label">Merchant</span>
                    <span className="metric-value">{consumerStatus.merchant}</span>
                  </div>
                )}
                <div className="metric-chip">
                  <span className="metric-label">Fraud Score</span>
                  <span className="metric-value" style={{ color: scoreColor(consumerStatus.fraud_score) }}>
                    {pct(consumerStatus.fraud_score)}
                  </span>
                </div>
                <div className="metric-chip">
                  <span className="metric-label">L1 Score</span>
                  <span className="metric-value" style={{ color: scoreColor(consumerStatus.layer1_score) }}>
                    {consumerStatus.layer1_score.toFixed(4)}
                  </span>
                </div>
                {consumerStatus.layer2_score !== undefined && (
                  <div className="metric-chip">
                    <span className="metric-label">L2 Score</span>
                    <span className="metric-value" style={{ color: scoreColor(consumerStatus.layer2_score) }}>
                      {consumerStatus.layer2_score.toFixed(4)}
                    </span>
                  </div>
                )}
                {consumerStatus.user_balance !== undefined && consumerStatus.user_balance !== null && (
                  <div className="metric-chip">
                    <span className="metric-label">Balance</span>
                    <span className="metric-value" style={{ color: '#10b981' }}>
                      ${consumerStatus.user_balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                )}
              </div>

              {/* ── Tolerance components ── */}
              {consumerStatus.tolerance_components && (
                <div className="components-section">
                  <h4><ShieldCheck size={16} style={{ verticalAlign: 'middle' }} /> Tolerance Component Breakdown</h4>
                  {([
                    { key: 'habit_score'    as const, label: '🛍️ Purchase Habit',   desc: 'vs. user avg spending' },
                    { key: 'seasonal_score' as const, label: '🕐 Time / Seasonal',  desc: 'time-of-day & day-of-week risk' },
                    { key: 'merchant_score' as const, label: '🏪 Merchant Risk',    desc: 'merchant category signal' },
                  ]).map(({ key, label, desc }) => {
                    const val = consumerStatus.tolerance_components![key];
                    return (
                      <div className="component-bar-row" key={key}>
                        <div className="component-bar-label">
                          <span>{label}</span>
                          <span className="component-bar-pct" style={{ color: scoreColor(val) }}>{pct(val)}</span>
                        </div>
                        <div className="component-bar-track">
                          <div
                            className="component-bar-fill"
                            style={{ width: pct(val), backgroundColor: scoreColor(val) }}
                          />
                        </div>
                        <p className="component-bar-desc">{desc}</p>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* ── Pipeline steps ── */}
              {consumerStatus.pipeline_steps && consumerStatus.pipeline_steps.length > 0 && (
                <div className="steps-section">
                  <h4><Activity size={16} style={{ verticalAlign: 'middle' }} /> Pipeline Steps</h4>
                  <div className="steps-header-row">
                    <span>Step</span>
                    <span>Start</span>
                    <span>End</span>
                    <span>Duration</span>
                    <span>Status</span>
                  </div>
                  {consumerStatus.pipeline_steps.map(step => (
                    <div className={`step-row ${step.status}`} key={step.step}>
                      <span className="step-name">{step.step}. {step.name}</span>
                      <span>{step.start_ms.toFixed(1)} ms</span>
                      <span>{step.end_ms.toFixed(1)} ms</span>
                      <span className="step-duration">{step.duration_ms.toFixed(2)} ms</span>
                      <span className={`step-status ${step.status}`}>{step.status}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* ── Performance metrics ── */}
              {consumerStatus.performance && (
                <div className="perf-section">
                  <h4><Activity size={16} style={{ verticalAlign: 'middle' }} /> Performance Metrics</h4>
                  <div className="perf-grid">
                    <div className="perf-item">
                      <span className="perf-label">🕐 Query Start</span>
                      <span className="perf-value">{new Date(consumerStatus.timestamp).toISOString().replace('T', ' ').replace('Z', ' UTC')}</span>
                    </div>
                    <div className="perf-item">
                      <span className="perf-label">🕑 Pipeline Total</span>
                      <span className="perf-value">{consumerStatus.performance.pipeline_total_ms.toFixed(1)} ms</span>
                    </div>
                    <div className="perf-item">
                      <span className="perf-label">📡 Kafka Lag</span>
                      <span className="perf-value">{consumerStatus.performance.kafka_latency_ms.toFixed(0)} ms</span>
                    </div>
                    <div className="perf-item">
                      <span className="perf-label">⚙️ CPU (before)</span>
                      <span className="perf-value">{consumerStatus.performance.cpu_before_pct.toFixed(1)} %</span>
                    </div>
                    <div className="perf-item">
                      <span className="perf-label">⚙️ CPU (after)</span>
                      <span className="perf-value">{consumerStatus.performance.cpu_after_pct.toFixed(1)} %</span>
                    </div>
                    <div className="perf-item">
                      <span className="perf-label">🧠 Memory (before)</span>
                      <span className="perf-value">{consumerStatus.performance.memory_before_mb.toFixed(1)} MB</span>
                    </div>
                    <div className="perf-item">
                      <span className="perf-label">🧠 Memory (after)</span>
                      <span className="perf-value">{consumerStatus.performance.memory_after_mb.toFixed(1)} MB</span>
                    </div>
                    <div className="perf-item">
                      <span className="perf-label">🆔 Transaction ID</span>
                      <span className="perf-value mono">{consumerStatus.transaction_id.substring(0, 16)}…</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state">
              <p>Waiting for fraud detection results…</p>
              <p style={{ fontSize: '12px', color: '#6b7280' }}>Submit transactions to see results</p>
            </div>
          )}
        </section>

        {/* ── ALERTS ─────────────────────────────────────────────────────── */}
        {error && (
          <div className="alert alert-error">
            <AlertCircle size={20} /><span>{error}</span>
            <button onClick={() => setError(null)} className="alert-dismiss">✕</button>
          </div>
        )}
        {success && (
          <div className="alert alert-success">
            <CheckCircle size={20} /><span>{success}</span>
          </div>
        )}

        {/* ── RESULTS TABLE ──────────────────────────────────────────────── */}
        {results.length > 0 && (
          <section className="card results-card">
            <div className="card-header">
              <Clock size={20} />
              <h2>Transaction History</h2>
            </div>

            <div className="pagination-controls">
              <div className="pagination-info">
                Showing {paginatedResults.length > 0 ? (currentPage - 1) * pageSize + 1 : 0}–{Math.min(currentPage * pageSize, results.length)} of {results.length}
              </div>
              <div className="pagination-buttons">
                <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} className="btn btn-pagination">
                  <ChevronLeft size={16} /> Prev
                </button>
                <span className="page-indicator">Page {currentPage} / {totalPages || 1}</span>
                <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages} className="btn btn-pagination">
                  Next <ChevronRight size={16} />
                </button>
              </div>
              <div className="page-size-selector">
                <label>Per page:</label>
                <select value={pageSize} onChange={e => { setPageSize(parseInt(e.target.value)); setCurrentPage(1); }} className="select-input">
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
              </div>
            </div>

            <div className="results-list">
              {paginatedResults.map((r, i) => (
                <div key={i} className="result-item">
                  <div className="result-content">
                    <p className="result-id">ID: {r.transaction_id.substring(0, 8)}…</p>
                    <p className="result-status">Status: <span className="status-badge">{r.status}</span></p>
                    <p className="result-time">Submitted: {r.timestamp}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── API INFO ───────────────────────────────────────────────────── */}
        <section className="card info-card">
          <h3>API Information</h3>
          <div className="info-content">
            <p><strong>Base URL:</strong> {API_BASE_URL}</p>
            <p><strong>Status:</strong>{' '}
              {auth.isAuthenticated
                ? <span style={{ color: '#10b981' }}>✓ Authenticated</span>
                : <span style={{ color: '#ef4444' }}>✗ Not connected</span>}
            </p>
            <p><strong>Endpoints:</strong></p>
            <ul>
              <li>POST /token — Generate JWT + initialise balance</li>
              <li>POST /auth/pin — Verify PIN (mock)</li>
              <li>POST /transaction — Submit transaction</li>
              <li>GET  /tolerance — Read tolerance config</li>
              <li>PUT  /tolerance — Update tolerance thresholds</li>
              <li>GET  /health — Health check</li>
            </ul>
          </div>
        </section>

      </div>
    </div>
  );
};

export default App;
