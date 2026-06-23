"""
core/config.py
Billiam OS — Configuration Management

Manages Billiam OS configuration via YAML file, environment variables,
and CLI arguments. Provides typed access to all configuration values
with Pydantic schema validation.

Configuration file locations (first found wins):
1. $BILLIAM_CONFIG or --config path
2. ~/.config/billiam-os/config.yaml
3. ~/.billiam.yaml
4. ./billiam.yaml
5. Default values
"""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("billiam.config")

# ── Pydantic Schema for Config Validation ─────────────────────────────────────

_has_pydantic = False
try:
    from pydantic import BaseModel, field_validator  # noqa: F401
    _has_pydantic = True
except ImportError:
    BaseModel = object  # type: ignore[misc]


class LLMConfig(BaseModel if _has_pydantic else object):  # type: ignore[no-redef, misc]
    """LLM backend configuration with validation."""
    api_base: str = "http://localhost:8080/v1"
    model: str
    temperature: float = 0.2
    max_tokens: int = 512

    if _has_pydantic:
        @field_validator("temperature")
        @classmethod
        def check_temperature(cls, v: float) -> float:
            if not 0.0 <= v <= 2.0:
                raise ValueError(f"Temperature must be between 0 and 2, got {v}")
            return v

        @field_validator("max_tokens")
        @classmethod
        def check_max_tokens(cls, v: int) -> int:
            if v < 1:
                raise ValueError(f"max_tokens must be positive, got {v}")
            return v


def validate_config(data: dict) -> list[str]:
    """Validate configuration data against Pydantic schema.

    Args:
        data: Raw configuration dictionary.

    Returns:
        List of validation error messages (empty if valid).
    """
    if not _has_pydantic:
        return ["pydantic not installed. Install with: pip install pydantic"]

    errors = []
    llm_data = data.get("llm", {})
    try:
        LLMConfig(**llm_data)
    except Exception as e:
        errors.append(str(e))
    return errors

# Default configuration
DEFAULT_CONFIG: dict[str, Any] = {
    "billiam": {
        "name": "Billiam",
        "wake_word": "billiam",
        "polite_mode": True,
    },
    "llm": {
        "api_base": "http://localhost:8080/v1",
        "model": "qwen-2.5-coder-3b-instruct",
        "temperature": 0.2,
        "max_tokens": 512,
        "context_length": 4096,
    },
    "tts": {
        "enabled": True,
        "provider": "edge-tts",
        "voice": "en-GB-RyanNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "fallback_provider": "espeak-ng",
    },
    "stt": {
        "enabled": True,
        "model_size": "base",
        "language": "en",
        "wake_word_required": True,
        "device": "cpu",
        "compute_type": "int8",
    },
    "audio": {
        "input_device": None,
        "output_device": None,
        "sample_rate": 16000,
        "capture_timeout": 10,
    },
    "memory": {
        "storage_path": "~/.config/billiam-os/memory.json",
        "max_history": 100,
    },
    "logging": {
        "level": "INFO",
        "file": "~/.config/billiam-os/billiam.log",
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    },
    "security": {
        "banned_patterns": True,
        "require_privilege_confirmation": True,
        "max_command_timeout": 20,
    },
}


def find_config_file() -> str | None:
    """Locate the configuration file.

    Returns:
        Path to config file, or None if not found.
    """
    # Check environment variable
    env_path = os.environ.get("BILLIAM_CONFIG")
    if env_path and os.path.exists(env_path):
        return env_path

    # Check standard locations
    candidates = [
        Path.home() / ".config" / "billiam-os" / "config.yaml",
        Path.home() / ".billiam.yaml",
        Path("billiam.yaml"),
        Path("config.yaml"),
    ]

    for path in candidates:
        if path.exists():
            return str(path)

    return None


def load_yaml_config(path: str) -> dict[str, Any]:
    """Load YAML configuration from file.

    Args:
        path: Path to YAML file.

    Returns:
        Parsed configuration dict.
    """
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        logger.warning("PyYAML not installed. Install with: pip install pyyaml")
        return {}
    except Exception as e:
        logger.warning("Failed to load config %s: %s", path, e)
        return {}


def merge_config(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict.

    Args:
        base: Base configuration.
        override: Override values to merge.

    Returns:
        Merged configuration.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | None = None) -> dict[str, Any]:
    """Load complete configuration from all sources.

    Priority (highest wins):
        1. Explicit path argument
        2. Environment variable BILLIAM_CONFIG
        3. Config file in standard locations
        4. Environment variables (BILLIAM_*)
        5. Default values

    Args:
        path: Explicit config file path.

    Returns:
        Final merged configuration.
    """
    config = DEFAULT_CONFIG.copy()

    # Load from file
    config_path = path or find_config_file()
    if config_path:
        file_config = load_yaml_config(config_path)
        config = merge_config(config, file_config)
        logger.info("Loaded config from %s", config_path)

    # Environment variable overrides
    env_mapping = {
        "BILLIAM_API_BASE": ("llm", "api_base"),
        "BILLIAM_MODEL": ("llm", "model"),
        "BILLIAM_TEMPERATURE": ("llm", "temperature", float),
        "BILLIAM_MAX_TOKENS": ("llm", "max_tokens", int),
        "BILLIAM_LOG_LEVEL": ("logging", "level"),
        "BILLIAM_TTS_VOICE": ("tts", "voice"),
        "BILLIAM_STT_MODEL": ("stt", "model_size"),
        "BILLIAM_MEMORY_PATH": ("memory", "storage_path"),
    }

    for env_var, config_key in env_mapping.items():
        value = os.environ.get(env_var)
        if value is not None:
            section = config_key[0]
            key = config_key[1]
            cast = config_key[2] if len(config_key) > 2 else str
            try:
                config[section][key] = cast(value)
            except (ValueError, TypeError):
                logger.warning("Invalid value for %s: %s", env_var, value)

    return config


def get_config_value(
    config: dict, key_path: str, default: Any = None
) -> Any:
    """Get a configuration value by dot-separated key path.

    Args:
        config: Configuration dict.
        key_path: Dot-separated path (e.g., 'llm.api_base').
        default: Default value if key not found.

    Returns:
        Configuration value or default.
    """
    keys = key_path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return default
        else:
            return default
    return value if value is not None else default


def save_config(config: dict[str, Any], path: str) -> bool:
    """Save configuration to a YAML file.

    Args:
        config: Configuration dict to save.
        path: Path to write to.

    Returns:
        True if save succeeded.
    """
    try:
        import yaml
        os.makedirs(os.path.dirname(os.path.expanduser(path)), exist_ok=True)
        with open(os.path.expanduser(path), "w") as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
        logger.info("Config saved to %s", path)
        return True
    except ImportError:
        logger.error("PyYAML not installed. Cannot save config.")
        return False
    except Exception as e:
        logger.error("Failed to save config: %s", e)
        return False
