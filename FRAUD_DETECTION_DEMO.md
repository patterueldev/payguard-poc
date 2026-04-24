# PayGuard Fraud Detection - Complete Demo Guide

## System Overview

The PayGuard system is a **6-step fraud detection pipeline** that analyzes transactions in real-time:

```
Transaction Submitted → Feature Extraction → ML Layer 1 → ML Layer 2 → Decision Engine → Risk Assessment → Results Stored
```

## Prerequisites

All services must be running:

```bash
docker compose up -d --build
```

Verify with:
```bash
docker compose ps
```

All 5 services should show as "Up":
- zookeeper
- kafka
- redis
- api (fastapi)
- frontend (react)

## How the Demo Works

### 1. User Submits Transaction via Frontend

The React frontend at `http://localhost:3000` collects:
- User ID (auto-generated)
- Token (JWT authentication)
- Transaction details (amount, merchant, description)

### 2. API Validates & Publishes to Kafka

The FastAPI backend:
- Validates JWT token
- Checks transaction format
- Publishes message to Kafka topic: `transactions`
- Returns: `{"status": "accepted", "transaction_id": "..."}`

### 3. Consumer Listens & Processes

The consumer pipeline:
- Subscribes to Kafka `transactions` topic
- Processes each message through 6-step pipeline
- Stores results in Redis

### 4. ML Models Score Fraud Risk

The pipeline runs two layers of ML models:
- **Layer 1**: Initial risk scoring
- **Layer 2**: Refined prediction

Decision outcomes:
- **APPROVED** (score < 0.3) - Legitimate transaction
- **REVIEW** (score 0.3-0.7) - Borderline, needs human review
- **FRAUD_DETECTED** (score > 0.7) - High fraud risk, block

## Complete Demo Walkthrough

### Step 1: Start Services (if not running)

```bash
# Terminal 1: Ensure Docker services are running
cd /Users/pat/Projects/PAT/payguard-poc
docker compose up -d --build
```

### Step 2: Start the Consumer Pipeline

```bash
# Terminal 2: Run the fraud detection consumer
cd /Users/pat/Projects/PAT/payguard-poc
cd consumer
python3 pipeline.py
```

You should see:
```
2026-04-24 21:25:19,338 [INFO] ================================================================================
2026-04-24 21:25:19,338 [INFO] PayGuard Fraud Detection Consumer - INITIALIZATION
2026-04-24 21:25:19,338 [INFO] ================================================================================
2026-04-24 21:25:19,339 [INFO] [FEATURE EXTRACTOR] Initialized, redis=localhost:6379
2026-04-24 21:25:19,400 [INFO] [DECISION ENGINE] Initialized with circuit breaker
2026-04-24 21:25:19,450 [INFO] [CONSUMER] Listening on topic: transactions
```

### Step 3: Open Frontend

```
http://localhost:3000
```

You'll see the PayGuard transaction submission form.

### Step 4: Generate Initial Token

Click **"Generate Token"** button

You should see:
- Green message: "Token generated successfully"
- JWT token displayed (starts with `eyJh...`)
- Token Type: "bearer"

### Step 5: Submit Test Transactions

Submit these transactions in sequence to demonstrate different fraud detection scenarios:

#### Scenario 1: Normal Transaction (LEGITIMATE)

```
Amount: 75.50
Merchant: Starbucks Coffee
Description: Morning coffee purchase
```

**Expected Result:**
```
API Response: 200 OK
{
  "status": "accepted",
  "transaction_id": "txn_abc123",
  "message": "Transaction accepted"
}

Consumer Output:
[INFO] Processing transaction: txn_abc123
[INFO] Amount: $75.50 | Merchant: Starbucks | Features: NORMAL
[INFO] Layer 1 Score: 0.15
[INFO] Layer 2 Score: 0.12
[INFO] Decision: APPROVED (Score: 0.12)
[INFO] Risk Level: LOW
[INFO] Result stored in Redis
```

#### Scenario 2: High-Value Transaction (SUSPICIOUS)

```
Amount: 5000.00
Merchant: Electronics Store
Description: Laptop purchase
```

