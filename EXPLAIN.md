# System Architecture Explanation - PayGuard Fraud Detection

## Docker Containers Overview

The PayGuard fraud detection system uses **5 Docker containers** working together on a shared Docker network.

```mermaid
graph TB
    subgraph docker["Docker Network: payguard-network"]
        ZK["🔹 Zookeeper<br/>Port: 2181"]
        KAFKA["🔹 Kafka<br/>Port: 29092/9092"]
        REDIS["🔹 Redis<br/>Port: 6379"]
        API["🔹 API<br/>Port: 8000"]
        FE["🔹 Frontend<br/>Port: 3000"]
    end
    
    ZK -->|coordinates| KAFKA
    KAFKA -->|stores messages| REDIS
    API -->|publishes to| KAFKA
    FE -->|calls| API
    REDIS -->|stores results| REDIS
    
    style docker fill:#f0f0f0
    style ZK fill:#4CAF50
    style KAFKA fill:#2196F3
    style REDIS fill:#FF9800
    style API fill:#9C27B0
    style FE fill:#F44336
```

---

## Container 1: Zookeeper

### Overview
**Coordination Service for Kafka** - Manages Kafka broker state and configuration

### Configuration
```yaml
Image: confluentinc/cp-zookeeper:7.5.0
Port: 2181
Network: payguard-network
Environment:
  ZOOKEEPER_CLIENT_PORT: 2181
  ZOOKEEPER_TICK_TIME: 2000
```

### Purpose in This Project
- **Manages Kafka State**: Tracks broker health, configuration, and metadata
- **Leader Election**: Ensures cluster stability
- **Configuration Storage**: Maintains topic and permission info
- **Broker Discovery**: Keeps track of which brokers are available

### Responsibilities

```mermaid
graph LR
    ZK["Zookeeper<br/>(Port 2181)"]
    
    ZK -->|Monitors| BH["Broker Health"]
    ZK -->|Manages| TC["Topic Config"]
    ZK -->|Tracks| PA["Partition<br/>Assignment"]
    ZK -->|Handles| LE["Leader<br/>Election"]
    
    style ZK fill:#4CAF50
    style BH fill:#E8F5E9
    style TC fill:#E8F5E9
    style PA fill:#E8F5E9
    style LE fill:#E8F5E9
```

### Why It's Needed
- Kafka **requires** Zookeeper to function
- Without Zookeeper, Kafka can't coordinate
- Single instance fine for development
- Production would use Zookeeper cluster for HA

### Startup
- Starts first (no dependencies)
- Other containers wait for it to be ready

---

## Container 2: Kafka

### Overview
**Asynchronous Message Broker** - Queues transactions for processing

### Configuration
```yaml
Image: confluentinc/cp-kafka:7.5.0
Ports:
  - 9092:9092        (external: localhost:9092)
  - 29092 (internal) (inside Docker: kafka:29092)
Network: payguard-network
Broker ID: 1
Topic: transactions (auto-created)
```

### Message Flow Through Kafka

```mermaid
sequenceDiagram
    actor User as User<br/>(Browser)
    participant FE as Frontend<br/>:3000
    participant API as API<br/>:8000
    participant KAFKA as Kafka<br/>:29092
    participant CONSUMER as Consumer<br/>(Your Mac)
    participant REDIS as Redis<br/>:6379

    User->>FE: 1. Submit Transaction
    FE->>API: 2. POST /transaction
    API->>KAFKA: 3. Publish to "transactions"
    API-->>FE: 4. Return 200 OK (immediately)
    FE-->>User: 5. "Transaction accepted!"
    
    CONSUMER->>KAFKA: 6. Subscribe to topic
    KAFKA->>CONSUMER: 7. Deliver message
    CONSUMER->>CONSUMER: 8. ML Processing (6 steps)
    CONSUMER->>REDIS: 9. Store result
    CONSUMER->>CONSUMER: 10. Done
```

