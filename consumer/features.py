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
import os
import time
import datetime
import random
from typing import Dict, List

logger = logging.getLogger(__name__)

class FeatureExtractor:
    """Extracts and engineers features from transactions"""
    
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

    def get_tolerance_components(self, transaction: Dict, profile: Dict) -> Dict:
        """
        Calculate per-component tolerance scores (0.0 = safe, 1.0 = very suspicious).

        Components:
          - habit_score   : how much this deviates from the user's typical spending
          - seasonal_score: risk based on time-of-day / day-of-week patterns
          - merchant_score: risk based on merchant name / category signals
        """
        amount = transaction['amount']
        merchant = transaction.get('merchant', '')
        ts = transaction.get('timestamp', time.time())

        # ── 1. Habit score ────────────────────────────────────────────────────
        avg_amount = profile.get('avg_amount', 0.0)
        tx_count = profile.get('tx_count', 0)

        if avg_amount > 0 and tx_count >= 2:
            ratio = amount / avg_amount
            # ratio 1.0 = normal; ratio 5.0+ = very suspicious → maps to 0.0–1.0
            habit_score = min(1.0, max(0.0, (ratio - 1.0) / 4.0))
        elif tx_count == 0:
            habit_score = 0.1   # first-ever transaction: slight uncertainty
        else:
            habit_score = 0.2   # too few transactions to form a baseline

        # ── 2. Seasonal / time score ─────────────────────────────────────────
        dt = datetime.datetime.fromtimestamp(ts)
        hour = dt.hour

        if 0 <= hour <= 4:
            time_risk = 0.8    # late night
        elif 5 <= hour <= 8:
            time_risk = 0.3    # early morning
        elif 9 <= hour <= 21:
            time_risk = 0.0    # normal business hours
        else:
            time_risk = 0.4    # late evening

        if dt.weekday() >= 5:  # Saturday / Sunday
            time_risk = min(1.0, time_risk + 0.1)

        seasonal_score = time_risk

        # ── 3. Merchant score ────────────────────────────────────────────────
        ml = merchant.lower()
        high_risk_kw    = ['offshore', 'unknown', 'crypto', 'casino', 'wire', '.biz', 'foreign']
        medium_risk_kw  = ['international', 'atm', 'withdrawal', 'western union', 'pawnshop']
        low_risk_kw     = [
            'starbucks', 'target', 'walmart', 'amazon', 'mcdonalds', 'shell',
            'bp', 'costco', 'cvs', 'walgreens', 'apple', 'netflix', 'spotify',
        ]

        if any(kw in ml for kw in high_risk_kw):
            merchant_score = 0.9
        elif any(kw in ml for kw in low_risk_kw):
            merchant_score = 0.05
        elif any(kw in ml for kw in medium_risk_kw):
            merchant_score = 0.5
        else:
            merchant_score = 0.25   # unknown merchant

        components = {
            'habit_score':    round(habit_score,    4),
            'seasonal_score': round(seasonal_score, 4),
            'merchant_score': round(merchant_score, 4),
        }
        logger.info(
            f"[TOLERANCE] habit={habit_score:.2f}  "
            f"seasonal={seasonal_score:.2f}  merchant={merchant_score:.2f}"
        )
        return components

    def get_or_init_balance(self, user_id: str) -> float:
        """Return user's available balance, initialising a random value for new users."""
        key = f"user:{user_id}:balance"
        raw = self.redis_client.get(key)
        if raw is None:
            initial = round(random.uniform(500.0, 5000.0), 2)
            self.redis_client.set(key, str(initial))
            logger.info(f"[BALANCE] Initialised balance for user={user_id}: ${initial:.2f}")
            return initial
        return float(raw)

    def deduct_balance(self, user_id: str, amount: float) -> float:
        """Deduct amount from user balance on approved transactions. Returns new balance."""
        key = f"user:{user_id}:balance"
        current = self.get_or_init_balance(user_id)
        new_balance = round(max(0.0, current - amount), 2)
        self.redis_client.set(key, str(new_balance))
        return new_balance
