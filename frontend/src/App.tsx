import React, { useState } from 'react';
import { AlertCircle, CheckCircle, Clock, Lock, Send } from 'lucide-react';
import axios from 'axios';
import './App.css';

interface AuthState {
  token: string | null;
  userId: string;
  isAuthenticated: boolean;
}

interface TransactionResponse {
  status: string;
  transaction_id: string;
  message: string;
}

interface Transaction {
  amount: number;
  merchant: string;
  description: string;
  timestamp: string;
}

interface Result {
  transaction_id: string;
  status: string;
  timestamp: string;
}

// Use localhost when browser accesses from host machine
const API_BASE_URL = 'http://localhost:8000';

const App: React.FC = () => {
  const [auth, setAuth] = useState<AuthState>({
    token: null,
    userId: 'user_' + Math.random().toString(36).substr(2, 9),
    isAuthenticated: false,
  });

  const [transaction, setTransaction] = useState<Transaction>({
    amount: 100,
    merchant: 'Starbucks Coffee',
    description: 'Normal transaction',
    timestamp: new Date().toLocaleString(),
  });

  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Generate JWT token
  const generateToken = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.post(`${API_BASE_URL}/token`, null, {
        params: { user_id: auth.userId },
      });

      const newToken = response.data.access_token;
      setAuth({
        ...auth,
        token: newToken,
        isAuthenticated: true,
      });
      
      setSuccess(`Token generated for user: ${auth.userId}`);
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Failed to generate token. Is the API running on localhost:8000?');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Submit transaction
  const submitTransaction = async () => {
    if (!auth.token) {
      setError('Please generate a token first');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await axios.post<TransactionResponse>(
        `${API_BASE_URL}/transaction`,
        {
          amount: transaction.amount,
          merchant: transaction.merchant,
          description: transaction.description,
        },
        {
          headers: {
            Authorization: `Bearer ${auth.token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      const result: Result = {
        transaction_id: response.data.transaction_id,
        status: response.data.status,
        timestamp: new Date().toLocaleString(),
      };

      setResults([result, ...results]);
      setSuccess(`Transaction submitted: ${response.data.transaction_id.substring(0, 8)}...`);
      
      // Reset form
      setTransaction({
        amount: 100,
        merchant: 'Starbucks Coffee',
        description: 'Normal transaction',
        timestamp: new Date().toLocaleString(),
      });
      
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to submit transaction';
      setError(errorMsg);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Preset scenarios
  const scenarios = [
    {
      name: 'Normal Transaction',
      amount: 75.5,
      merchant: 'Starbucks Coffee',
      description: 'Regular coffee purchase',
    },
    {
      name: 'Large Purchase',
      amount: 8500,
      merchant: 'unknown_offshore_merchant.biz',
      description: 'Suspicious large transaction',
    },
    {
      name: 'Grocery Shopping',
      amount: 120,
      merchant: 'Target Retail',
      description: 'Weekly grocery shopping',
    },
    {
      name: 'Online Shopping',
      amount: 299.99,
      merchant: 'Amazon.com',
      description: 'Online purchase',
    },
    {
      name: 'Gas Station',
      amount: 45.2,
      merchant: 'Shell Gas Station',
      description: 'Fuel purchase',
    },
  ];

  const loadScenario = (scenario: typeof scenarios[0]) => {
    setTransaction({
      amount: scenario.amount,
      merchant: scenario.merchant,
      description: scenario.description,
      timestamp: new Date().toLocaleString(),
    });
  };

  return (
    <div className="app">
      <div className="header">
        <h1>🛡️ PayGuard Fraud Detection</h1>
        <p>Real-time transaction fraud analysis system</p>
      </div>

      <div className="container">
        {/* Authentication Section */}
        <section className="card auth-card">
          <div className="card-header">
            <Lock size={20} />
            <h2>Authentication</h2>
          </div>
          <div className="auth-content">
            <div className="auth-info">
              <label>User ID:</label>
              <input
                type="text"
                value={auth.userId}
                onChange={(e) => setAuth({ ...auth, userId: e.target.value })}
                placeholder="user_id"
                disabled={auth.isAuthenticated}
              />
            </div>
            {auth.isAuthenticated && (
              <div className="token-display">
                <p>Token: {auth.token?.substring(0, 50)}...</p>
                <p className="status-badge" style={{ color: '#10b981' }}>
                  ✓ Authenticated
                </p>
              </div>
            )}
            <button
              onClick={generateToken}
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? 'Generating...' : 'Generate Token'}
            </button>
          </div>
        </section>

        {/* Transaction Section */}
        <section className="card transaction-card">
          <div className="card-header">
            <Send size={20} />
            <h2>Submit Transaction</h2>
          </div>

          {/* Preset Scenarios */}
          <div className="scenarios">
            <p className="scenarios-label">Quick Scenarios:</p>
            <div className="scenario-buttons">
              {scenarios.map((scenario, idx) => (
                <button
                  key={idx}
                  onClick={() => loadScenario(scenario)}
                  className="btn btn-scenario"
                >
                  {scenario.name}
                </button>
              ))}
            </div>
          </div>

          {/* Transaction Form */}
          <div className="form-group">
            <label>Amount ($)</label>
            <input
              type="number"
              step="0.01"
              value={transaction.amount}
              onChange={(e) =>
                setTransaction({ ...transaction, amount: parseFloat(e.target.value) })
              }
              placeholder="Transaction amount"
            />
          </div>

          <div className="form-group">
            <label>Merchant</label>
            <input
              type="text"
              value={transaction.merchant}
              onChange={(e) =>
                setTransaction({ ...transaction, merchant: e.target.value })
              }
              placeholder="Merchant name"
            />
          </div>

          <div className="form-group">
            <label>Description</label>
            <input
              type="text"
              value={transaction.description}
              onChange={(e) =>
                setTransaction({ ...transaction, description: e.target.value })
              }
              placeholder="Transaction description"
            />
          </div>

          <button
            onClick={submitTransaction}
            disabled={loading || !auth.isAuthenticated}
            className="btn btn-submit"
          >
            {loading ? 'Processing...' : 'Submit Transaction'}
          </button>
        </section>

        {/* Status Messages */}
        {error && (
          <div className="alert alert-error">
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            <CheckCircle size={20} />
            <span>{success}</span>
          </div>
        )}

        {/* Results Section */}
        {results.length > 0 && (
          <section className="card results-card">
            <div className="card-header">
              <Clock size={20} />
              <h2>Transaction Results</h2>
            </div>
            <div className="results-list">
              {results.map((result, idx) => (
                <div key={idx} className="result-item">
                  <div className="result-content">
                    <p className="result-id">
                      ID: {result.transaction_id.substring(0, 8)}...
                    </p>
                    <p className="result-status">
                      Status: <span className="status-badge">{result.status}</span>
                    </p>
                    <p className="result-time">Submitted: {result.timestamp}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* API Info */}
        <section className="card info-card">
          <h3>API Information</h3>
          <div className="info-content">
            <p>
              <strong>Base URL:</strong> {API_BASE_URL}
            </p>
            <p>
              <strong>Status:</strong>{' '}
              {auth.isAuthenticated ? (
                <span style={{ color: '#10b981' }}>✓ Connected</span>
              ) : (
                <span style={{ color: '#ef4444' }}>✗ Not connected</span>
              )}
            </p>
            <p>
              <strong>Endpoints:</strong>
            </p>
            <ul>
              <li>POST /token - Generate JWT token</li>
              <li>POST /transaction - Submit transaction for fraud detection</li>
              <li>GET /health - API health check</li>
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
};

export default App;
