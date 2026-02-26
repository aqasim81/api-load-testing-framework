"""Custom exception hierarchy for LoadForge."""

from __future__ import annotations


class LoadForgeError(Exception):
    """Base exception for all LoadForge errors.

    All custom exceptions in the LoadForge framework inherit from this class,
    making it easy to catch any LoadForge-specific error with a single
    except clause.
    """


class ScenarioError(LoadForgeError):
    """Raised when a scenario definition is invalid.

    Examples:
        - A class decorated with @scenario has no @task methods.
        - A @task method is not a coroutine function.
        - A scenario file cannot be loaded or parsed.
    """


class ConfigError(LoadForgeError):
    """Raised when configuration is invalid or missing.

    Examples:
        - Required environment variable has an invalid value.
        - Configuration value is out of acceptable range.
    """
