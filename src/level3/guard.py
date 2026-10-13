"""
ToolGuard: loop detection, per tool call limits, total call limits.
All safety checks before tool execution.
"""

import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class LoopDetector:
    """
    Detect when the model is looping (calling the same tool with same args repeatedly).
    """
    def __init__(self, max_repeat: int = 3):
        self.max_repeat = max_repeat
        self._history: list[str] = []

    def _key(self, tool_name: str, arguments: dict) -> str:
        args_hash = hashlib.md5(
            json.dumps(arguments, sort_keys=True).encode()
        ).hexdigest()[:8]
        return f"{tool_name}:{args_hash}"

    def is_looping(self, tool_name: str, arguments: dict) -> bool:
        """Returns True if this exact call has been seen max_repeat times."""
        key = self._key(tool_name, arguments)
        count = self._history.count(key)
        self._history.append(key)
        return count >= self.max_repeat

    def reset(self) -> None:
        self._history = []



class ToolGuard:
    """
    Combined safety guard: allowlist + per-tool limits + total limits
    """

    def __init__(
        self,
        allowed_tools: set[str] | None = None,
        max_calls_per_tool: int = 5,
        max_total_calls: int = 3,
    ):
        self.allowed_tools = allowed_tools  # None = allow all registered
        self.max_calls_per_tool = max_calls_per_tool
        self.max_total_calls = max_total_calls
        self._call_counts: dict[str, int] = {}
        self._total_calls: int = 0
        self.loop_detector = LoopDetector(max_repeat=3)
    

    def check(self, tool_name: str, arguments: dict) -> None:
        """
        Check all guards. Returns error string if blocked, None if ok.
        """
        # Allowlist check
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            logger.warning(f"Blocked non-allowlisted tool: {tool_name!r}")
            return f"Error: Tool '{tool_name}' is not permitted"

        # Per-tool limit
        count = self._call_counts.get(tool_name, 0)
        if count >= self.max_calls_per_tool:
            return f"Error: Tool '{tool_name}' has been called too many times ({self.max_calls_per_tool} max)"

        # Loop detection
        if self.loop_detector.is_looping(tool_name, arguments):
            logger.warning(f"Loop detected: {tool_name}({arguments})")
            return f"Error: Loop detected — tool '{tool_name}' called repeatedly with identical arguments"

        # Total call limit (last, as a global safety cap)
        if self._total_calls >= self.max_total_calls:
            return f"Error: Maximum total tool calls ({self.max_total_calls}) reached"

        return None  # All checks passed

    def record(self, tool_name: str) -> None:
        """Record a successful guard check (call it after check() returns None)"""
        self._call_counts[tool_name] = self._call_counts.get(tool_name, 0) + 1
        self._total_calls += 1
    
    def reset(self) -> None:
        self._call_counts = {}
        self._total_calls = 0
        self.loop_detector.reset()

