"""
Model Scoring Modules

Responsibilities:
- Load pre-trained models
- Run Layer 1 (fast) and Layer 2 (deep) scoring
- Return fraud probabilities

Academic Point:
Dual-layer architecture allows high-throughput systems to make most decisions
(>95% of transactions) with a fast, lightweight model, while complex edge cases
are delegated to a more expensive deep model. This optimizes latency vs. accuracy.
"""

import pickle
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class ModelScorer:
    """Loads and runs fraud detection models"""
    
    def __init__(self, layer1_path: str = "models/layer1.pkl", 
                 layer2_path: str = "models/layer2.pkl"):
        # Load Layer 1 model
        with open(layer1_path, 'rb') as f:
            self.layer1_model = pickle.load(f)
        logger.info(f"[MODEL LOADER] ✓ Layer 1 model loaded from {layer1_path}")
        
        # Load Layer 2 model
        with open(layer2_path, 'rb') as f:
            self.layer2_model = pickle.load(f)
        logger.info(f"[MODEL LOADER] ✓ Layer 2 model loaded from {layer2_path}")
    
    def score_layer1(self, features) -> float:
        """
        Layer 1: Fast, shallow model for initial risk assessment.
        
        Decision threshold: 0.4
        - score < 0.4  → Low risk (approve immediately)
        - score >= 0.4 → Suspicious (escalate to Layer 2)
        """
        probs = self.layer1_model.predict_proba(features)
        fraud_probability = probs[0][1]  # Index 1 is fraud class
        
        logger.info(
            f"[LAYER 1 SCORING] Fraud probability: {fraud_probability:.4f} "
            f"{'→ LOW RISK, fast-track approval' if fraud_probability < 0.4 else '→ SUSPICIOUS, escalate to Layer 2'}"
        )
        
        return fraud_probability
    
    def score_layer2(self, features) -> float:
        """
        Layer 2: Deep, complex model for suspicious transactions.
        
        Decision threshold: 0.7
        - score <= 0.7 → Approve
        - score > 0.7  → Block
        
        Only called if Layer 1 score >= 0.4 (suspicious).
        """
        probs = self.layer2_model.predict_proba(features)
        fraud_probability = probs[0][1]  # Index 1 is fraud class
        
        logger.info(
            f"[LAYER 2 SCORING] Fraud probability: {fraud_probability:.4f} "
            f"{'→ BLOCK (high confidence in fraud)' if fraud_probability > 0.7 else '→ APPROVE (acceptable risk)'}"
        )
        
        return fraud_probability
