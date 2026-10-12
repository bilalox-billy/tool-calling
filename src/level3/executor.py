# src/level3/executor.py
"""
SafeToolExecutor: validation + guard checks + timeout + error handling.
"""
import logging
import time
import threading
from pydantic import ValidationError
from .guard import ToolGuard

logger = logging.getLogger(__name__)


class SafeToolExecutor:
    """
    Execute tools safely:
    1. Guard check (allowlist, limits, loop detection)
    2. Pydantic argument validation
    3. Timeout enforcement
    4. Exception catching
    """

    def __init__(self, registry, guard: ToolGuard, timeout_seconds: float = 10.0):
        self.registry = registry
        self.guard = guard
        self.timeout = timeout_seconds

    def execute(self, tool_name: str, raw_arguments: dict) -> tuple[str, bool]:
        """
        Returns (result_string, success_bool).
        Never raises exceptions.
        """
        start = time.perf_counter()

        # Step 1: Guard check
        guard_error = self.guard.check(tool_name, raw_arguments)
        if guard_error:
            logger.warning(f"Guard blocked {tool_name}: {guard_error}")
            return guard_error, False

        # Step 2: Get tool
        if tool_name not in self.registry:
            result = f"Error: Unknown tool '{tool_name}'"
            logger.warning(result)
            return result, False

        tool = self.registry.get(tool_name)

        # Step 3: Validate arguments
        try:
            validated = tool.input_schema.model_validate(raw_arguments)
        except ValidationError as e:
            errors = "; ".join(
                f"{'.'.join(str(l) for l in err['loc'])}: {err['msg']}"
                for err in e.errors()
            )
            result = f"Error: Invalid arguments: {errors}"
            logger.warning(f"{tool_name} validation failed: {errors}")
            return result, False

        # Step 4: Execute with timeout
        result_container = [None]
        error_container = [None]

        def run_tool():
            try:
                result_container[0] = tool.execute(validated)
            except Exception as e:
                error_container[0] = e

        thread = threading.Thread(target=run_tool, daemon=True)
        thread.start()
        thread.join(timeout=self.timeout)

        if thread.is_alive():
            result = f"Error: Tool '{tool_name}' timed out after {self.timeout}s"
            logger.error(result)
            return result, False

        if error_container[0] is not None:
            result = f"Error: Tool execution failed: {type(error_container[0]).__name__}: {error_container[0]}"
            logger.error(f"{tool_name} raised: {error_container[0]}")
            return result, False

        # Step 5: Record successful call
        self.guard.record(tool_name)
        latency = (time.perf_counter() - start) * 1000
        result = result_container[0]
        success = not str(result).startswith("Error:")
        logger.info(f"{tool_name} completed in {latency:.1f}ms: {str(result)[:80]}")
        return result, success
