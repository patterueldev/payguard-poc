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

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from kafka import KafkaProducer
import json
import uuid
import time
import logging

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
