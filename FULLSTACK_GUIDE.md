# PayGuard Full Stack - Docker-Complete Setup

Complete guide for running the entire PayGuard fraud detection system in Docker.

## 🎉 COMPLETE DOCKER SETUP - Everything in Containers!

**NEW**: All services now run in Docker (infrastructure + API + frontend)!

```bash
# Start EVERYTHING with ONE command
docker compose up

# In another terminal, start just the consumer
cd consumer && python pipeline.py

# Open browser: http://localhost:3000
```

✨ **Perfect setup!** All services (Zookeeper, Kafka, Redis, API, Frontend) run in Docker. Only the Consumer (Python) runs on your machine for live development.

For more details: See `DOCKER_QUICK_START.md`

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                 React Frontend (Port 3000)                      │
│                  ✓ Token Generation                             │
│                  ✓ Transaction Submission                       │
│                  ✓ Results Display                              │
│                                                                 │
└────────────────┬─────────────────────────────────────────────────┘
                 │ HTTP/REST API
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│              FastAPI Backend (Port 8000)                        │
│         • Authentication (JWT)                                  │
│         • Transaction Ingestion                                 │
│         • Kafka Producer                                        │
│                                                                 │
└────────────────┬─────────────────────────────────────────────────┘
                 │ Kafka Event Stream
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│         Kafka Consumer Pipeline (6-Step Processing)             │
│         ✓ Feature Extraction (Redis profiling)                  │
│         ✓ Layer 1 - Fast Model Scoring                          │
│         ✓ Layer 2 - Deep Model Scoring (if needed)              │
│         ✓ Decision Engine (Circuit Breaker)                     │
│         ✓ Result Storage (Redis)                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
        │              │              │
        ▼              ▼              ▼
    Kafka         Redis Cache     Zookeeper
   (Port 9092)    (Port 6379)    (Port 2181)
```

## Prerequisites

- **Docker Desktop** - For Kafka, Zookeeper, Redis
- **Python 3.9+** - For API and consumer
- **Node.js 16+** - For React frontend
- **npm** or **yarn** - For package management

## Quick Start (5 Steps)

### Step 1: Start Infrastructure

```bash
# From payguard-poc root directory
docker compose up -d

# Verify services
docker compose ps
```

Expected output:
```
NAME          SERVICE        STATUS
payguard-poc-kafka-1         Up (healthy)
payguard-poc-redis-1         Up (healthy)
payguard-poc-zookeeper-1     Up (healthy)
```

### Step 2: Start API Server

**Terminal 1:**
```bash
cd /Users/pat/Projects/PAT/payguard-poc
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Start Fraud Detection Consumer

**Terminal 2:**
```bash
cd /Users/pat/Projects/PAT/payguard-poc
source venv/bin/activate
cd consumer
python pipeline.py
```

Expected output:
```
[INFO] PayGuard Fraud Detection Consumer - INITIALIZATION
[INFO] Waiting for transactions...
```

### Step 4: Start React Frontend

**Terminal 3:**
```bash
cd /Users/pat/Projects/PAT/payguard-poc/frontend
npm run dev
```

Expected output:
```
VITE v5.4.21  ready in 543 ms

➜  Local:   http://localhost:3000/
➜  press h to show help
```

The frontend opens automatically in your browser.

### Step 5: Test the System

