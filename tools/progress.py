"""
Lightweight progress emitter using a ContextVar.

Usage in any node:
    from tools.progress import emit
    emit("🔍 Scraping Google Trends…")

The bot sets a callback before invoking the graph.
If no callback is set, emit() is a no-op (safe for CLI runs too).
"""
from contextvars import ContextVar
from typing import Callable, Optional

_callback: ContextVar[Optional[Callable[[str], None]]] = ContextVar(
    "_progress_callback", default=None
)


def set_callback(cb: Optional[Callable[[str], None]]) -> None:
    _callback.set(cb)


def emit(message: str) -> None:
    cb = _callback.get()
    if cb:
        cb(message)