### Data Structure in Kafka

```json
Topic: "transactions"
Message: {
  "user_id": "user_123",
  "amount": 75.50,
  "merchant": "Starbucks Coffee",
  "description": "Morning coffee",
  "currency": "USD",
  "timestamp": "2026-04-24T21:30:00Z"
}
```

### Purpose in This Project
- **Decouples API from Consumer**: API doesn't wait for fraud detection
- **Handles High Throughput**: Can queue thousands of transactions
- **Persistence**: Transactions survive crashes
- **Scalability**: Multiple consumers can process same topic

### Listener Configuration

```mermaid
graph TB
    CLIENT1["API Container<br/>(inside Docker)"]
    CLIENT2["Consumer<br/>(on Mac)"]
    KAFKA["Kafka Broker"]
    
    CLIENT1 -->|Uses:<br/>kafka:29092| INTERNAL["PLAINTEXT<br/>Listener:29092"]
    CLIENT2 -->|Uses:<br/>localhost:9092| EXTERNAL["PLAINTEXT_HOST<br/>Listener:9092"]
    
    INTERNAL --> KAFKA
    EXTERNAL --> KAFKA
    
    style KAFKA fill:#2196F3
    style CLIENT1 fill:#9C27B0
    style CLIENT2 fill:#FF9800
    style INTERNAL fill:#81C784
    style EXTERNAL fill:#81C784
```

### Common Issues
- **API error 503**: Kafka not ready when API starts
- **Consumer can't connect**: Using wrong address (kafka:29092 from Mac won't work)
- **Messages not persisting**: Volume issue or broker crash

---

## Container 3: Redis

### Overview
**In-Memory Cache & Result Storage** - Stores transaction fraud detection results

### Configuration
```yaml
Image: redis:7.2-alpine
Port: 6379
Network: payguard-network
Volume: redis_data
Health Check: redis-cli ping
```

### Data Flow to Redis

```mermaid
graph LR
    CONSUMER["Consumer<br/>(Your Mac)"]
    ML["ML Pipeline<br/>(6 Steps)"]
    RESULT["Result:<br/>fraud_score: 0.72<br/>decision: FRAUD_DETECTED"]
    REDIS["Redis<br/>:6379"]
    STORE["Key: transaction:txn_123<br/>Value: JSON Result"]
    
    CONSUMER -->|Process| ML
    ML -->|Generate| RESULT
    RESULT -->|Store in| REDIS
    REDIS -->|Persist| STORE
    
    style CONSUMER fill:#FF9800
    style ML fill:#FF9800
    style RESULT fill:#FFE0B2
    style REDIS fill:#FF9800
    style STORE fill:#FFE0B2
```

### Result Data Structure

```json
Key: transaction:txn_abc123

Value: {
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
    "geographic_score": 0.0,
    "time_of_day": 0.05
  }
}
```

### Use Cases in System

```mermaid
graph TB
    CONSUMER["Consumer Writes"]
    API_READ["API Reads<br/>(optional)"]
    SESSION["Session Cache<br/>(optional)"]
    REDIS["Redis"]
    
    CONSUMER -->|Store Result| REDIS
    API_READ -->|Get Result| REDIS
    SESSION -->|Cache Data| REDIS
    
    style REDIS fill:#FF9800
    style CONSUMER fill:#4CAF50
    style API_READ fill:#2196F3
    style SESSION fill:#9C27B0
```

### Why It's Needed
- **Performance**: Instant result lookups (microseconds vs milliseconds)
- **Scalability**: Multiple API instances can share results
- **TTL Support**: Auto-expire old transactions
- **No Database**: Simpler architecture for POC
- **Pub/Sub**: Can notify about suspicious transactions

### Persistence
- Data persists to `/data` volume
- Survives container restart
- RDB snapshots and AOF (append-only file)

---

## Container 4: API (FastAPI)

