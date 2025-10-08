"""
Port Validation Test
"""

from mandatory_validator import MandatoryValidator, RuleViolationError

def test_port_validation():
    """Test port validation specifically"""
    print("Port Validation Test Started")
    
    validator = MandatoryValidator()
    
    # Test cases for port validation
    test_commands = [
        "streamlit run app.py",  # Should PASS
        "streamlit run app.py --server.port 8520",  # Should FAIL
        "streamlit run app.py --server.port 8501",  # Should FAIL (still uses --server.port)
    ]
    
    print("\nTesting Streamlit Commands:")
    
    for command in test_commands:
        try:
            result = validator.validate_streamlit_command(command)
            if result.get("valid", True):
                print(f"[PASS] {command}")
                if result.get("action"):
                    print(f"   Action: {result.get('action')}")
            else:
                print(f"[FAIL] {command}")
                print(f"   Error: {result.get('error', '')}")
                print(f"   Suggestion: {result.get('suggestion', '')}")
                if result.get("blocking"):
                    print("   [BLOCKING] This would stop execution")
        except Exception as e:
            print(f"[ERROR] {command}: {e}")
    
    print("\nPort Validation Test Completed")

if __name__ == "__main__":
    test_port_validation()
