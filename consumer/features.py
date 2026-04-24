"""
Feature Extraction Module

Responsibilities:
- Extract raw transaction data into ML-friendly features
- Query Redis for user behavioral history
- Construct feature vectors for ML models

Academic Point:
Feature engineering is the bridge between raw business data and ML models.
This module demonstrates how to enrich simple transaction data with historical
context to improve model decision quality.
"""

import redis
import numpy as np
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class FeatureExtractor:
    """Extracts and engineers features from transactions"""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        logger.info(f"[FEATURE EXTRACTOR] Initialized, redis={redis_host}:{redis_port}")
    
    def get_user_profile(self, user_id: str) -> Dict[str, float]:
        """
        Retrieve user's behavioral profile from Redis.
        
        Returns:
        {
            'avg_amount': float,
            'tx_count': int,
            'last_timestamp': float,
            'days_since_last_tx': float
        }
        """
        key = f"user:{user_id}:profile"
        profile = self.redis_client.hgetall(key)
        
        if not profile:
            logger.debug(f"[REDIS LOOKUP] No profile for user={user_id}, using defaults")
            return {
                'avg_amount': 0.0,
                'tx_count': 0,
                'last_timestamp': 0.0,
                'days_since_last_tx': 999.0
            }
        
        logger.debug(
            f"[REDIS LOOKUP] Found profile for user={user_id}: "
            f"avg=${profile.get('avg_amount', 0)}, count={profile.get('tx_count', 0)}"
        )
        
        return {
            'avg_amount': float(profile.get('avg_amount', 0.0)),
            'tx_count': int(profile.get('tx_count', 0)),
            'last_timestamp': float(profile.get('last_timestamp', 0.0)),
            'days_since_last_tx': float(profile.get('days_since_last_tx', 999.0))
        }
    
    def extract_features(self, transaction: Dict) -> np.ndarray:
        """
        Extract feature vector from transaction + user profile.
        
        Feature vector: [amount, avg_amount, tx_count, days_since_last_tx]
        """
        user_id = transaction['user_id']
        amount = transaction['amount']
        
        # Get user history
        profile = self.get_user_profile(user_id)
        
        # Construct feature vector
        features = np.array([[
            amount,
            profile['avg_amount'],
            profile['tx_count'],
            profile['days_since_last_tx']
        ]])
        
        logger.info(
            f"[FEATURE EXTRACTION] tx_id={transaction['transaction_id'][:8]}... "
            f"user={user_id} features=[${amount:.0f}, "
            f"avg=${profile['avg_amount']:.0f}, "
            f"count={profile['tx_count']}, "
            f"days_since={profile['days_since_last_tx']:.1f}]"
        )
        
        return features
    
    def update_user_profile(self, transaction: Dict) -> None:
        """Update user's behavioral profile with new transaction"""
        user_id = transaction['user_id']
        amount = transaction['amount']
        timestamp = transaction['timestamp']
        
        key = f"user:{user_id}:profile"
        profile = self.redis_client.hgetall(key)
        
        # Calculate new statistics
        old_count = int(profile.get('tx_count', 0))
        new_count = old_count + 1
        
        old_avg = float(profile.get('avg_amount', 0.0))
        new_avg = (old_avg * old_count + amount) / new_count
        
        old_timestamp = float(profile.get('last_timestamp', 0.0))
        days_since = 0.0  # Just made a transaction
        
        # Update profile in Redis
        self.redis_client.hset(
            key,
            mapping={
                'tx_count': new_count,
                'avg_amount': round(new_avg, 2),
                'last_timestamp': timestamp,
                'days_since_last_tx': days_since
            }
        )
        
        logger.info(
            f"[PROFILE UPDATE] user={user_id} "
            f"count={old_count}→{new_count}, "
            f"avg=${old_avg:.2f}→${new_avg:.2f}"
        )
