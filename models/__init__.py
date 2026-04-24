"""
Model definitions for PayGuard fraud detection
"""

import numpy as np

class Layer1MockModel:
    """Fast, lightweight model for initial fraud scoring"""
    
    def predict_proba(self, features):
        """
        Layer 1: Fast model
        Score < 0.4: Approve
        Score >= 0.4: Escalate to Layer 2
        """
        amount = features[0][0]
        avg_amount = features[0][1]
        
        if avg_amount == 0:
            ratio = 1.0
        else:
            ratio = amount / avg_amount
        
        fraud_prob = min(0.95, max(0.05, (ratio - 1.0) * 0.2))
        legit_prob = 1.0 - fraud_prob
        
        return np.array([[legit_prob, fraud_prob]])

class Layer2MockModel:
    """Deep, complex model for suspicious transactions"""
    
    def predict_proba(self, features):
        """
        Layer 2: Deep model
        Score <= 0.7: Approve
        Score > 0.7: Block
        """
        amount = features[0][0]
        avg_amount = features[0][1]
        tx_count = features[0][2]
        
        fraud_prob = 0.1
        
        if avg_amount > 0:
            ratio = amount / avg_amount
            fraud_prob += (ratio - 1.0) * 0.25
        
        if tx_count < 3:
            fraud_prob += 0.2
        elif tx_count < 10:
            fraud_prob += 0.1
        
        fraud_prob = min(0.95, max(0.05, fraud_prob))
        legit_prob = 1.0 - fraud_prob
        
        return np.array([[legit_prob, fraud_prob]])