### Overview
**Transaction Intake & Validation Engine** - REST API for transaction submission

### Configuration
```yaml
Build:
  context: .
  dockerfile: api/Dockerfile
Base Image: python:3.11-slim
Port: 8000
Network: payguard-network
Framework: FastAPI
Language: Python
```

### Complete Transaction Flow Through API

```mermaid
sequenceDiagram
    actor User
    participant Browser as Browser<br/>localhost:3000
    participant API as API<br/>localhost:8000
    participant JWT as JWT<br/>Engine
    participant KAFKA as Kafka<br/>kafka:29092
    
    User->>Browser: Click "Generate Token"
    Browser->>API: POST /token?user_id=user_123
    API->>JWT: Create JWT (HS256)
    JWT-->>API: eyJh...
    API-->>Browser: {token, type: bearer}
    Browser-->>User: Display Token
    
    User->>Browser: Fill transaction form
    User->>Browser: Click Submit
    Browser->>API: POST /transaction<br/>Header: Authorization: Bearer eyJh...
    API->>JWT: Validate JWT
    JWT-->>API: Valid ✓
    API->>API: Validate schema
    API->>KAFKA: Publish message
    KAFKA-->>API: OK
    API-->>Browser: 200 OK
    API-->>Browser: {status: accepted, txn_id}
    Browser-->>User: "Transaction accepted!"
```

### API Endpoints

```mermaid
graph TB
    FE["Frontend"]
    
    FE -->|POST /token<br/>?user_id=X| TOKEN["🔑 Token Generation<br/>Returns: JWT Token"]
    FE -->|POST /transaction<br/>+ JWT Header| TXN["💳 Transaction Submission<br/>Validates & Publishes to Kafka"]
    FE -->|GET /health| HEALTH["❤️ Health Check<br/>Returns: {status: healthy}"]
    
    style FE fill:#F44336
    style TOKEN fill:#4CAF50
    style TXN fill:#2196F3
    style HEALTH fill:#FF9800
```

### Key Features
- ✅ **JWT Authentication**: HS256 algorithm
- ✅ **CORS Enabled**: Allows http://localhost:3000
- ✅ **Input Validation**: Pydantic models
- ✅ **Async Publishing**: Doesn't wait for consumer
- ✅ **Error Handling**: 503 if Kafka unavailable
- ✅ **Logging**: Structured JSON logs

### Startup Dependencies

```mermaid
graph TD
    DOCKER["docker compose up"]
    DOCKER -->|Wait| KAFKA_HEALTH["Kafka Healthy?"]
    DOCKER -->|Wait| REDIS_HEALTH["Redis Healthy?"]
    KAFKA_HEALTH -->|Yes| API_START["Initialize API"]
    REDIS_HEALTH -->|Yes| API_START
    API_START -->|Create routes| ROUTES["Setup endpoints"]
    ROUTES -->|Setup| CORS["CORS middleware"]
    CORS -->|Start| UVICORN["Uvicorn on :8000"]
    UVICORN -->|Ready| DONE["✓ API Ready"]
    
    style DOCKER fill:#2196F3
    style KAFKA_HEALTH fill:#FF9800
    style REDIS_HEALTH fill:#FF9800
    style API_START fill:#4CAF50
    style DONE fill:#4CAF50
```

---

## Container 5: Frontend (React)

### Overview
**User Interface** - React web application for transaction submission

### Configuration
```yaml
Build:
  context: ./frontend
  dockerfile: Dockerfile
Base: node:18-alpine
Port: 3000
Network: payguard-network
Framework: React 18 + TypeScript
Build Tool: Vite
Server: serve
```

### User Interaction Flow

