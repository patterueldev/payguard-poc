"""
Decision Engine & Circuit Breaker

Responsibilities:
- Combine model scores into final decision
- Apply circuit breaker pattern for graceful degradation
- Store decision results in Redis

Academic Point:
The circuit breaker is a critical resilience pattern. If the deep analysis (Layer 2)
becomes slow or unavailable, the system can gracefully degrade to using only Layer 1
scores, rather than failing entirely. This ensures uptime even during partial outages.
"""

import redis
import logging
from pybreaker import CircuitBreaker

logger = logging.getLogger(__name__)

class DecisionEngine:
    """Makes final approve/block decisions with resilience patterns"""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        
        # Circuit breaker for Layer 2 calls
        # Fails after 3 consecutive errors, resets after 30 seconds
        self.layer2_breaker = CircuitBreaker(
            fail_max=3,
            reset_timeout=30,
            listeners=[]  # Could add monitoring here
        )
        
        logger.info(
            "[DECISION ENGINE] Initialized with circuit breaker: "
            "fail_max=3, reset_timeout=30s"
        )
    
    def make_decision(self, 
                     transaction_id: str,
                     layer1_score: float,
                     layer2_scorer=None,
                     features=None) -> str:
        """
        Make final decision: "approved" or "blocked"
        
        Logic:
        1. If Layer 1 score < 0.4: Approve immediately (fast path)
        2. If Layer 1 score >= 0.4: Try Layer 2 with circuit breaker
           - If Layer 2 available: Use Layer 2 score (threshold: 0.7)
           - If Layer 2 fails: Fall back to conservative Layer 1 estimate
        """
        
        logger.info(f"\n[DECISION ENGINE] Processing transaction {transaction_id}")
        
        # Fast path: low risk
        if layer1_score < 0.4:
            decision = "approved"
            logger.info(
                f"[DECISION] ✓ APPROVED (Layer 1 score {layer1_score:.4f} < 0.4 threshold)"
            )
            return decision
        
        # Suspicious: try Layer 2
        logger.info(f"[DECISION] Suspicious score from Layer 1 ({layer1_score:.4f})")
        logger.info("[DECISION] Attempting Layer 2 deep analysis...")
        
        if layer2_scorer is None or features is None:
            logger.warning("[DECISION] Layer 2 scorer not provided, using Layer 1 only")
            decision = "approved" if layer1_score < 0.5 else "blocked"
            return decision
        
        # Try Layer 2 with circuit breaker
        try:
            @self.layer2_breaker
            def run_layer2():
                return layer2_scorer.score_layer2(features)
            
            layer2_score = run_layer2()
            
            # Layer 2 threshold
            if layer2_score > 0.7:
                decision = "blocked"
                logger.info(
                    f"[DECISION] ✗ BLOCKED (Layer 2 score {layer2_score:.4f} > 0.7 threshold)"
                )
            else:
                decision = "approved"
                logger.info(
                    f"[DECISION] ✓ APPROVED (Layer 2 score {layer2_score:.4f} <= 0.7 threshold)"
                )
        
        except Exception as e:
            # Circuit breaker is open or Layer 2 failed
            logger.warning(f"[CIRCUIT BREAKER] ⚠ Layer 2 unavailable: {str(e)}")
            logger.warning("[CIRCUIT BREAKER] Falling back to conservative Layer 1 estimate")
            
            # Conservative fallback: if Layer 1 is uncertain, block
            if layer1_score > 0.6:
                decision = "blocked"
                logger.info(
                    f"[DECISION] ✗ BLOCKED (Layer 2 failed, Layer 1 score {layer1_score:.4f} too high)"
                )
            else:
                decision = "approved"
                logger.info(
                    f"[DECISION] ✓ APPROVED (Layer 2 failed, Layer 1 score {layer1_score:.4f} acceptable)"
                )
        
        return decision
    
    def store_result(self, transaction_id: str, decision: str, 
                     layer1_score: float, layer2_score: float = None) -> None:
        """Store decision result in Redis for retrieval"""
        key = f"result:{transaction_id}"
        value = {
            "decision": decision,
            "layer1_score": round(layer1_score, 4),
        }
        if layer2_score is not None:
            value["layer2_score"] = round(layer2_score, 4)
        
        # Store with 1-hour TTL
        self.redis_client.setex(key, 3600, str(value))
        
        logger.info(f"[RESULT STORAGE] Stored decision in Redis: {key} = {decision}")
