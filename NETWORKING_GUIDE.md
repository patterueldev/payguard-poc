# Docker Frontend-to-Backend Networking Guide

## Problem Solved ✅

The React frontend running inside a Docker container needed to connect to the FastAPI backend running on the host machine at `localhost:8000`.

**The Challenge**: Inside a Docker container, `localhost` refers to the container itself, not your host machine.

**The Solution**: Use `host.docker.internal` - Docker Desktop's special DNS name that automatically maps to the host machine.

---

## How It Works

### Network Architecture

```
Your Host Machine                          Docker Container
┌──────────────────────────┐              ┌──────────────────────┐
│                          │              │                      │
│  FastAPI                 │◄─────────────┤  React Frontend      │
│  localhost:8000          │              │  host.docker         │
│                          │              │  .internal:8000      │
│  Consumer                │              │                      │
│  (Kafka listener)        │              └──────────────────────┘
│                          │
└──────────────────────────┘
```

### The Magic

Docker Desktop automatically provides `host.docker.internal` as a DNS entry that resolves to your host machine's `localhost`. This allows containers to reach services running on the host.

---

## Implementation Details

### 1. Frontend Code (App.tsx)

The frontend intelligently selects the API URL based on environment:

```typescript
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'http://host.docker.internal:8000'    // Docker containers
  : 'http://localhost:8000';                 // Local development
```

**Benefits:**
- `npm run dev` (development mode) → uses `localhost:8000` ✓
- Docker (production mode) → uses `host.docker.internal:8000` ✓
- No hardcoding, automatic detection ✓

### 2. Docker Configuration (docker-compose.yml)

Frontend service explicitly sets the environment:

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  environment:
    - NODE_ENV=production          # Triggers production API URL
    - VITE_API_URL=...             # Optional override
```

### 3. Environment Configuration (.env.example)

```bash
# Frontend can optionally override with environment variable
VITE_API_URL=http://host.docker.internal:8000
NODE_ENV=production
```

---

## How to Use

### Standard Setup (3 Terminals)

**Terminal 1:** Start infrastructure + frontend in Docker
```bash
docker compose up
```

Output shows:
```
frontend  | ✓ Ready on http://0.0.0.0:3000
kafka     | [Ready]
redis     | [Ready]
zookeeper | [Ready]
```

**Terminal 2:** Start API on your machine
```bash
source venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

Output shows:
```
Uvicorn running on http://127.0.0.1:8000
```

**Terminal 3:** Start consumer on your machine
```bash
cd consumer && python pipeline.py
```

Output shows:
```
Connected to Kafka broker at kafka:9092
Consumer ready...
```

**Browser:** Open http://localhost:3000

The frontend automatically connects to your API at `http://host.docker.internal:8000` and works seamlessly!

---

## Verification

### Check Frontend Can Reach API

```bash
# From inside the Docker container
docker exec $(docker ps -q -f name=payguard-frontend) \
  wget --spider -q http://host.docker.internal:8000

# Should complete without error (exit code 0)
```

### Manual Test

```bash
# Start API first
uvicorn api.main:app --reload

# Then in another terminal, test the endpoint
curl http://localhost:8000/health
# Should return: {"status": "healthy", ...}
```

### From Frontend

The frontend automatically tests connectivity:

```typescript
const generateToken = async () => {
  try {
    const response = await axios.post(`${API_BASE_URL}/token`, {
      user_id: auth.userId,
    });
    // Connection succeeded!
    setAuth(prev => ({...prev, token: ...}));
  } catch (error) {
    // Connection failed
    setError("Could not connect to API at " + API_BASE_URL);
  }
};
```

---

## Platform Compatibility

| Platform | Support | Notes |
|----------|---------|-------|
| **macOS** | ✅ Full | Docker Desktop includes host.docker.internal |
| **Windows** | ✅ Full | Docker Desktop includes host.docker.internal |
| **Linux** | ⚠️ Manual | May need configuration (see below) |

### Linux-Specific Setup

On Linux, `host.docker.internal` is not automatically available. Options:

**Option 1: Use Docker gateway (Recommended)**
```yaml
frontend:
  environment:
    - VITE_API_URL=http://172.17.0.1:8000  # Default Docker gateway
```

**Option 2: Pass --add-host flag**
```bash
docker compose run --add-host=host.docker.internal:host-gateway frontend
```