```mermaid
graph TD
    USER["👤 User<br/>(on Mac)"]
    BROWSER["🌐 Browser<br/>localhost:3000"]
    FE["⚛️ React Frontend<br/>(in Docker)"]
    API["🔌 API<br/>:8000"]
    
    USER -->|Open| BROWSER
    BROWSER -->|Renders| FE
    USER -->|Click Generate| FE
    FE -->|POST /token| API
    API -->|Return JWT| FE
    FE -->|Display Token| USER
    USER -->|Fill Form| FE
    FE -->|POST /transaction| API
    API -->|Return 200| FE
    FE -->|Show Success| USER
    
    style USER fill:#FF5722
    style BROWSER fill:#FFF3E0
    style FE fill:#F44336
    style API fill:#9C27B0
```

### Build Process

```mermaid
graph TB
    DOCKER["docker build"]
    
    DOCKER -->|Stage 1| BUILDER["📦 Builder<br/>node:18-alpine"]
    BUILDER -->|install| DEPS["npm install"]
    DEPS -->|build| BUILD["npm run build"]
    BUILD -->|produces| DIST["dist/<br/>optimized bundle"]
    
    DOCKER -->|Stage 2| RUNTIME["🚀 Runtime<br/>node:18-alpine"]
    RUNTIME -->|install| SERVE["npm install -g serve"]
    SERVE -->|copy| COPY["COPY dist/ from builder"]
    COPY -->|start| START["serve -s dist -l 3000"]
    START -->|port| PORT["0.0.0.0:3000"]
    PORT -->|ready| DONE["✓ Ready"]
    
    DIST -.->|reused in Stage 2| COPY
    
    style DOCKER fill:#2196F3
    style BUILDER fill:#4CAF50
    style RUNTIME fill:#2196F3
    style DONE fill:#4CAF50
```

### Frontend to API Communication

```mermaid
graph LR
    subgraph Frontend["🌐 React Frontend<br/>Browser Context"]
        FORM["Transaction Form"]
        STATE["React State"]
        AXIOS["Axios Client"]
    end
    
    subgraph API["🔌 FastAPI Backend<br/>Docker Container"]
        CORS["CORS Middleware"]
        VALIDATION["Validation"]
        KAFKA["Kafka Publish"]
    end
    
    FORM -->|Fill| STATE
    STATE -->|Submit| AXIOS
    AXIOS -->|POST http://localhost:8000| CORS
    CORS -->|Check origin| CORS
    CORS -->|Allow| VALIDATION
    VALIDATION -->|OK| KAFKA
    KAFKA -->|Publish| KAFKA
    KAFKA -->|Return 200| AXIOS
    AXIOS -->|Show result| FORM
    
    style Frontend fill:#F44336
    style API fill:#9C27B0
    style CORS fill:#4CAF50
    style KAFKA fill:#2196F3
```

---

## Complete Data Flow: End-to-End

### Full Journey of a Transaction

```mermaid
graph LR
    subgraph User["👤 You (Browser)"]
        BUY["Click Generate<br/>Token Button"]
    end
    
    subgraph Frontend_UI["⚛️ Frontend Container<br/>:3000"]
        FORM["Transaction Form"]
        STATE["React State<br/>with JWT"]
    end
    
    subgraph Backend["🔌 API Container<br/>:8000"]
        JWT_CHECK["Validate<br/>JWT"]
        VALIDATE["Validate<br/>Schema"]
    end
    
    subgraph MessageQueue["🔹 Kafka Container<br/>:29092"]
        QUEUE["Queue<br/>Message"]
    end
    
    subgraph Processing["🖥️ Consumer (Your Mac)"]
        EXTRACT["Feature<br/>Extraction"]
        ML1["ML Layer 1<br/>Score"]
        ML2["ML Layer 2<br/>Score"]
        DECISION["Decision<br/>Engine"]
    end
    
    subgraph Cache["🔹 Redis Container<br/>:6379"]
        STORE["Store<br/>Result"]
    end
    
    BUY -->|1. Request| Frontend_UI
    Frontend_UI -->|2. HTTP POST| Backend
    Backend -->|3. Validate| Backend
    Backend -->|4. Publish| MessageQueue
    MessageQueue -->|5. Queue| MessageQueue
    MessageQueue -->|6. Receive| Processing
    Processing -->|7. Process| Processing
    Processing -->|8. Store| Cache
    
    style BUY fill:#FF5722
    style Frontend_UI fill:#F44336
    style Backend fill:#9C27B0
    style MessageQueue fill:#2196F3
    style Processing fill:#FF9800
    style Cache fill:#FF9800
```