**Expected Result:**
```
API Response: 200 OK
{
  "status": "accepted",
  "transaction_id": "txn_def456",
  ...
}

Consumer Output:
[INFO] Processing transaction: txn_def456
[INFO] Amount: $5000.00 | Merchant: Electronics | Features: HIGH_AMOUNT
[INFO] Layer 1 Score: 0.68
[INFO] Layer 2 Score: 0.72
[INFO] Decision: FRAUD_DETECTED (Score: 0.72)
[INFO] Risk Level: HIGH
[INFO] Result stored in Redis
[WARNING] Transaction flagged for review
```

#### Scenario 3: Rapid Successive Transactions (VELOCITY FRAUD)

Submit these 3 transactions quickly (within 60 seconds):

```
Transaction 1:
Amount: 200.00
Merchant: Best Buy
Description: Computer monitor

Transaction 2 (10 seconds later):
Amount: 300.00
Merchant: Amazon
Description: Keyboard

Transaction 3 (20 seconds later):
Amount: 250.00
Merchant: Target
Description: Office supplies
```

**Expected Result:**
```
Consumer Output for Transaction 2:
[INFO] Processing transaction: txn_ghi789
[INFO] Features: NORMAL
[INFO] Layer 1 Score: 0.25
[INFO] Layer 2 Score: 0.28
[INFO] Decision: APPROVED

Consumer Output for Transaction 3:
[INFO] Processing transaction: txn_jkl012
[INFO] Features: VELOCITY_FRAUD (3 transactions in 60 seconds)
[INFO] Layer 1 Score: 0.75
[INFO] Layer 2 Score: 0.81
[INFO] Decision: FRAUD_DETECTED
[INFO] Risk Level: HIGH
[INFO] Reason: Unusual transaction velocity
```

#### Scenario 4: Unusual Geographic Pattern (if supported)

```
Amount: 2000.00
Merchant: International Hotel (different country)
Description: Hotel booking
```

**Expected Result:**
```
Consumer Output:
[INFO] Processing transaction: txn_mno345
[INFO] Features: GEOGRAPHIC_ANOMALY
[INFO] Layer 1 Score: 0.65
[INFO] Layer 2 Score: 0.70
[INFO] Decision: FRAUD_DETECTED (borderline)
[INFO] Risk Level: HIGH
```

## Understanding Consumer Output

When the consumer processes a transaction, look for:

### Processing Log Format
```
[TIMESTAMP] [LOG_LEVEL] [COMPONENT] Message
```

### Key Components
- `[FEATURE EXTRACTOR]` - Analyzing transaction features
- `[MODEL SCORER]` - Running ML models
- `[DECISION ENGINE]` - Making fraud/legitimate decision
- `[RESULT STORAGE]` - Saving to Redis

### Risk Scores

The ML models produce a fraud risk score from 0.0 to 1.0:

```
0.0 - 0.3  = APPROVED (Safe transaction)
0.3 - 0.7  = REVIEW (Borderline, needs human review)
0.7 - 1.0  = FRAUD_DETECTED (Block transaction)
```

### What Triggers Fraud Detection

The models detect:

1. **Unusual Amount** - Spike from typical spending
2. **Velocity Fraud** - Too many transactions too quickly
3. **Merchant Category Mismatch** - Wrong type of store for user
4. **Time-Based Anomaly** - Transaction at unusual hour
5. **Geographic Inconsistency** - Impossible travel between locations
6. **Behavioral Change** - Deviation from user's normal patterns

## Checking Results in Redis

Optional: View the results stored in Redis:

```bash
# Terminal 3: Connect to Redis
redis-cli -p 6379

# List all stored transactions
> KEYS *

# View a specific transaction result
> GET transaction:txn_abc123
> GET transaction:txn_def456

# View all keys
> SCAN 0

# Exit
> exit
```

Expected Redis data format:
```json
{
  "transaction_id": "txn_abc123",
  "user_id": "user_xyz",
  "amount": 75.50,
  "merchant": "Starbucks Coffee",
  "fraud_score": 0.12,
  "decision": "APPROVED",
  "risk_level": "LOW",
  "timestamp": "2026-04-24T21:30:00Z",
  "features": {
    "amount_std_dev": 0.8,
    "velocity": 0.1,
    "geographic_score": 0.0
  }
}
```

