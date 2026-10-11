# src/level2/mock_adapter.py
"""
MockAdapter: scripted responses for testing the agent loop without Ollama.
"""
from dataclasses import dataclass


@dataclass
class ScriptedResponse:
    """One scripted response in the mock sequence."""
    tool_name: str | None = None
    arguments: dict | None = None
    content: str | None = None

    def to_ollama_message(self) -> dict:
        if self.tool_name:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": self.tool_name, "arguments": self.arguments or {}}}
                ]
            }
        return {"role": "assistant", "content": self.content or "", "tool_calls": None}


class MockAgentLoop:
    """
    Test-only agent loop that uses scripted responses instead of Ollama.
    Identical logic to AgentLoop — only the LLM call is replaced.
    """

    def __init__(self, registry, responses: list[ScriptedResponse], max_iterations: int = 10):
        self.registry = registry
        self.responses = responses
        self.max_iterations = max_iterations
        self._call_index = 0

    def run(self, user_message: str):
        from src.level2.agent import AgentResult, ToolCallRecord
        result = AgentResult(final_answer="", termination_reason="")
        history = [{"role": "user", "content": user_message}]

        for iteration in range(self.max_iterations):
            result.iterations = iteration + 1

            if self._call_index >= len(self.responses):
                result.final_answer = "Mock: no more scripted responses"
                result.termination_reason = "error"
                return result

            scripted = self.responses[self._call_index]
            self._call_index += 1
            msg = scripted.to_ollama_message()

            if msg.get("tool_calls"):
                tc = msg["tool_calls"][0]["function"]
                tool_name = tc["name"]
                arguments = tc["arguments"]
                tool_result = self.registry.execute(tool_name, arguments)
                result.tool_calls_made.append(
                    ToolCallRecord(tool_name=tool_name, arguments=arguments,
                                  result=tool_result, success=not tool_result.startswith("Error:"),
                                  iteration=iteration + 1)
                )
                history.append(msg)
                history.append({"role": "tool", "content": tool_result})
            elif msg.get("content"):
                result.final_answer = msg["content"]
                result.termination_reason = "answer"
                return result

        result.final_answer = "Max iterations reached"
        result.termination_reason = "max_iterations"
        return result