### Happy Path: Normal Transaction

```mermaid
sequenceDiagram
    participant Browser
    participant Frontend
    participant API
    participant Kafka
    participant Consumer
    participant Redis

    Browser->>Frontend: 1. User submits transaction
    activate Frontend
    Frontend->>API: 2. POST /transaction (Amount: $75.50)
    activate API
    API->>API: 3. Validate JWT ✓
    API->>API: 4. Validate schema ✓
    API->>Kafka: 5. Publish to "transactions"
    activate Kafka
    API-->>Frontend: 6. Return 200 OK
    deactivate API
    Frontend-->>Browser: 7. Show "Accepted!"
    deactivate Frontend
    
    Kafka->>Consumer: 8. Deliver message
    deactivate Kafka
    activate Consumer
    Consumer->>Consumer: 9. Extract features
    Consumer->>Consumer: 10. Layer 1 score: 0.15
    Consumer->>Consumer: 11. Layer 2 score: 0.12
    Consumer->>Consumer: 12. Decision: APPROVED
    Consumer->>Redis: 13. Store result
    deactivate Consumer
    activate Redis
    Redis->>Redis: 14. Persist to disk
    deactivate Redis
    
    Note over Consumer,Redis: Fraud score < 0.3 = APPROVED ✓
```

### Fraud Path: High-Value Transaction

```mermaid
sequenceDiagram
    participant Browser
    participant Frontend
    participant API
    participant Kafka
    participant Consumer
    participant Redis

    Browser->>Frontend: 1. User submits transaction
    activate Frontend
    Frontend->>API: 2. POST /transaction (Amount: $5000)
    activate API
    API->>API: 3. Validate JWT ✓
    API->>API: 4. Validate schema ✓
    API->>Kafka: 5. Publish to "transactions"
    activate Kafka
    API-->>Frontend: 6. Return 200 OK (always)
    deactivate API
    Frontend-->>Browser: 7. Show "Accepted!"
    deactivate Frontend
    
    Kafka->>Consumer: 8. Deliver message
    deactivate Kafka
    activate Consumer
    Consumer->>Consumer: 9. Extract features
    Note over Consumer: ⚠️ ANOMALY: Amount spike!
    Consumer->>Consumer: 10. Layer 1 score: 0.68
    Consumer->>Consumer: 11. Layer 2 score: 0.72
    Consumer->>Consumer: 12. Decision: FRAUD_DETECTED
    Consumer->>Redis: 13. Store result
    deactivate Consumer
    activate Redis
    Redis->>Redis: 14. Persist to disk
    deactivate Redis
    
    Note over Consumer,Redis: Fraud score > 0.7 = FRAUD_DETECTED 🚨
```

---

## Container Networking

### Docker Network Architecture