1. **In the React Frontend** (http://localhost:3000):
   - User ID is auto-generated
   - Click "Generate Token"
   - Select a preset scenario or enter custom transaction details
   - Click "Submit Transaction"

2. **Watch Terminal 2** (Consumer):
   - See the complete 6-step fraud detection pipeline
   - Observe feature extraction, model scoring, decision making

3. **Check Results** in the Frontend:
   - Transaction submitted status
   - Transaction ID
   - Submission timestamp

## Detailed Component Startup

### Docker Infrastructure

```bash
docker compose up -d
```

**What starts:**
- **Kafka** (9092) - Message broker
- **Zookeeper** (2181) - Kafka coordinator
- **Redis** (6379) - User profile cache

**Verify:**
```bash
docker compose logs -f kafka    # Watch Kafka logs
redis-cli ping                  # Should return PONG
```

### Python API Server

```bash
cd /Users/pat/Projects/PAT/payguard-poc
python3 -m venv venv            # Create if not exists
source venv/bin/activate
pip install -r requirements.txt # Install if not exists
uvicorn api.main:app --reload --port 8000
```

**Available endpoints:**
- `GET /health` - Health check
- `POST /token` - Generate JWT token
- `POST /transaction` - Submit transaction

**Test API:**
```bash
curl http://localhost:8000/health
```

### Python Consumer

```bash
cd /Users/pat/Projects/PAT/payguard-poc/consumer
python pipeline.py
```

**What it does:**
- Connects to Kafka topic "transactions"
- Runs 6-step fraud detection pipeline
- Stores results in Redis
- Logs detailed execution flow

### React Frontend

```bash
cd /Users/pat/Projects/PAT/payguard-poc/frontend
npm install  # First time only
npm run dev
```

**Features:**
- Responsive web interface
- Real-time transaction submission
- Results history
- Pre-built test scenarios

## Testing the Full Stack

### Scenario 1: Normal Transaction

1. Frontend: Select "Normal Transaction" scenario
2. Click "Submit Transaction"
3. Watch consumer terminal for 6-step pipeline
4. Layer 1 score < 0.4 → Fast approval
5. See result in frontend

### Scenario 2: Suspicious Transaction

1. Frontend: Select "Large Purchase" scenario
2. Click "Submit Transaction"
3. Watch consumer terminal:
   - Layer 1 detects suspicious amount
   - Escalates to Layer 2
   - Shows anomaly (85x normal amount)
   - Layer 2 blocks transaction
4. See result in frontend

### Scenario 3: Custom Transaction

1. Frontend: Manually enter amount, merchant, description
2. Click "Submit Transaction"
3. Watch complete pipeline execution
4. Observe decision making

## API Response Flow

### Frontend → API → Backend

```
1. Frontend generates token
   POST http://localhost:8000/token?user_id=user_123
   Response: {"access_token": "eyJ...", "token_type": "bearer"}

2. Frontend submits transaction
   POST http://localhost:8000/transaction
   Headers: Authorization: Bearer eyJ...
   Body: {"amount": 100, "merchant": "Starbucks", "description": "..."}
   Response: {"status": "accepted", "transaction_id": "abc-123...", "message": "..."}

3. API publishes to Kafka
   Topic: "transactions"

4. Consumer processes (6 steps)
   Step 1: Feature Extraction
   Step 2: Layer 1 Scoring
   Step 3: Behavioral Analysis
   Step 4: Layer 2 Scoring (if needed)
   Step 5: Decision Engine
   Step 6: Result Storage (Redis)

5. Frontend polls/displays results
```

## Monitoring & Debugging

### View API Logs

Terminal 1 shows all API requests and responses.

### View Consumer Logs

Terminal 2 shows detailed pipeline execution:
```
[PIPELINE START] Transaction: abc123...
[STEP 1/6] Feature Extraction & Behavioral Profiling
[REDIS LOOKUP] Found profile for user=user_001...
[FEATURE EXTRACTION] features=[amount, avg_amount, tx_count...]
[STEP 2/6] Layer 1 - Fast Model Scoring
[LAYER 1 SCORING] Fraud probability: 0.0500 → LOW RISK...
[DECISION] ✓ APPROVED
[PROFILE UPDATE] user=user_001 count=1→2...
[RESULT STORAGE] Stored decision in Redis...
[PIPELINE COMPLETE] Transaction abc123... → APPROVED
```

### Check Redis Results

```bash
redis-cli
> KEYS result:*           # See all results
> GET result:<tx_id>      # View specific result
> HGETALL user:user_001:profile  # View user profile
```

### View Frontend Network Requests

1. Open browser DevTools (F12)
2. Go to Network tab
3. Submit a transaction
4. See API calls and responses

## Troubleshooting

### API Connection Error

**Error:** "Failed to generate token. Is the API running?"

**Solution:**
```bash
# Check if API is running
curl http://localhost:8000/health
# Should return: {"status": "healthy", "service": "payguard-api"}

# If not running, start it:
uvicorn api.main:app --reload --port 8000
```

### Consumer Not Processing

**Error:** Consumer shows "Waiting for transactions..." but no messages

**Solution:**
```bash
# Verify Kafka is running
docker compose logs kafka

# Check consumer is connected
# (should show Kafka CONNECT message in logs)

# Send a test transaction from frontend
# (consumer should start processing immediately)
```

### Redis Connection Error

**Error:** "Connection refused" in consumer logs

**Solution:**
```bash
# Start Redis if not running
docker compose restart redis

# Test Redis
redis-cli ping
# Should return: PONG
```

### Port Already in Use

**Error:** "Address already in use"

**Solution:**
```bash
# Kill process using the port
# For port 3000 (frontend):
kill -9 $(lsof -t -i :3000)

# For port 8000 (API):
kill -9 $(lsof -t -i :8000)

# Then restart the service
```

### Frontend Shows CORS Error

**Error:** "Access to XMLHttpRequest has been blocked by CORS policy"

**Solution:**
This is normal in development. The API needs to allow requests from localhost:3000.

In production, configure CORS properly in `api/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "your-production-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Performance Optimization

### Frontend Optimization

```bash
# Production build
npm run build

# Analyze bundle size
npm install -g source-map-explorer
source-map-explorer 'dist/assets/*.js'
```

### API Optimization

Use uvicorn workers in production:
```bash
uvicorn api.main:app --workers 4 --host 0.0.0.0 --port 8000
```

### Consumer Optimization

Increase Kafka batch size in `consumer/pipeline.py`:
```python
# Process multiple messages at once
# Improve throughput with multiple consumer threads
```

## Production Deployment

### Docker Compose Deployment

Full system in Docker:
```bash
docker compose -f docker-compose.prod.yml up -d
```

### Cloud Deployment

**Frontend** → Vercel/Netlify
```bash
cd frontend
npm run build
# Deploy dist/ folder
```

**API** → AWS Lambda / Google Cloud Run / Heroku
```bash
# Containerize API
docker build -f Dockerfile.api -t payguard-api .
```

**Consumer** → Kubernetes / ECS
```bash
docker build -f Dockerfile.consumer -t payguard-consumer .
```

## Stopping the System

### Stop All Services

```bash
# Stop containers
docker compose down

# Stop frontend (Ctrl+C in terminal 3)
# Stop API (Ctrl+C in terminal 1)
# Stop consumer (Ctrl+C in terminal 2)

# Deactivate venv
deactivate
```

### Clean Everything

```bash
# Remove all containers and volumes
docker compose down -v

# Remove frontend node_modules
cd frontend && rm -rf node_modules dist
```

## Next Steps

1. ✅ System is running with full frontend
2. 📊 Test with various scenarios
3. 📝 Review logs to understand pipeline
4. 🔧 Customize scenarios in frontend
5. 🚀 Deploy to production

## Documentation

- **Frontend Details**: `frontend/README.md`
- **API Details**: `README_IMPLEMENTATION.md`
- **System Architecture**: `payguard_fraud_detection_flowchart.svg`
- **Quick Start**: `QUICKSTART.md`

---

**Quick Copy-Paste Commands:**

```bash
# Terminal 1: Start infrastructure
docker compose up -d && docker compose ps

# Terminal 2: Start API
source venv/bin/activate && uvicorn api.main:app --reload

# Terminal 3: Start consumer
cd consumer && python pipeline.py

# Terminal 4: Start frontend
cd frontend && npm run dev
```

**System is running!** Open http://localhost:3000 in your browser.
