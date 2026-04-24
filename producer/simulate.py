"""
Test Transaction Producer

Generates demo transactions with controlled scenarios to showcase the pipeline.

Scenarios:
1. Normal transactions: low amounts, regular merchants, regular users
2. Suspicious transactions: large amounts, unknown merchants
3. Behavioral anomalies: large deviation from user history
4. Circuit breaker test: can be triggered manually

Usage:
    python producer/simulate.py
"""

import requests
import json
import time
import logging
from typing import List, Tuple
from jose import jwt

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

API_BASE_URL = "http://localhost:8000"
SECRET_KEY = "payguard-demo-secret-key-change-in-production"
ALGORITHM = "HS256"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# TOKEN GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_token(user_id: str) -> str:
    """Generate a JWT token for the given user"""
    token = jwt.encode({"sub": user_id}, SECRET_KEY, algorithm=ALGORITHM)
    return token

# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTION SCENARIOS
# ══════════════════════════════════════════════════════════════════════════════

class TransactionScenario:
    """Represents a test transaction scenario"""
    
    def __init__(self, name: str, user_id: str, amount: float, 
                 merchant: str, description: str = ""):
        self.name = name
        self.user_id = user_id
        self.amount = amount
        self.merchant = merchant
        self.description = description
    
    def submit(self):
        """Submit this scenario to the API"""
        token = generate_token(self.user_id)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": self.amount,
            "merchant": self.merchant,
            "description": self.description
        }
        
        logger.info(f"\n{'='*80}")
        logger.info(f"[SCENARIO] {self.name}")
        logger.info(f"[SCENARIO] User: {self.user_id} | Amount: ${self.amount:.2f} | Merchant: {self.merchant}")
        logger.info(f"{'='*80}")
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/transaction",
                headers=headers,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"[API RESPONSE] ✓ {result['message']}")
                logger.info(f"[TRANSACTION ID] {result['transaction_id']}")
            else:
                logger.error(f"[API RESPONSE] ✗ Status {response.status_code}: {response.text}")
        
        except requests.exceptions.ConnectionError:
            logger.error("[API RESPONSE] ✗ Cannot connect to API. Is it running on port 8000?")
        except Exception as e:
            logger.error(f"[API RESPONSE] ✗ Error: {str(e)}")

# ══════════════════════════════════════════════════════════════════════════════
# TEST SCENARIOS
# ══════════════════════════════════════════════════════════════════════════════

def get_demo_scenarios() -> List[TransactionScenario]:
    """Get all demo scenarios in a logical order"""
    return [
        # Scenario 1: Normal transaction (should be approved fast)
        TransactionScenario(
            name="1. NORMAL TRANSACTION (Low Risk)",
            user_id="user_001",
            amount=75.50,
            merchant="Starbucks Coffee",
            description="Regular coffee purchase"
        ),
        
        # Scenario 2: Another normal transaction from same user
        TransactionScenario(
            name="2. NORMAL TRANSACTION #2 (Low Risk)",
            user_id="user_001",
            amount=120.00,
            merchant="Target Retail",
            description="Grocery shopping"
        ),
        
        # Scenario 3: Large transaction from user with low history (suspicious)
        TransactionScenario(
            name="3. BEHAVIORAL ANOMALY (High Risk)",
            user_id="user_001",
            amount=8500.00,
            merchant="unknown_offshore_merchant.biz",
            description="Large purchase from unknown merchant"
        ),
        
        # Scenario 4: New user, normal transaction
        TransactionScenario(
            name="4. NEW USER, NORMAL AMOUNT (Low Risk)",
            user_id="user_002",
            amount=45.00,
            merchant="McDonald's Restaurant",
            description="Meal purchase"
        ),
        
        # Scenario 5: Existing user, normal range
        TransactionScenario(
            name="5. RETURNING USER, NORMAL (Low Risk)",
            user_id="user_002",
            amount=65.00,
            merchant="CVS Pharmacy",
            description="Pharmacy purchase"
        ),
        
        # Scenario 6: User 3, establish history
        TransactionScenario(
            name="6. NEW USER, SMALL TRANSACTION (Low Risk)",
            user_id="user_003",
            amount=25.00,
            merchant="Uber Eats",
            description="Food delivery"
        ),
        
        # Scenario 7: User 3, escalating pattern
        TransactionScenario(
            name="7. SAME USER, INCREASED AMOUNT (Medium Risk)",
            user_id="user_003",
            amount=150.00,
            merchant="Amazon.com",
            description="Online shopping"
        ),
        
        # Scenario 8: User 3, huge spike (very suspicious)
        TransactionScenario(
            name="8. SUSPICIOUS PATTERN (Very High Risk)",
            user_id="user_003",
            amount=12500.00,
            merchant="LuxuryWatches_CN.ru",
            description="Suspicious high-value purchase"
        ),
    ]

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Run demo scenarios"""
    
    logger.info("="*80)
    logger.info("PayGuard Demo - Transaction Producer")
    logger.info("="*80)
    logger.info(f"API Base URL: {API_BASE_URL}")
    logger.info("="*80)
    
    # Check if API is available
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            logger.info("✓ API is healthy and ready\n")
        else:
            logger.error("✗ API health check failed")
            return
    except:
        logger.error("✗ Cannot connect to API. Make sure it's running:")
        logger.error("   uvicorn api.main:app --reload\n")
        return
    
    scenarios = get_demo_scenarios()
    
    for i, scenario in enumerate(scenarios, 1):
        scenario.submit()
        
        # Small delay between scenarios to avoid overwhelming
        if i < len(scenarios):
            logger.info(f"\n[DEMO] Waiting 3 seconds before next scenario...")
            time.sleep(3)
    
    logger.info(f"\n{'='*80}")
    logger.info("✓ All demo scenarios submitted!")
    logger.info("="*80)
    logger.info("\nCheck the consumer terminal for detailed pipeline execution logs.")
    logger.info("Open another terminal and query Redis to see the results:")
    logger.info("   redis-cli")
    logger.info("   > KEYS result:*")
    logger.info("   > GET result:<transaction_id>")

if __name__ == "__main__":
    main()