```mermaid
graph TB
    subgraph Host["🖥️ Your Mac (Host Machine)"]
        PORT_MAPPING["Port Mapping:<br/>3000→3000<br/>8000→8000<br/>9092→9092<br/>6379→6379<br/>2181→2181"]
    end
    
    subgraph Docker["🐳 Docker Bridge Network<br/>payguard-network"]
        ZK["Zookeeper<br/>:2181"]
        KAFKA["Kafka<br/>:29092 (internal)<br/>:9092 (external)"]
        REDIS["Redis<br/>:6379"]
        API["API<br/>:8000"]
        FE["Frontend<br/>:3000"]
    end
    
    subgraph Consumer["🖥️ Your Mac<br/>Consumer Process"]
        CONS["Consumer<br/>localhost:9092"]
    end
    
    HOST_CONSUMER["Your Mac<br/>Browser"]
    
    HOST_CONSUMER -->|http://localhost:3000| FE
    HOST_CONSUMER -->|http://localhost:8000| API
    CONS -->|localhost:9092| KAFKA
    
    ZK -->|coordinates| KAFKA
    API -->|kafka:29092| KAFKA
    API -->|redis:6379| REDIS
    FE -->|localhost:8000| API
    
    style Docker fill:#E3F2FD
    style Host fill:#F3E5F5
    style Consumer fill:#FFF3E0
    style KAFKA fill:#2196F3
    style API fill:#9C27B0
    style REDIS fill:#FF9800
    style ZK fill:#4CAF50
```

### Service Name Resolution

```mermaid
graph LR
    API_CODE["API Code:<br/>kafka:29092"]
    DNS["Docker DNS<br/>Resolver"]
    KAFKA_IP["Kafka Container IP<br/>172.19.0.3"]
    KAFKA["Kafka<br/>Listening on<br/>:29092"]
    
    API_CODE -->|Lookup| DNS
    DNS -->|Resolve| KAFKA_IP
    KAFKA_IP -->|Connect to| KAFKA
    KAFKA -->|Accept| KAFKA
    
    style API_CODE fill:#9C27B0
    style DNS fill:#4CAF50
    style KAFKA_IP fill:#2196F3
    style KAFKA fill:#2196F3
```

---

## Startup Sequence

```mermaid
graph TD
    START["docker compose up -d --build"]
    
    START -->|1. No deps| ZK["Zookeeper Starts"]
    ZK -->|Ready| ZK_OK["✓ Zookeeper Ready<br/>:2181"]
    
    ZK_OK -->|2. Waits for| KAFKA["Kafka Starts"]
    KAFKA -->|Health check| KAFKA_HC["Kafka API Version OK?"]
    KAFKA_HC -->|Yes| KAFKA_OK["✓ Kafka Ready<br/>:29092"]
    
    KAFKA_OK -->|3. No deps| REDIS["Redis Starts"]
    REDIS -->|Health check| REDIS_HC["redis-cli ping?"]
    REDIS_HC -->|PONG| REDIS_OK["✓ Redis Ready<br/>:6379"]
    
    KAFKA_OK -->|4. Waits for| API["API Starts"]
    REDIS_OK -->|4. Waits for| API
    API -->|Initialize| API_INIT["Setup FastAPI"]
    API_INIT -->|Routes| API_READY["✓ API Ready<br/>:8000"]
    
    API_READY -->|5. Waits for| FE["Frontend Starts"]
    KAFKA_OK -->|5. Waits for| FE
    REDIS_OK -->|5. Waits for| FE
    FE -->|Build dist| FE_BUILD["npm run build"]
    FE_BUILD -->|Serve| FE_READY["✓ Frontend Ready<br/>:3000"]
    
    FE_READY -->|All Ready| DONE["🎉 System Ready!"]
    
    style START fill:#2196F3
    style DONE fill:#4CAF50
    style ZK_OK fill:#81C784
    style KAFKA_OK fill:#81C784
    style REDIS_OK fill:#81C784
    style API_READY fill:#81C784
    style FE_READY fill:#81C784
```

---

## Communication Paths

### Valid Connections

