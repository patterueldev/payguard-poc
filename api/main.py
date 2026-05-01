"""
PayGuard Transaction Ingestion API

Responsibilities:
- Authenticate incoming requests using JWT
- Validate transaction data structure
- Publish transactions to Kafka asynchronously
- Return immediately without waiting for fraud analysis (demonstrates decoupling)

Academic Point:
The API does not process transactions directly. It simply validates identity and
hands off responsibility to the message queue. This separation of concerns is
fundamental to scalable microservices architecture.
"""

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from kafka import KafkaProducer
import json
import uuid
import time
import logging
import redis
import threading
import asyncio
from queue import Queue

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Secret key for JWT signing (for demo purposes only)
SECRET_KEY = "payguard-demo-secret-key-change-in-production"
ALGORITHM = "HS256"

# Kafka bootstrap server (use 'kafka:29092' for Docker internal, localhost:9092 for host access)
KAFKA_BROKER = "kafka:29092"
KAFKA_TOPIC = "transactions"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════════

class TransactionRequest(BaseModel):
    """Request body for transaction submission"""
    amount: float
    merchant: str
    description: str = ""

class TransactionResponse(BaseModel):
    """Response after transaction is accepted"""
    status: str
    transaction_id: str
    message: str

# ══════════════════════════════════════════════════════════════════════════════
# KAFKA PRODUCER
# ══════════════════════════════════════════════════════════════════════════════

kafka_producer = None

def get_kafka_producer():
    """Lazy initialization of Kafka producer with retry logic"""
    global kafka_producer
    if kafka_producer is None:
        try:
            kafka_producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3,
                request_timeout_ms=10000,
                api_version=(2, 5, 0)  # Specify Kafka API version
            )
            logger.info(f"[KAFKA PRODUCER] Initialized, broker={KAFKA_BROKER}, topic={KAFKA_TOPIC}")
        except Exception as e:
            logger.warning(f"[KAFKA PRODUCER] Delayed initialization (will retry on first request): {e}")
            kafka_producer = None
            raise
    return kafka_producer

# ══════════════════════════════════════════════════════════════════════════════
# REDIS & WEBSOCKET PUBSUB
# ══════════════════════════════════════════════════════════════════════════════

redis_client = None
message_queue = Queue()  # Thread-safe queue for passing messages
connected_clients = []  # List of asyncio queues
pubsub_thread = None

def get_redis_client():
    """Get or create Redis client"""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.Redis(
                host="redis",
                port=6379,
                decode_responses=True
            )
            redis_client.ping()
            logger.info("[REDIS] Connected to Redis")
        except Exception as e:
            logger.warning(f"[REDIS] Connection failed: {e}")
            redis_client = None
            raise
    return redis_client

