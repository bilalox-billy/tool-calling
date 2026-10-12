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
    Detect when the model is looping (calling the same tool with the same arguments over and over).
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
        count = self.history.count(key)
        self._history.append(key)
        return count >= self.max_repeat
    
    def reset(self) -> None:
        self._history = []

    