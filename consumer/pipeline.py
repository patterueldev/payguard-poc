"""
Kafka Consumer Pipeline Orchestrator

Responsibilities:
- Connect to Kafka and consume transactions
- Orchestrate the entire fraud detection pipeline
- Coordinate all steps: feature extraction → scoring → decision → storage

Academic Point:
This is where the architecture comes alive. By clearly separating concerns
(features, models, decisions), the code becomes testable and maintainable.
Each step is independently verifiable, making it suitable for academic demonstration.
"""

import json
import logging
import os
from kafka import KafkaConsumer
from kafka.errors import KafkaError

from features import FeatureExtractor
from models import ModelScorer
from decision import DecisionEngine

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "transactions"
KAFKA_GROUP = "fraud-detection-consumer-group"

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# ML Models configuration
ML_MODELS_DIR = os.getenv("ML_MODELS_DIR", "models")
LAYER1_PATH = os.path.join(ML_MODELS_DIR, "layer1.pkl")
LAYER2_PATH = os.path.join(ML_MODELS_DIR, "layer2.pkl")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE INITIALIZATION
# ══════════════════════════════════════════════════════════════════════════════

def initialize_pipeline():
    """Initialize all components of the fraud detection pipeline"""
    
    logger.info("="*80)
    logger.info("PayGuard Fraud Detection Consumer - INITIALIZATION")
    logger.info("="*80)
    
    # Feature extraction
    feature_extractor = FeatureExtractor(
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT
    )
    
    # Model scoring
    model_scorer = ModelScorer(
        layer1_path=LAYER1_PATH,
        layer2_path=LAYER2_PATH
    )
    
    # Decision engine with circuit breaker
    decision_engine = DecisionEngine(
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT
    )
    
    # Kafka consumer
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id=KAFKA_GROUP,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True
    )
    
    logger.info(f"[KAFKA CONSUMER] Connected to {KAFKA_BROKER}")
    logger.info(f"[KAFKA CONSUMER] Subscribed to topic '{KAFKA_TOPIC}'")
    logger.info(f"[KAFKA CONSUMER] Consumer group: {KAFKA_GROUP}")
    logger.info("="*80)
    logger.info("Waiting for transactions...\n")
    
    return {
        'consumer': consumer,
        'feature_extractor': feature_extractor,
        'model_scorer': model_scorer,
        'decision_engine': decision_engine
    }

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

def process_transaction(transaction, components):
    """
    Execute the complete fraud detection pipeline for one transaction.
    
    Steps:
    1. Feature extraction (with Redis behavioral profiling)
    2. Layer 1 fast model scoring
    3. Behavioral anomaly detection
    4. Layer 2 deep model scoring (if suspicious)
    5. Final decision with circuit breaker
    6. Update user profile
    7. Store result
    """
    
    transaction_id = transaction['transaction_id']
    user_id = transaction['user_id']
    amount = transaction['amount']
    merchant = transaction['merchant']
    
    logger.info(f"\n{'='*80}")
    logger.info(f"[PIPELINE START] Transaction: {transaction_id[:8]}...")
    logger.info(f"[TRANSACTION] User: {user_id} | Amount: ${amount:.2f} | Merchant: {merchant}")
    logger.info(f"{'='*80}\n")
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: FEATURE EXTRACTION
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("[STEP 1/6] Feature Extraction & Behavioral Profiling")
    logger.info("-" * 80)
    
    features = components['feature_extractor'].extract_features(transaction)
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: LAYER 1 FAST MODEL
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n[STEP 2/6] Layer 1 - Fast Model Scoring")
    logger.info("-" * 80)
    
    layer1_score = components['model_scorer'].score_layer1(features)
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: BEHAVIORAL ANOMALY DETECTION
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n[STEP 3/6] Behavioral Anomaly Detection")
    logger.info("-" * 80)
    
    user_profile = components['feature_extractor'].get_user_profile(user_id)
    if user_profile['avg_amount'] > 0:
        ratio = amount / user_profile['avg_amount']
        logger.info(f"[ANOMALY] Amount/Avg Ratio: {ratio:.2f}x")
        if ratio > 3.0:
            logger.warning(f"[ANOMALY] ⚠ Significant deviation detected (>{3.0}x)")
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: LAYER 2 DEEP MODEL (if needed)
    # ─────────────────────────────────────────────────────────────────────────
    layer2_score = None
    if layer1_score >= 0.4:
        logger.info("\n[STEP 4/6] Layer 2 - Deep Model Scoring")
        logger.info("-" * 80)
        
        layer2_score = components['model_scorer'].score_layer2(features)
    else:
        logger.info("\n[STEP 4/6] Layer 2 - Deep Model Scoring")
        logger.info("-" * 80)
        logger.info("[LAYER 2 SCORING] Skipped (Layer 1 score indicates low risk)")
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: FINAL DECISION
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n[STEP 5/6] Final Decision Engine")
    logger.info("-" * 80)
    
    decision = components['decision_engine'].make_decision(
        transaction_id=transaction_id,
        layer1_score=layer1_score,
        layer2_scorer=components['model_scorer'] if layer1_score >= 0.4 else None,
        features=features if layer1_score >= 0.4 else None
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: UPDATE PROFILE & STORE RESULT
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n[STEP 6/6] Profile Update & Result Storage")
    logger.info("-" * 80)
    
    components['feature_extractor'].update_user_profile(transaction)
    components['decision_engine'].store_result(
        transaction_id=transaction_id,
        decision=decision,
        layer1_score=layer1_score,
        layer2_score=layer2_score
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # PIPELINE COMPLETE
    # ─────────────────────────────────────────────────────────────────────────
    logger.info(f"\n{'='*80}")
    logger.info(f"[PIPELINE COMPLETE] Transaction {transaction_id[:8]}... → {decision.upper()}")
    logger.info(f"{'='*80}\n")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

def run_consumer():
    """Main loop: consume and process transactions from Kafka"""
    
    components = initialize_pipeline()
    
    try:
        logger.info("Consumer ready. Processing messages...\n")
        
        for message in components['consumer']:
            if message.value is None:
                continue
            
            transaction = message.value
            
            try:
                process_transaction(transaction, components)
            
            except Exception as e:
                logger.error(f"[ERROR] Failed to process transaction: {str(e)}", exc_info=True)
    
    except KeyboardInterrupt:
        logger.info("\nShutting down consumer...")
    finally:
        components['consumer'].close()
        logger.info("Consumer closed.")

if __name__ == "__main__":
    run_consumer()
