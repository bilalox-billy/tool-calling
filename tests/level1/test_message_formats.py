# tests/level1/test_message_formats.py
"""
Tests for Level 1: message format correctness.
These tests don't require Ollama — they test your understanding of the format.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestMessageRoles:
    """Test that you understand the 4 message roles."""

    def test_system_role_accepted(self):
        msg = {"role": "system", "content": "You are helpful."}
        assert msg["role"] == "system"
        assert "content" in msg

    def test_user_role_accepted(self):
        msg = {"role": "user", "content": "What is 2 + 2?"}
        assert msg["role"] == "user"

    def test_assistant_role_with_tool_calls(self):
        msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "calculate", "arguments": {"expression": "2+2"}}}
            ]
        }
        assert msg["role"] == "assistant"
        assert msg["tool_calls"] is not None
        assert len(msg["tool_calls"]) == 1

    def test_tool_role_is_valid(self):
        msg = {"role": "tool", "content": "4.0"}
        assert msg["role"] == "tool"


class TestToolSchemaFormat:
    """Test that tool schemas are structured correctly."""

    def test_tool_schema_has_required_fields(self):
        schema = {
            "type": "function",
            "function": {
                "name": "my_tool",
                "description": "Does something useful",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "The input"}
                    },
                    "required": ["input"]
                }
            }
        }
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]
        assert "required" in schema["function"]["parameters"]

    def test_parameters_has_object_type(self):
        schema = {"type": "object", "properties": {}, "required": []}
        assert schema["type"] == "object"

    def test_tool_schema_description_is_string(self):
        schema = {"type": "function", "function": {"name": "x", "description": "desc"}}
        assert isinstance(schema["function"]["description"], str)
        assert len(schema["function"]["description"]) > 0


class TestResponseDetection:
    """Test logic for detecting tool calls vs text responses."""

    def detect_response_type(self, message: dict) -> str:
        if message.get("tool_calls"):
            return "tool_call"
        elif message.get("content"):
            return "text"
        else:
            return "empty"

    def test_detects_tool_call(self):
        msg = {"role": "assistant", "content": "", "tool_calls": [{"function": {}}]}
        assert self.detect_response_type(msg) == "tool_call"

    def test_detects_text_response(self):
        msg = {"role": "assistant", "content": "The answer is 42.", "tool_calls": None}
        assert self.detect_response_type(msg) == "text"

    def test_detects_empty_response(self):
        msg = {"role": "assistant", "content": "", "tool_calls": None}
        assert self.detect_response_type(msg) == "empty"

    def test_tool_call_takes_priority(self):
        # If both content and tool_calls, tool_calls wins
        msg = {"role": "assistant", "content": "I'll calculate that", "tool_calls": [{"function": {}}]}
        assert self.detect_response_type(msg) == "tool_call"