**Option 3: Use network_mode: host**
```yaml
frontend:
  network_mode: "host"
  # Then remove ports and depends_on conditions
```

---

## Development Workflow

### Running Frontend Locally (npm dev mode)

If you want to develop the frontend with hot-reloading:

```bash
# Stop the Docker frontend
docker compose stop frontend

# Start the local dev server
cd frontend
npm run dev

# This uses localhost:8000 automatically
```

The dev server will hot-reload as you edit code.

### Running Frontend in Docker (production build)

```bash
docker compose up frontend

# Uses host.docker.internal:8000
# Production-optimized build, no hot-reload
```

---

## Troubleshooting

### "Cannot connect to API" Error

**Check 1:** Is the API running?
```bash
curl http://localhost:8000/health
```

**Check 2:** Is it listening on port 8000?
```bash
lsof -i :8000
# Should show: uvicorn  LISTEN
```

**Check 3:** Is Docker container healthy?
```bash
docker compose ps
# Should show: frontend  Up (healthy)
```

**Check 4:** Test from inside container
```bash
docker exec $(docker ps -q -f name=payguard-frontend) \
  wget --verbose http://host.docker.internal:8000
# Should succeed with 200 status
```

### API is running but frontend still fails

Try these in order:

1. **Rebuild frontend**
   ```bash
   docker compose up --build frontend
   ```

2. **Check logs**
   ```bash
   docker compose logs -f frontend
   # Look for connection errors
   ```

3. **On Linux, use manual gateway**
   ```bash
   # Edit docker-compose.yml
   # Change VITE_API_URL to http://172.17.0.1:8000
   docker compose up --build
   ```

4. **Hardcode the URL (Debug only)**
   ```bash
   # Edit frontend/.env file
   VITE_API_URL=http://host.docker.internal:8000
   docker compose up --build
   ```

---

## Advanced Configuration

### Custom API URL

If you need a different API location:

**Option 1: Environment variable**
```bash
# Create frontend/.env (or .env.local)
VITE_API_URL=http://custom-api.example.com:8000

# Then restart
docker compose up --build frontend
```

**Option 2: Modify docker-compose.yml**
```yaml
frontend:
  environment:
    - VITE_API_URL=http://api.example.com:8000
```

**Option 3: Modify App.tsx** (hardcoding - not recommended)
```typescript
const API_BASE_URL = 'http://your-api:8000';
```

### Multi-Machine Setup

If API is on a different machine:

```yaml
frontend:
  environment:
    - VITE_API_URL=http://192.168.1.100:8000  # Replace with your API machine
```

---

## Technical Background

### Why host.docker.internal Works

Docker Desktop runs a lightweight Linux VM that contains your containers. Docker Desktop includes special DNS resolution:

- **In containers**: `host.docker.internal` → `192.168.65.2` (Docker Desktop VM gateway)
- **In Docker Desktop VM**: `192.168.65.2` → your host machine's `localhost`

This creates a transparent bridge from containers to the host.

### Alternative Approaches (Not Used Here)

1. **Docker network with backend container** - Would require FastAPI in Docker too
2. **Use external network** - More complex setup
3. **Use host network mode** - Breaks container isolation
4. **API in Docker, frontend on host** - Opposite of current setup

The current approach (`host.docker.internal`) is the best balance for development:
- ✅ Frontend uses production Docker build
- ✅ API/Consumer use local development with hot-reloading
- ✅ Easy to iterate and debug
- ✅ No complex networking configuration

---

## Summary

| Aspect | Solution |
|--------|----------|
| **Frontend location** | Docker container (port 3000) |
| **API location** | Your host machine (port 8000) |
| **Connection method** | `host.docker.internal:8000` |
| **Auto-detection** | Yes (based on NODE_ENV) |
| **Configuration needed** | None (automatic!) |
| **Works on macOS/Windows** | Yes ✓ |
| **Works on Linux** | Yes (with one env var) |

---

## Quick Reference

```bash
# Everything you need

# Terminal 1: Start Docker infrastructure + frontend
docker compose up

# Terminal 2: Start API
source venv/bin/activate
uvicorn api.main:app --reload

# Terminal 3: Start consumer
cd consumer && python pipeline.py

# Browser: Open this URL
http://localhost:3000
```

Frontend automatically finds API at `host.docker.internal:8000`.

No additional configuration needed! ✨