```mermaid
graph TB
    subgraph INSIDE["Inside Docker Network"]
        API["API Container"]
        KAFKA["Kafka Container"]
        REDIS["Redis Container"]
    end
    
    subgraph OUTSIDE["Outside Docker Network"]
        MAC["Your Mac"]
        BROWSER["Browser"]
        CONSUMER["Consumer Process"]
    end
    
    API -->|✅ kafka:29092| KAFKA
    API -->|✅ redis:6379| REDIS
    BROWSER -->|✅ localhost:8000| API
    BROWSER -->|✅ localhost:3000| API
    CONSUMER -->|✅ localhost:9092| KAFKA
    
    API -.->|❌ localhost:9092| KAFKA
    MAC -.->|❌ kafka:29092| KAFKA
    
    style INSIDE fill:#E8F5E9
    style OUTSIDE fill:#FFF3E0
    style KAFKA fill:#2196F3
    style API fill:#9C27B0
    style REDIS fill:#FF9800
```

---

## Resource Usage & Performance

### Container Resource Estimates

```mermaid
graph TB
    TOTAL["Total System<br/>~1.5 GB RAM"]
    
    TOTAL --> ZK["Zookeeper<br/>100-200 MB"]
    TOTAL --> KAFKA["Kafka<br/>500-800 MB"]
    TOTAL --> REDIS["Redis<br/>50-100 MB"]
    TOTAL --> API["API<br/>200-300 MB"]
    TOTAL --> FE["Frontend<br/>50-100 MB"]
    
    style TOTAL fill:#FF6F00
    style ZK fill:#4CAF50
    style KAFKA fill:#2196F3
    style REDIS fill:#FF9800
    style API fill:#9C27B0
    style FE fill:#F44336
```

### Typical Latency

```mermaid
graph LR
    USER["User<br/>Action"]
    API_CALL["API Call<br/>&lt;10ms"]
    KAFKA["Kafka<br/>Publish<br/>&lt;50ms"]
    CONSUMER["Consumer<br/>Receive<br/>&lt;100ms"]
    ML["ML<br/>Processing<br/>200-500ms"]
    REDIS["Redis<br/>Store<br/>&lt;10ms"]
    
    USER -->|⏱️| API_CALL
    API_CALL -->|⏱️| KAFKA
    KAFKA -->|⏱️| CONSUMER
    CONSUMER -->|⏱️| ML
    ML -->|⏱️| REDIS
    
    style USER fill:#FF5722
    style API_CALL fill:#4CAF50
    style KAFKA fill:#2196F3
    style CONSUMER fill:#FF9800
    style ML fill:#FF9800
    style REDIS fill:#FF9800
```

---

## Summary Table

| Container | Image | Port | Purpose | Depends On | Status |
|-----------|-------|------|---------|-----------|--------|
| **Zookeeper** | confluentinc/cp-zookeeper | 2181 | Kafka coordination | None | Always up |
| **Kafka** | confluentinc/cp-kafka | 29092/9092 | Message broker | Zookeeper ✓ | Healthy |
| **Redis** | redis:alpine | 6379 | Result caching | None | Healthy |
| **API** | python:3.11-slim | 8000 | Transaction intake | Kafka, Redis ✓ | Running |
| **Frontend** | node:18-alpine | 3000 | User interface | API ✓ | Healthy |

---

## Key Concepts

### Asynchronous Processing
The API returns immediately (200 OK) without waiting for fraud detection results. Consumer processes transactions asynchronously from Kafka queue.

### Service Discovery
Docker's embedded DNS server resolves service names (kafka, redis, etc.) to container IPs on the payguard-network.

### Port Mapping
Exposes container ports to host machine:
- Internal communication: Container name + internal port (kafka:29092)
- External access: localhost + exposed port (localhost:9092)

### Health Checks
Each container declares how to verify it's healthy. Other containers wait for dependencies to be healthy before starting.

### Data Persistence
Redis volume ensures results survive container restarts. Kafka and Zookeeper also persist their data.

---

This architecture enables:
✅ **Scalability** - Add more consumers for parallel processing
✅ **Reliability** - Kafka persists messages
✅ **Performance** - Async processing doesn't block frontend
✅ **Testability** - Each component can be tested independently
✅ **Maintainability** - Clear separation of concerns
