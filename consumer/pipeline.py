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
import time
import psutil
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
    1. Feature extraction (with Redis behavioural profiling)
    2. Layer 1 fast model scoring
    3. Behavioural anomaly detection + tolerance components
    4. Layer 2 deep model scoring (if suspicious)
    5. Final decision with circuit breaker
    6. Update user profile & store result

    Timing and CPU/memory metrics are collected for each step.
    """

    pipeline_start   = time.perf_counter()
    cpu_before       = psutil.cpu_percent(interval=None)
    mem_before       = psutil.Process().memory_info().rss / (1024 * 1024)  # MB

    transaction_id   = transaction['transaction_id']
    user_id          = transaction['user_id']
    amount           = transaction['amount']
    merchant         = transaction['merchant']

    # Kafka latency: seconds between transaction creation and now
    kafka_latency_ms = round((time.time() - float(transaction.get('timestamp', time.time()))) * 1000, 2)

    logger.info(f"\n{'='*80}")
    logger.info(f"[PIPELINE START] Transaction: {transaction_id[:8]}...")
    logger.info(f"[TRANSACTION] User: {user_id} | Amount: ${amount:.2f} | Merchant: {merchant}")
    logger.info(f"{'='*80}\n")

    steps = []

    def record_step(step_num, name, start, end, status='completed', skipped=False):
        steps.append({
            'step':        step_num,
            'name':        name,
            'start_ms':    round((start - pipeline_start) * 1000, 2),
            'end_ms':      round((end   - pipeline_start) * 1000, 2),
            'duration_ms': round((end   - start)          * 1000, 2),
            'status':      'skipped' if skipped else status,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: FEATURE EXTRACTION
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("[STEP 1/6] Feature Extraction & Behavioral Profiling")
    logger.info("-" * 80)
    t0 = time.perf_counter()
    features     = components['feature_extractor'].extract_features(transaction)
    user_profile = components['feature_extractor'].get_user_profile(user_id)
    t1 = time.perf_counter()
    record_step(1, "Feature Extraction", t0, t1)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: LAYER 1 FAST MODEL
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n[STEP 2/6] Layer 1 - Fast Model Scoring")
    logger.info("-" * 80)
    t0 = time.perf_counter()
    layer1_score = components['model_scorer'].score_layer1(features)
    t1 = time.perf_counter()
    record_step(2, "Layer 1 Fast Scoring", t0, t1)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: BEHAVIOURAL ANOMALY + TOLERANCE COMPONENTS
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n[STEP 3/6] Behavioral Anomaly & Tolerance Components")
    logger.info("-" * 80)
    t0 = time.perf_counter()
    if user_profile['avg_amount'] > 0:
        ratio = amount / user_profile['avg_amount']
        logger.info(f"[ANOMALY] Amount/Avg Ratio: {ratio:.2f}x")
        if ratio > 3.0:
            logger.warning(f"[ANOMALY] ⚠ Significant deviation detected (>{3.0}x)")

    tolerance_components = components['feature_extractor'].get_tolerance_components(
        transaction, user_profile
    )
    # Fetch (or initialise) user balance
    user_balance = components['feature_extractor'].get_or_init_balance(user_id)
    logger.info(f"[BALANCE] user={user_id} balance=${user_balance:.2f}")
    t1 = time.perf_counter()
    record_step(3, "Anomaly & Tolerance Analysis", t0, t1)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: LAYER 2 DEEP MODEL (if needed)
    # ─────────────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    if layer1_score >= 0.4:
        logger.info("\n[STEP 4/6] Layer 2 - Deep Model Scoring")
        logger.info("-" * 80)
        layer2_score_prefetch = components['model_scorer'].score_layer2(features)
        t1 = time.perf_counter()
        record_step(4, "Layer 2 Deep Scoring", t0, t1)
    else:
        logger.info("\n[STEP 4/6] Layer 2 - Deep Model Scoring")
        logger.info("-" * 80)
        logger.info("[LAYER 2 SCORING] Skipped (Layer 1 score indicates low risk)")
        layer2_score_prefetch = None
        t1 = time.perf_counter()
        record_step(4, "Layer 2 Deep Scoring", t0, t1, skipped=True)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: FINAL DECISION
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n[STEP 5/6] Final Decision Engine")
    logger.info("-" * 80)
    t0 = time.perf_counter()
    decision, decision_reason, layer2_score = components['decision_engine'].make_decision(
        transaction_id=transaction_id,
        layer1_score=layer1_score,
        layer2_scorer=components['model_scorer'] if layer1_score >= 0.4 else None,
        features=features if layer1_score >= 0.4 else None,
        tolerance_components=tolerance_components,
    )
    # Prefer the pre-fetched score (avoids double model call)
    if layer2_score_prefetch is not None and layer2_score is None:
        layer2_score = layer2_score_prefetch
    t1 = time.perf_counter()
    record_step(5, "Decision Engine", t0, t1)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: UPDATE PROFILE & STORE RESULT
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n[STEP 6/6] Profile Update & Result Storage")
    logger.info("-" * 80)
    t0 = time.perf_counter()
    components['feature_extractor'].update_user_profile(transaction)

    # Deduct balance on approved transactions
    if decision == 'approved':
        amount = float(transaction.get('amount', 0))
        user_balance = components['feature_extractor'].deduct_balance(user_id, amount)
        logger.info(f"[BALANCE] Deducted ${amount:.2f} → new balance=${user_balance:.2f}")

    t1 = time.perf_counter()
    record_step(6, "Profile Update & Storage", t0, t1)

    # ─────────────────────────────────────────────────────────────────────────
    # PERFORMANCE SUMMARY
    # ─────────────────────────────────────────────────────────────────────────
    pipeline_end    = time.perf_counter()
    cpu_after       = psutil.cpu_percent(interval=None)
    mem_after       = psutil.Process().memory_info().rss / (1024 * 1024)
    total_ms        = round((pipeline_end - pipeline_start) * 1000, 2)

    performance = {
        'pipeline_total_ms': total_ms,
        'kafka_latency_ms':  kafka_latency_ms,
        'cpu_before_pct':    cpu_before,
        'cpu_after_pct':     cpu_after,
        'memory_before_mb':  round(mem_before, 2),
        'memory_after_mb':   round(mem_after,  2),
    }
    logger.info(
        f"[PERFORMANCE] total={total_ms:.1f}ms  "
        f"kafka_lag={kafka_latency_ms:.0f}ms  "
        f"cpu={cpu_after:.1f}%  mem={mem_after:.1f}MB"
    )

    components['decision_engine'].store_result(
        transaction_id=transaction_id,
        decision=decision,
        layer1_score=layer1_score,
        layer2_score=layer2_score,
        transaction_data=transaction,
        tolerance_components=tolerance_components,
        pipeline_steps=steps,
        performance=performance,
        decision_reason=decision_reason,
        user_balance=user_balance,
    )

    logger.info(f"\n{'='*80}")
    logger.info(f"[PIPELINE COMPLETE] {transaction_id[:8]}... → {decision.upper()}  ({total_ms:.1f}ms)")
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
