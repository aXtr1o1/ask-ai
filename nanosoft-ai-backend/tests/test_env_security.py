import pytest
import os
import sys
import logging
from io import StringIO

# Path to find config.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../app")))

def test_env_loading_security():
    """
    TC-SEC-001: Environment Security
    Goal: Ensure API_KEY is loaded but never leaked in logs during a crash.
    """
    # 1. Capture logs
    log_output = StringIO()
    handler = logging.StreamHandler(log_output)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    try:
        from .env import GOOGLE_API_KEY
        
        # Test Case: Key should exist
        assert GOOGLE_API_KEY is not None, "❌ GOOGLE_API_KEY not found in .env"
        
        # 2. TRIGGER THE BREAKING POINT (Simulate a crash)
        # We purposely log an error to see if the key appears in the logs
        logging.error(f"System crashed. API Key status: {GOOGLE_API_KEY}")
        
        captured_logs = log_output.getvalue()
        
        # 3. SECURITY CHECK
        # In a secure system, the actual key should NEVER be in the log text
        if "AIza" in captured_logs: # 'AIza' is the standard prefix for Google API keys
             pytest.fail(
                "🔥 NOT PASSED: API Key leaked in logs!\n"
                "Explanation: Your error handling is printing the actual key value. "
                "An attacker with access to your logs now has your credentials."
            )
        else:
            print("\n✅ PASSED: API Key is loaded, but logs are clean.")
            print("Explanation: The system failed without exposing the secret value.")

    except Exception as e:
        pytest.fail(f"❌ Setup Error: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-s"])