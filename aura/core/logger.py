"""
AURA OS — Structured Logging Subsystem
Configures contextual log sinks, masks credentials, and prepares for journald.
"""

import sys
from typing import Any, Dict
from loguru import logger

# List of sensitive keys to redact from logs
SENSITIVE_KEYS = {
    "password", "secret", "token", "auth", "credential",
    "key", "api_key", "bearer", "private_key"
}


def redact_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive keys in log payloads."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = redact_sensitive_data(v)
        return sanitized
    if isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


def setup_logger(log_level: str = "INFO", json_output: bool = False) -> None:
    """Initialize loguru sinks for daemon operation."""
    logger.remove()

    if json_output:
        logger.add(
            sys.stdout,
            level=log_level,
            serialize=True,
            enqueue=True,
        )
    else:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        logger.add(
            sys.stdout,
            level=log_level,
            format=log_format,
            colorize=True,
            enqueue=True,
        )


__all__ = ["logger", "setup_logger", "redact_sensitive_data"]
