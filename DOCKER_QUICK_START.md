# PayGuard Docker-Complete Quick Start

Run the **entire system** (Infrastructure + API + Frontend) with a single Docker command.

## What's Included

```
docker compose up
    ├─ Zookeeper (port 2181)
    ├─ Kafka (port 9092)
    ├─ Redis (port 6379)
    └─ React Frontend (port 3000) ✨ NEW!
```

## Prerequisites

- **Docker Desktop** installed and running
- **Python 3.9+** (for API and consumer - run separately)
- **Terminal** (you'll need 2-3 windows)

## Super Quick Start (3 Steps)

### Step 1: Start Docker Infrastructure + Frontend

```bash
cd /Users/pat/Projects/PAT/payguard-poc
docker compose up
```

**Wait for output:**
```
frontend    | ✓ Ready on http://0.0.0.0:3000
```

This starts:
- ✅ Zookeeper
- ✅ Kafka
- ✅ Redis
- ✅ React Frontend (auto-built and running)

### Step 2: Start API (New Terminal)

```bash
source venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

### Step 3: Start Consumer (New Terminal)

```bash
cd consumer
python pipeline.py
```

## Access the System

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **Kafka**: localhost:9092
- **Redis**: localhost:6379

## Using the Frontend

1. **Frontend loads automatically** at http://localhost:3000
2. Click "Generate Token"
3. Select a scenario or enter custom transaction
4. Click "Submit Transaction"
5. Watch consumer terminal for 6-step pipeline execution

## What's Different?

### Before (Manual Docker)
```bash
docker compose up -d  # Just infra
npm run dev          # Frontend in dev mode
uvicorn ...          # API
cd consumer && python pipeline.py  # Consumer
```

### Now (Complete Docker)
```bash
docker compose up  # Everything (infra + frontend)
uvicorn ...        # API (separate terminal)
python pipeline.py # Consumer (separate terminal)
```

## Docker Compose Features

✅ **Frontend Service**
- Automatically built from `frontend/Dockerfile`
- Optimized production build (63KB gzip)
- Health checks enabled
- Auto-restart on failure
- Runs on port 3000

✅ **Service Dependencies**
- Frontend waits for Kafka and Redis to be healthy
- Proper startup order maintained
- All services on `payguard-network`

✅ **Health Checks**
- Zookeeper: Ready when port 2181 responds
- Kafka: Ready when broker API responds
- Redis: Ready when redis-cli ping succeeds
- Frontend: Ready when HTTP 200 on port 3000

## Commands

```bash
# Start everything
docker compose up

# Start in background
docker compose up -d

# View logs
docker compose logs -f frontend
docker compose logs -f kafka
docker compose logs -f redis

# Stop all services
docker compose down

# Remove volumes (reset Redis)
docker compose down -v

# Rebuild frontend (if you change code)
docker compose up --build frontend

# View service status
docker compose ps
```

## Benefits

✨ **Single Command**: Start infra + frontend with one command
✨ **Faster**: No manual npm dev server startup
✨ **Cleaner**: One window for infra, one for API, one for consumer
✨ **Production-Like**: Frontend runs as optimized production build
✨ **Better Testing**: Test the real build, not dev mode
✨ **Teamwork**: Non-developers just run `docker compose up`

## Development Notes

If you need to develop the frontend:

```bash
# Option 1: Stop Docker frontend, run npm dev locally
docker compose stop frontend
cd frontend && npm run dev

# Option 2: Rebuild Docker image
docker compose up --build frontend
```

## Troubleshooting

### Frontend won't start
```bash
docker compose logs frontend
# Check for build errors
docker compose up --build frontend
```

### Frontend can't connect to API
```bash
# Make sure API is running
curl http://localhost:8000/health
# Should return: {"status": "healthy", ...}
```

### Port 3000 already in use
```bash
# Find and kill process
kill -9 $(lsof -t -i :3000)

# Or use different port in docker-compose.yml
# Change: "3000:3000" to "3001:3000"
```

## Full System Architecture

```
User Browser
    ↓
http://localhost:3000
    ↓
    ┌─ React Frontend ────────────────────┐
    │  (Running in Docker on port 3000)   │
    └─────────────────┬────────────────────┘
                      │ REST API calls
                      ↓
    ┌─ FastAPI Backend ──────────────────┐
    │  (Your Python process on port 8000) │
    └─────────────────┬────────────────────┘
                      │ Kafka messages
                      ↓
    ┌─ Kafka (Docker) ───────────────────┐
    │  Port: 9092                         │
    └─────────┬───────────────────────────┘
              │
    ┌─────────┴──────────┐
    ↓                    ↓
Kafka Topic        Zookeeper
                  (Docker)
    
    Consumer Pipeline (Your Python process)
    ↓
    Redis (Docker - Port 6379)
```

## Next Steps

1. ✅ Run: `docker compose up`
2. ✅ View: http://localhost:3000
3. ✅ API: `uvicorn api.main:app --reload`
4. ✅ Consumer: `cd consumer && python pipeline.py`
5. ✅ Test: Use frontend to submit transactions
6. ✅ Watch: Consumer terminal for pipeline execution

---

**Quick Reference:**

| Command | What it does |
|---------|-------------|
| `docker compose up` | Start all services (infra + frontend) |
| `docker compose up -d` | Start in background |
| `docker compose down` | Stop all services |
| `docker compose logs -f frontend` | Watch frontend logs |
| `docker compose ps` | Show service status |
| `docker compose up --build frontend` | Rebuild frontend |

---

**Support Files:**
- Full guide: `FULLSTACK_GUIDE.md`
- Frontend docs: `frontend/README.md`
- Architecture: `README_IMPLEMENTATION.md`
