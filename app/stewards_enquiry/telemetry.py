"""Structured logging for tool calls — invariant 5: everything is traceable.

Every tool invocation emits exactly one JSON log line: tool name, a short
digest of the input (for audit correlation, never the raw input), duration,
and outcome. The logger has no handler of its own; it propagates to the root
logger, so the runtime (uvicorn locally, AgentCore observability when
deployed) decides where lines go and pytest's caplog can capture them.
"""

import functools
import hashlib
import json
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger("stewards_enquiry.tools")

# In-memory record of the current triage's successful tool calls, used to
# cross-check the model's verdict against what actually happened (PR #2
# review finding: nothing correlated the verdict with the tool trace).
_trace: ContextVar[list[dict] | None] = ContextVar("steward_tool_trace", default=None)


def begin_trace() -> None:
    _trace.set([])


def get_trace() -> list[dict]:
    return list(_trace.get() or [])


def end_trace() -> None:
    _trace.set(None)


def configure_logging() -> None:
    """Make stewards_enquiry.* log lines visible under any runtime.

    Without this the namespace inherits the root logger's WARNING threshold
    and every INFO tool line is silently dropped. Called from main.py; safe
    to call repeatedly; leaves existing root handlers (uvicorn, AgentCore)
    untouched.
    """
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("stewards_enquiry").setLevel(logging.INFO)


def input_digest(*args: Any, **kwargs: Any) -> str:
    """Short, stable digest of a tool's input, for audit correlation."""
    payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def traced(fn: Callable) -> Callable:
    """Wrap a tool so every call logs one structured JSON line, even on error."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        outcome = "ok"
        try:
            result = fn(*args, **kwargs)
            trace = _trace.get()
            if trace is not None:
                trace.append({"tool": fn.__name__, "result": result})
            return result
        except Exception as exc:
            outcome = f"error:{type(exc).__name__}"
            raise
        finally:
            line = {
                "event": "tool_call",
                "tool": fn.__name__,
                "input_digest": input_digest(*args, **kwargs),
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "outcome": outcome,
            }
            logger.info(json.dumps(line, separators=(",", ":")))

    return wrapper
