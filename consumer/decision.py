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
import os
from typing import Dict, Optional
from pybreaker import CircuitBreaker

logger = logging.getLogger(__name__)

class DecisionEngine:
    """Makes final approve/block decisions with resilience patterns"""
    
    def __init__(self, redis_host: str = None, redis_port: int = None):
        # Support environment variables for Docker deployments
        if redis_host is None:
            redis_host = os.getenv("REDIS_HOST", "localhost")
        if redis_port is None:
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
        
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

    def get_tolerance_config(self) -> Dict:
        """Read configurable thresholds from Redis (falls back to safe defaults)."""
        try:
            cfg = self.redis_client.hgetall("config:tolerance")
            if cfg:
                return {
                    'layer1_threshold': float(cfg.get('layer1_threshold', 0.4)),
                    'layer2_threshold': float(cfg.get('layer2_threshold', 0.7)),
                    'anomaly_ratio':    float(cfg.get('anomaly_ratio',    3.0)),
                    'habit_weight':     float(cfg.get('habit_weight',     0.4)),
                    'seasonal_weight':  float(cfg.get('seasonal_weight',  0.2)),
                    'merchant_weight':  float(cfg.get('merchant_weight',  0.4)),
                }
        except Exception as exc:
            logger.warning(f"[TOLERANCE CONFIG] Redis read failed, using defaults: {exc}")
        return {
            'layer1_threshold': 0.4,
            'layer2_threshold': 0.7,
            'anomaly_ratio':    3.0,
            'habit_weight':     0.4,
            'seasonal_weight':  0.2,
            'merchant_weight':  0.4,
        }
    
    def make_decision(self,
                     transaction_id: str,
                     layer1_score: float,
                     layer2_scorer=None,
                     features=None,
                     tolerance_components: Optional[Dict] = None) -> tuple:
        """
        Make final decision: ("approved"|"blocked", reason_string, layer2_score|None)

        Logic:
        1. Read configurable thresholds from Redis.
        2. If Layer 1 score < layer1_threshold → Approve immediately (fast path).
        3. Otherwise → Try Layer 2 with circuit breaker (threshold: layer2_threshold).
        4. Build a human-readable reason string combining scores + components.
        """
        cfg = self.get_tolerance_config()
        l1_thresh = cfg['layer1_threshold']
        l2_thresh = cfg['layer2_threshold']

        logger.info(f"\n[DECISION ENGINE] Processing transaction {transaction_id}")
        logger.info(f"[DECISION ENGINE] Thresholds → L1={l1_thresh}  L2={l2_thresh}")

        layer2_score = None

        # ── Fast path ────────────────────────────────────────────────────────
        if layer1_score < l1_thresh:
            decision = "approved"
            reason = (
                f"Layer 1 fast scan: low risk score ({layer1_score:.4f} < {l1_thresh} threshold). "
                f"Transaction approved immediately."
            )
            logger.info(f"[DECISION] ✓ APPROVED (L1 {layer1_score:.4f} < {l1_thresh})")
            return decision, reason, layer2_score

        # ── Suspicious — escalate to Layer 2 ─────────────────────────────────
        logger.info(f"[DECISION] Suspicious L1 score ({layer1_score:.4f}) — escalating to Layer 2")

        if layer2_scorer is None or features is None:
            logger.warning("[DECISION] Layer 2 scorer not provided, falling back to L1 only")
            decision = "approved" if layer1_score < 0.5 else "blocked"
            reason = (
                f"Layer 2 unavailable. Based on Layer 1 score ({layer1_score:.4f}): "
                f"{'approved' if decision == 'approved' else 'blocked'}."
            )
            return decision, reason, layer2_score

        try:
            @self.layer2_breaker
            def run_layer2():
                return layer2_scorer.score_layer2(features)

            layer2_score = run_layer2()

            if layer2_score > l2_thresh:
                decision = "blocked"
                top_component = self._top_component(tolerance_components)
                reason = (
                    f"Layer 1 elevated ({layer1_score:.4f}). "
                    f"Layer 2 deep analysis: {layer2_score:.4f} > {l2_thresh} threshold. "
                    f"Blocked. {top_component}"
                )
                logger.info(f"[DECISION] ✗ BLOCKED (L2 {layer2_score:.4f} > {l2_thresh})")
            else:
                decision = "approved"
                reason = (
                    f"Layer 1 elevated ({layer1_score:.4f}), but "
                    f"Layer 2 deep analysis cleared ({layer2_score:.4f} ≤ {l2_thresh}). "
                    f"Transaction approved."
                )
                logger.info(f"[DECISION] ✓ APPROVED (L2 {layer2_score:.4f} ≤ {l2_thresh})")

        except Exception as exc:
            logger.warning(f"[CIRCUIT BREAKER] ⚠ Layer 2 unavailable: {exc}")
            if layer1_score > 0.6:
                decision = "blocked"
                reason = (
                    f"Layer 2 failed (circuit breaker). "
                    f"Conservative block: Layer 1 score {layer1_score:.4f} too high."
                )
                logger.info(f"[DECISION] ✗ BLOCKED (L2 failed, L1 {layer1_score:.4f})")
            else:
                decision = "approved"
                reason = (
                    f"Layer 2 failed (circuit breaker). "
                    f"Layer 1 score {layer1_score:.4f} acceptable — approved."
                )
                logger.info(f"[DECISION] ✓ APPROVED (L2 failed, L1 {layer1_score:.4f})")

        return decision, reason, layer2_score

    def _top_component(self, components: Optional[Dict]) -> str:
        """Return a human-readable string naming the highest-scoring risk component."""
        if not components:
            return ""
        labels = {
            'habit_score':    "Purchase amount unusually high vs. user history",
            'seasonal_score': "Transaction time is outside normal hours",
            'merchant_score': "Merchant matches high-risk category",
        }
        top_key = max(components, key=lambda k: components[k])
        top_val = components[top_key]
        return f"Primary risk factor: {labels.get(top_key, top_key)} ({top_val:.0%})."
    
    def store_result(self, transaction_id: str, decision: str,
                     layer1_score: float, layer2_score: float = None,
                     transaction_data: dict = None,
                     tolerance_components: dict = None,
                     pipeline_steps: list = None,
                     performance: dict = None,
                     decision_reason: str = None,
                     user_balance: float = None) -> None:
        """Store decision result in Redis and publish to pub/sub channel"""
        import json
        from datetime import datetime

        key = f"result:{transaction_id}"
        value = {
            "decision": decision,
            "layer1_score": round(layer1_score, 4),
        }
        if layer2_score is not None:
            value["layer2_score"] = round(layer2_score, 4)

        self.redis_client.setex(key, 3600, str(value))
        logger.info(f"[RESULT STORAGE] Stored decision in Redis: {key} = {decision}")

        try:
            now = datetime.utcnow().isoformat() + "Z"
            message = {
                "transaction_id":    transaction_id,
                "decision":          decision,
                "fraud_score":       round(layer2_score, 4) if layer2_score is not None else round(layer1_score, 4),
                "layer1_score":      round(layer1_score, 4),
                "timestamp":         now,
                "decision_reason":   decision_reason or "",
                "tolerance_components": tolerance_components or {},
                "pipeline_steps":    pipeline_steps or [],
                "performance":       performance or {},
                "user_balance":      user_balance,
            }
            if layer2_score is not None:
                message["layer2_score"] = round(layer2_score, 4)
            if transaction_data:
                message["amount"]   = transaction_data.get("amount")
                message["merchant"] = transaction_data.get("merchant")

            self.redis_client.publish("fraud_results", json.dumps(message))
            logger.info(f"[RESULT STORAGE] Published to pub/sub: {transaction_id[:8]}... → {decision}")
        except Exception as e:
            logger.error(f"[RESULT STORAGE] Failed to publish to pub/sub: {e}")
