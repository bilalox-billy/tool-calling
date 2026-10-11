# src/level2/registry.py
"""
Tool registry: central store for all tools.
Handles: schema injection, allowlisting, dispatch.
"""
from pydantic import ValidationError
from .tools import CalculatorTool, WeatherTool, DateTool


class ToolNotFoundError(Exception):
    pass


class ToolRegistry:
    def __init__(self):
        self._tools: dict = {}

    def register(self, tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str):
        if name not in self._tools:
            raise ToolNotFoundError(f"Unknown tool: '{name}'. Available: {list(self._tools)}")
        return self._tools[name]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def get_schemas(self) -> list[dict]:
        """Return all tool schemas for injection into Ollama request."""
        return [tool.get_ollama_schema() for tool in self._tools.values()]

    def execute(self, tool_name: str, raw_arguments: dict) -> str:
        """
        Safe execution: validate with Pydantic, then execute.
        Always returns a string (never raises).
        """
        # Allowlist check
        if tool_name not in self:
            return f"Error: Unknown tool '{tool_name}'"

        tool = self.get(tool_name)

        # Pydantic validation
        try:
            validated = tool.input_schema.model_validate(raw_arguments)
        except ValidationError as e:
            errors = "; ".join(
                f"{'.'.join(str(l) for l in err['loc'])}: {err['msg']}"
                for err in e.errors()
            )
            return f"Error: Invalid arguments for {tool_name}: {errors}"

        # Execute with exception safety
        try:
            return tool.execute(validated)
        except Exception as e:
            return f"Error: Tool '{tool_name}' execution failed: {type(e).__name__}: {e}"


def make_default_registry() -> ToolRegistry:
    """Create a registry with all default tools."""
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(WeatherTool())
    registry.register(DateTool())
    return registry