def start_pubsub_listener():
    """Start background thread to listen for fraud results on Redis pub/sub"""
    global pubsub_thread
    
    def listen_and_queue():
        try:
            redis_conn = get_redis_client()
            pubsub = redis_conn.pubsub()
            pubsub.subscribe("fraud_results")
            logger.info("[PUBSUB] Listening to 'fraud_results' channel")
            
            for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        logger.info(f"[PUBSUB] Received: {data.get('transaction_id', 'unknown')[:8]}...")
                        # Store latest result in Redis (for late connections to fetch)
                        redis_conn.setex("latest_fraud_result", 3600, json.dumps(data))
                        # Queue message for real-time delivery to connected clients
                        message_queue.put(data)
                        logger.info(f"[PUBSUB] Queued for {len(connected_clients)} WebSocket clients")
                    except Exception as e:
                        logger.error(f"[PUBSUB] Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"[PUBSUB] Listener error: {e}")
    
    pubsub_thread = threading.Thread(target=listen_and_queue, daemon=True)
    pubsub_thread.start()

# ══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════

security = HTTPBearer()

def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify JWT token and extract user information.
    
    Academic Point: In a real system, this would validate against a user database
    and use proper token refresh mechanisms. For demo, we accept any valid JWT.
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        if user_id is None:
            logger.warning("[JWT AUTH] Token missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )
        
        logger.info(f"[JWT AUTH] ✓ Token verified for user={user_id}")
        return {"user_id": user_id}
    
    except JWTError as e:
        logger.warning(f"[JWT AUTH] ✗ Token validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

# ══════════════════════════════════════════════════════════════════════════════
# API APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="PayGuard Fraud Detection API",
    description="Transaction ingestion layer for fraud detection pipeline",
    version="1.0.0"
)

# Add CORS middleware to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "payguard-api"}

@app.post("/transaction", response_model=TransactionResponse)
async def submit_transaction(
    request: TransactionRequest,
    user: dict = Depends(verify_jwt)
) -> TransactionResponse:
    """
    Accept a transaction and publish it to Kafka for async processing.
    
    Returns immediately without waiting for fraud analysis.
    This is a key architectural pattern: decoupling ingestion from processing.
    """
    
    user_id = user["user_id"]
    transaction_id = str(uuid.uuid4())
    timestamp = time.time()
    
    # Build transaction event
    event = {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "amount": request.amount,
        "merchant": request.merchant,
        "description": request.description,
        "timestamp": timestamp
    }
    
    logger.info(
        f"[TRANSACTION INTAKE] Received from {user_id}: "
        f"${request.amount:.2f} at {request.merchant}"
    )
    
    # Publish to Kafka
    try:
        producer = get_kafka_producer()
        future = producer.send(KAFKA_TOPIC, event)
        future.get(timeout=10)  # Wait for confirmation
        
        logger.info(
            f"[KAFKA PUBLISH] ✓ Transaction {transaction_id} "
            f"published to topic '{KAFKA_TOPIC}'"
        )
        
        return TransactionResponse(
            status="accepted",
            transaction_id=transaction_id,
            message="Transaction accepted. Fraud analysis in progress."
        )
    
    except Exception as e:
        logger.error(f"[KAFKA PUBLISH] ✗ Failed to publish: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Message broker unavailable. Please try again."
        )

@app.post("/token")
async def get_demo_token(user_id: str):
    """
    Generate a demo JWT token for testing.
    
    In production, this would validate credentials against a user database.
    For demo purposes, accept any user_id.
    """
    token = jwt.encode({"sub": user_id}, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"[JWT GENERATION] Generated token for user={user_id}")
    return {"access_token": token, "token_type": "bearer"}

@app.websocket("/ws/fraud-results")
async def websocket_fraud_results(websocket: WebSocket):
    """
    WebSocket endpoint for real-time fraud detection results.
    
    Clients connect and receive live updates when fraud detection completes.
    Results are streamed from Redis pub/sub channel via background listener.
    """
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"[WEBSOCKET] Client connected. Total clients: {len(connected_clients)}")
    
    try:
        # Send latest result if available (for late connections)
        try:
            latest = redis_client.get("latest_fraud_result")
            if latest:
                data = json.loads(latest)
                logger.info(f"[WEBSOCKET] Sending latest result to new client")
                await websocket.send_json(data)
        except Exception as e:
            logger.debug(f"[WEBSOCKET] No latest result available: {e}")
        
        # Now listen for new results
        while True:
            try:
                msg = message_queue.get_nowait()
                logger.info(f"[WEBSOCKET] Sending fraud result to client: {msg.get('transaction_id', 'unknown')}")
                await websocket.send_json(msg)
                logger.info(f"[WEBSOCKET] ✓ Message sent successfully")
            except Exception as e:
                if e.__class__.__name__ == 'Empty':
                    # Queue empty, sleep briefly before checking again
                    await asyncio.sleep(0.2)
                else:
                    # Real error - log it but continue
                    logger.error(f"[WEBSOCKET] Error sending message: {type(e).__name__}: {e}")
                    await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        try:
            connected_clients.remove(websocket)
        except:
            pass
        logger.info(f"[WEBSOCKET] Client disconnected. Total clients: {len(connected_clients)}")
    except Exception as e:
        logger.error(f"[WEBSOCKET] Error: {type(e).__name__}: {e}")
        try:
            connected_clients.remove(websocket)
        except:
            pass

# ══════════════════════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    logger.info("="*80)
    logger.info("PayGuard Transaction Ingestion API - STARTUP")
    logger.info("="*80)
    logger.info(f"Kafka Broker: {KAFKA_BROKER}")
    logger.info(f"Topic: {KAFKA_TOPIC}")
    logger.info("Listening for authenticated transaction requests...")
    logger.info("="*80)
    
    # Start Redis pub/sub listener for WebSocket broadcasts
    try:
        get_redis_client()
        start_pubsub_listener()
    except Exception as e:
        logger.warning(f"[STARTUP] Redis pub/sub not available: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down API...")
    if kafka_producer is not None:
        kafka_producer.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
