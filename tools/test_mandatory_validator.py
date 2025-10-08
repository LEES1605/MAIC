"""
Mandatory Validator Test
"""

from mandatory_validator import MandatoryValidator, RuleViolationError

def test_mandatory_validator():
    """Test mandatory validator system"""
    print("Mandatory Validator Test Started")
    
    validator = MandatoryValidator()
    
    # Test cases
    test_cases = [
        ("streamlit run app.py", "streamlit_run"),
        ("streamlit run app.py --server.port 8520", "streamlit_run"),
        ("streamlit run app.py --server.port 8501", "streamlit_run"),
        ("test_new_file.py", "file_creation"),
        ("src/new_file.py", "file_creation"),
    ]
    
    print("\nTest Execution:")
    
    for command, action_type in test_cases:
        try:
            result = validator.validate_before_execution(action_type, command)
            status = "PASS" if result.get("valid", True) else "FAIL"
            print(f"[{status}] {command}")
            if not result.get("valid", True):
                print(f"   Error: {result.get('error', '')}")
                print(f"   Suggestion: {result.get('suggestion', '')}")
        except RuleViolationError as e:
            print(f"[BLOCKED] {command}")
            print(f"   Error: {e.message}")
            print(f"   Suggestion: {e.suggestion}")
    
    print("\nTest Completed")

if __name__ == "__main__":
    test_mandatory_validator()