## Complete Demo Timeline

**Duration: ~10 minutes**

```
0:00 - Start Docker services (docker compose up)
1:00 - Consumer pipeline listening
2:00 - Open http://localhost:3000
2:30 - Generate token
3:00 - Submit normal transaction ($75.50)
3:30 - Consumer processes, shows APPROVED
4:00 - Submit high-value transaction ($5000)
4:30 - Consumer processes, shows FRAUD_DETECTED
5:00 - Submit 3 rapid transactions
6:00 - Consumer detects velocity fraud on 3rd
6:30 - Explain results and scoring
7:00 - Check Redis for stored results
8:00 - Show architecture and data flow
```

## Troubleshooting

### Consumer Won't Start
```bash
# Make sure you're in the right directory
cd /Users/pat/Projects/PAT/payguard-poc
python3 -m pip install --break-system-packages kafka-python
python3 consumer/pipeline.py
```

### API Returns 503 Error
```bash
# Check Kafka is running
docker compose logs kafka | tail -20

# Restart if needed
docker compose restart kafka
```

### No Consumer Output
```bash
# Check consumer logs
docker compose logs api | tail -20

# Verify Kafka is receiving messages
docker compose exec kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic transactions \
  --from-beginning
```

### Frontend Shows CORS Error
Already fixed - but if you see it:
```bash
# Rebuild API with CORS
docker compose up -d --build api
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│ Browser: http://localhost:3000                      │
│ ┌───────────────────────────────────────────────┐   │
│ │ React Frontend                                │   │
│ │ - Generate Token (JWT)                        │   │
│ │ - Submit Transactions                         │   │
│ │ - Display Status (200 OK / 503)               │   │
│ └─────────────┬─────────────────────────────────┘   │
└───────────────┼─────────────────────────────────────┘
                │ HTTP + CORS
                ↓
    ┌─────────────────────────────────────┐
    │ API: http://localhost:8000          │
    │ ┌─────────────────────────────────┐ │
    │ │ FastAPI Backend                 │ │
    │ │ - JWT Validation                │ │
    │ │ - Transaction Validation        │ │
    │ │ - Kafka Publishing              │ │
    │ └──────────┬──────────────────────┘ │
    └───────────┼────────────────────────┘
                │ TCP to kafka:29092
                ↓
    ┌─────────────────────────────────────┐
    │ Kafka: localhost:9092 (external)    │
    │ Internal: kafka:29092               │
    │ Topic: transactions                 │
    └──────────┬────────────────────────┘
               │
      ┌────────┴──────────┬────────────┐
      │                   │            │
      ↓                   ↓            ↓
  ┌─────────┐        ┌────────┐   ┌──────────┐
  │ Consumer│        │ Redis  │   │ Zookeeper│
  │Pipeline │        │ Cache  │   │ Coord    │
  │(6 steps)│        │        │   │          │
  └────┬────┘        └────────┘   └──────────┘
       │
   ML Models
   Decision
   Results
```

## What This Demonstrates

✅ **End-to-End Architecture**
- Frontend to API communication
- CORS cross-origin requests
- Kafka async messaging
- Docker containerization

✅ **Fraud Detection**
- Feature extraction from transactions
- Machine learning model scoring
- Decision engine logic
- Risk assessment

✅ **Real-Time Processing**
- Immediate transaction acceptance
- Async consumer processing
- Live logging of decisions
- Redis result persistence

✅ **Scalability**
- Kafka can handle high throughput
- Consumer can be scaled horizontally
- Stateless API design
- Distributed architecture

## Next Steps

After the demo:
1. Modify transaction amounts to see different fraud scores
2. Submit transactions during "off-hours" to test time-based detection
3. Check Redis for all stored decisions
4. Review consumer logs for detailed scoring
5. Examine the 6-step pipeline in `consumer/pipeline.py`

---

**Ready to demonstrate?** Start with Step 1 above!
