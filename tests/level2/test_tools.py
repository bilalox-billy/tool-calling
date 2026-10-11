# tests/level2/test_tools.py
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from pydantic import ValidationError
from level2.tools import CalculatorTool, WeatherTool, DateTool, CalculatorInput, WeatherInput, DateInput
from level2.registry import ToolRegistry, ToolNotFoundError, make_default_registry
from level2.mock_adapter import MockAgentLoop, ScriptedResponse


# ── Calculator Tests ───────────────────────────────────────────────────────────

class TestCalculatorTool:
    @pytest.fixture
    def tool(self):
        return CalculatorTool()

    def test_basic_addition(self, tool):
        inp = CalculatorInput(expression="2 + 2")
        assert tool.execute(inp) == "4.0"

    def test_multiplication(self, tool):
        inp = CalculatorInput(expression="12 * 8", precision=0)
        assert tool.execute(inp) == "96"

    def test_division(self, tool):
        inp = CalculatorInput(expression="144 / 12")
        assert tool.execute(inp) == "12.0"

    def test_division_by_zero(self, tool):
        inp = CalculatorInput(expression="5 / 0")
        result = tool.execute(inp)
        assert "Error" in result
        assert "zero" in result.lower()

    def test_unsafe_expression_rejected(self, tool):
        inp = CalculatorInput(expression="__import__('os').system('ls')")
        result = tool.execute(inp)
        assert "Error" in result

    def test_precision_applied(self, tool):
        inp = CalculatorInput(expression="1 / 3", precision=4)
        assert tool.execute(inp) == "0.3333"

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            CalculatorInput(expression="2+2", injected_field="evil")


class TestWeatherTool:
    @pytest.fixture
    def tool(self):
        return WeatherTool()

    def test_known_city_celsius(self, tool):
        import json
        inp = WeatherInput(city="Paris", unit="celsius")
        result = json.loads(tool.execute(inp))
        assert result["city"] == "Paris"
        assert isinstance(result["temperature"], float)
        assert result["unit"] == "°C"

    def test_fahrenheit_conversion(self, tool):
        import json
        inp = WeatherInput(city="paris", unit="fahrenheit")
        result = json.loads(tool.execute(inp))
        # Paris is 22°C = 71.6°F
        assert result["temperature"] == pytest.approx(71.6, abs=0.1)
        assert result["unit"] == "°F"

    def test_unit_must_be_literal(self):
        with pytest.raises(ValidationError):
            WeatherInput(city="Paris", unit="kelvin")


class TestDateTool:
    @pytest.fixture
    def tool(self):
        return DateTool()

    def test_today_returns_string(self, tool):
        inp = DateInput(operation="today")
        result = tool.execute(inp)
        assert isinstance(result, str)
        assert len(result) > 5

    def test_invalid_date_format(self, tool):
        inp = DateInput(operation="days_until", target_date="not-a-date")
        result = tool.execute(inp)
        assert "Error" in result

    def test_days_since_requires_date(self, tool):
        inp = DateInput(operation="days_since", target_date=None)
        result = tool.execute(inp)
        assert "Error" in result or "required" in result

    def test_day_of_week_known_date(self, tool):
        inp = DateInput(operation="day_of_week", target_date="2024-01-01")
        result = tool.execute(inp)
        assert result == "Monday"


# ── Registry Tests ─────────────────────────────────────────────────────────────

class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        return make_default_registry()

    def test_contains_default_tools(self, registry):
        assert "calculate" in registry
        assert "get_weather" in registry
        assert "get_date" in registry

    def test_len(self, registry):
        assert len(registry) == 3

    def test_unknown_tool_returns_error(self, registry):
        result = registry.execute("delete_everything", {})
        assert "Error" in result
        assert "Unknown tool" in result

    def test_invalid_args_returns_error(self, registry):
        result = registry.execute("calculate", {"expression": 99999})
        # 99999 gets coerced to "99999" which is valid... but test the error path
        # Try truly invalid: missing required field
        result = registry.execute("calculate", {})
        assert "Error" in result

    def test_get_schemas_returns_all(self, registry):
        schemas = registry.get_schemas()
        assert len(schemas) == 3
        names = [s["function"]["name"] for s in schemas]
        assert "calculate" in names

    def test_execution_safe_from_exceptions(self, registry):
        """Even if tool raises internally, registry catches it."""
        # Simulate by calling with edge case
        result = registry.execute("calculate", {"expression": "0 / 0"})
        assert isinstance(result, str)


# ── Agent Loop Tests (no Ollama) ───────────────────────────────────────────────

class TestMockAgentLoop:
    @pytest.fixture
    def registry(self):
        return make_default_registry()

    def test_single_tool_call_then_answer(self, registry):
        responses = [
            ScriptedResponse(tool_name="calculate", arguments={"expression": "6 * 7"}),
            ScriptedResponse(content="6 times 7 equals 42."),
        ]
        loop = MockAgentLoop(registry=registry, responses=responses)
        result = loop.run("What is 6 times 7?")
        assert result.final_answer == "6 times 7 equals 42."
        assert result.termination_reason == "answer"
        assert len(result.tool_calls_made) == 1
        assert result.tool_calls_made[0].tool_name == "calculate"
        assert result.tool_calls_made[0].result == "42"

    def test_max_iterations_terminates_loop(self, registry):
        responses = [
            ScriptedResponse(tool_name="calculate", arguments={"expression": "1 + 1"})
        ] * 20
        loop = MockAgentLoop(registry=registry, responses=responses, max_iterations=5)
        result = loop.run("Calculate forever")
        assert result.termination_reason == "max_iterations"
        assert result.iterations == 5

    def test_hallucinated_tool_produces_error_result(self, registry):
        responses = [
            ScriptedResponse(tool_name="delete_database", arguments={}),
            ScriptedResponse(content="I could not complete that task."),
        ]
        loop = MockAgentLoop(registry=registry, responses=responses)
        result = loop.run("Delete everything")
        # Hallucinated tool should produce an error result, not crash
        assert len(result.tool_calls_made) == 1
        assert result.tool_calls_made[0].success is False
        assert "Error" in result.tool_calls_made[0].result

    def test_tool_execution_error_does_not_crash_loop(self, registry):
        responses = [
            ScriptedResponse(tool_name="calculate", arguments={"expression": "5 / 0"}),
            ScriptedResponse(content="Division by zero is not possible."),
        ]
        loop = MockAgentLoop(registry=registry, responses=responses)
        result = loop.run("Divide 5 by 0")
        assert result.final_answer == "Division by zero is not possible."
        assert result.tool_calls_made[0].success is False
