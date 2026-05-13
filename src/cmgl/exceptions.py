from __future__ import annotations


class CMGLError(Exception):
    """Base exception for CMGL."""


class LedgerError(CMGLError):
    """Raised when ledger records cannot be read or verified."""


class LifecycleError(CMGLError):
    """Raised when a memory lifecycle transition is invalid."""


class AdapterOperationError(CMGLError):
    """Raised when an external adapter operation is blocked or fails."""


class OptionalDependencyError(CMGLError):
    """Raised when an optional adapter dependency is not installed."""

    def __init__(self, dependency: str, extra: str) -> None:
        self.dependency = dependency
        self.extra = extra
        super().__init__(
            f"Optional dependency '{dependency}' is required. Install it with "
            f"'pip install \"cmgl[{extra}]\"' or 'uv add \"cmgl[{extra}]\"'."
        )
