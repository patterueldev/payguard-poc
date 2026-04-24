# PayGuard Quick Start Guide

This guide will get you up and running with the PayGuard fraud detection demo in minutes.

## Prerequisites

- **Docker Desktop** (includes Docker and Docker Compose)
- **Python 3.9 or higher** (`python3 --version`)
- **pip** (usually comes with Python)

## Step 1: Clone and Navigate

```bash
cd /path/to/payguard-poc
```

## Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate              # On Windows: venv\Scripts\activate
```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- fastapi (web framework)
- uvicorn (API server)
- python-jose (JWT authentication)
- kafka-python (message broker client)
- redis (cache client)
- pybreaker (circuit breaker pattern)
- numpy (numerical computing)

## Step 4: Start Infrastructure

In one terminal, run:

```bash
docker compose up -d
```

Verify services are running:

```bash
docker compose ps
```

You should see:
- ✓ zookeeper
- ✓ kafka
- ✓ redis

## Step 5: Open 4 Terminal Windows

### Terminal 1: API Server

```bash
source venv/bin/activate
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2: Fraud Detection Consumer

```bash
source venv/bin/activate
cd consumer
python pipeline.py
```

Expected output:
```
[INFO] PayGuard Fraud Detection Consumer - INITIALIZATION
[INFO] Waiting for transactions...
```

### Terminal 3: Run Demo

```bash
source venv/bin/activate
python producer/simulate.py
```

Watch Terminal 2 to see transactions flowing through the pipeline!

### Terminal 4: Query Results (Optional)

```bash
redis-cli
```

Then:
```
> KEYS result:*          # See all results
> GET result:<tx_id>     # View specific result
> HGETALL user:*         # See user profiles
```

## Understanding Output

Watch Terminal 2 (consumer) to see the pipeline in action:

### Normal Transaction
```
[STEP 1/6] Feature Extraction & Behavioral Profiling
[FEATURE EXTRACTION] features=[75.50, 100.00, 1, 0.5]

[STEP 2/6] Layer 1 - Fast Model Scoring
[LAYER 1 SCORING] Fraud probability: 0.0500 → LOW RISK, fast-track approval

[DECISION] ✓ APPROVED (Layer 1 score 0.0500 < 0.4 threshold)
```

### Suspicious Transaction
```
[STEP 1/6] Feature Extraction & Behavioral Profiling
[FEATURE EXTRACTION] features=[8500.00, 100.00, 2, 0.5]

[STEP 2/6] Layer 1 - Fast Model Scoring
[LAYER 1 SCORING] Fraud probability: 0.9500 → SUSPICIOUS, escalate to Layer 2

[STEP 3/6] Behavioral Anomaly Detection
[ANOMALY] Amount/Avg Ratio: 85.00x
[ANOMALY] ⚠ Significant deviation detected (>3.0x)

[STEP 4/6] Layer 2 - Deep Model Scoring
[LAYER 2 SCORING] Fraud probability: 0.9500 → BLOCK (high confidence in fraud)

[DECISION] ✗ BLOCKED (Layer 2 score 0.9500 > 0.7 threshold)
```

## Key Concepts Demonstrated

### Fast Path (95% of transactions)
- Transaction comes in → Layer 1 quick check → Approve immediately
- Low-risk transactions bypass expensive deep analysis
- Result: Sub-100ms latency

### Suspicious Path (5% of transactions)
- Layer 1 flags as suspicious → Behavioral profiling → Layer 2 deep analysis
- Only worthy transactions pay the cost of intensive processing
- Higher accuracy but slower (200-500ms)

### Circuit Breaker
If Layer 2 becomes unavailable:
- System doesn't crash
- Falls back to conservative estimate using Layer 1
- Message: "Layer 2 unavailable, using conservative fallback"

### Behavioral Profiling
- User spends $100 on average
- Transaction for $8500 is 85x normal amount
- → HIGH RISK → Deep analysis
- Profile updates after each transaction

## Clean Up

When you're done:

```bash
# Stop containers (keep data)
docker compose stop

# Or remove everything
docker compose down

# Deactivate virtual environment
deactivate
```

## Troubleshooting

### Docker issues
```bash
docker compose logs kafka    # Check Kafka logs
docker compose logs redis    # Check Redis logs
```

### API not responding
```bash
curl http://localhost:8000/health    # Should return {"status": "healthy", ...}
```

### Python import errors
```bash
# Make sure venv is activated
which python    # Should point to venv/bin/python
pip list        # Should show fastapi, redis, kafka-python, etc.
```

### Kafka connection issues
```bash
docker compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

### Redis not working
```bash
redis-cli ping    # Should return PONG
```

## Next Steps

Once comfortable with the basic demo:

1. **Read the architecture docs**: See `README_IMPLEMENTATION.md` for deep dive
2. **Modify scenarios**: Edit `producer/simulate.py` to test custom transactions
3. **Adjust thresholds**: Change 0.4/0.7 scores in `consumer/pipeline.py`
4. **Study the patterns**: Each component demonstrates a design pattern

## Quick Reference

| Goal | Command |
|------|---------|
| Start all services | `docker compose up -d` |
| Start API | `uvicorn api.main:app --reload` |
| Start consumer | `cd consumer && python pipeline.py` |
| Send test transactions | `python producer/simulate.py` |
| Check results | `redis-cli` → `KEYS result:*` |
| View logs | `docker compose logs -f kafka` |
| Stop all | `docker compose down` |
| Clean everything | `docker compose down -v` |

---

**Need help?** Check `README_IMPLEMENTATION.md` for architectural details and troubleshooting.
