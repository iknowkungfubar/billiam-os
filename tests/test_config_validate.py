"""
tests/test_config_validate.py
Billiam OS — Config Validation Tests
"""

from core.config import validate_config


class TestConfigValidate:
    """Test config validation."""

    def test_valid_config_empty(self):
        """Empty config must return a list."""
        errors = validate_config({})
        assert isinstance(errors, list)

    def test_valid_config_full(self):
        """Full valid config must pass."""
        data = {
            "llm": {
                "model": "test-model",
                "api_base": "http://localhost:8080/v1",
                "temperature": 0.5,
                "max_tokens": 1024,
            }
        }
        errors = validate_config(data)
        if errors and "pydantic not installed" in errors[0]:
            pass
        else:
            assert len(errors) == 0, f"Expected no errors, got: {errors}"

    def test_valid_config_minimal(self):
        """Minimal valid config with only required fields."""
        data = {"llm": {"model": "test-model"}}
        errors = validate_config(data)
        if errors and "pydantic not installed" in errors[0]:
            pass
        else:
            assert len(errors) == 0

    def test_invalid_temperature(self):
        """Temperature out of range must be rejected."""
        data = {"llm": {"model": "test", "temperature": 99.9}}
        errors = validate_config(data)
        if errors and "pydantic not installed" in errors[0]:
            pass
        else:
            assert len(errors) > 0
            assert "temperature" in errors[0].lower() or "Temperature" in errors[0]

    def test_invalid_max_tokens(self):
        """Negative max_tokens must be rejected."""
        data = {"llm": {"model": "test", "max_tokens": -1}}
        errors = validate_config(data)
        if errors and "pydantic not installed" in errors[0]:
            pass
        else:
            assert len(errors) > 0

    def test_validate_config_returns_list(self):
        """validate_config must always return a list."""
        result = validate_config({})
        assert isinstance(result, list)
