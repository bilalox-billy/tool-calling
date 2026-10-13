# src/level2/agent.py
"""
The agent loop — bounded multi-turn tool execution.

This is the core of any tool-calling system:
  1. Send messages to LLM
  2. If tool call → execute → append → loop
  3. If text → return
  4. If max_iterations → stop
"""

import httpx
import logging
from dataclasses import dataclass, field

from level3.guard import ToolGuard
from level3.executor import SafeToolExecutor
from level3.security import check_user_message, sanitize_tool_result

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"

@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    result: str
    success: bool
    iteration: int


@dataclass
class AgentResult:                                         # BUG 1 FIX: renamed + consistent casing
    final_message: str
    tool_calls_made: list[ToolCallRecord] = field(default_factory=list)
    iteration: int = 0
    termination_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


class AgentLoop:
    """
    Bounded tool-calling agent loop with full Level 3 safety wired in:
      - check_user_message()    before the first LLM call
      - SafeToolExecutor        replaces registry.execute() (guard + validate + timeout)
      - sanitize_tool_result()  before each tool result is fed back to the LLM

    Usage:
        registry = make_default_registry()
        agent = AgentLoop(registry=registry)
        result = agent.run("What is 6 * 7?")
        print(result.final_message)
    """

    def __init__(
        self,
        registry,
        model: str = "qwen2.5:7b",
        max_iterations: int = 10,
        system_prompt: str | None = None,
        guard: ToolGuard | None = None,
    ):
        self.registry = registry
        self.model = model
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt or (
            "You are a helpful assistant with access to tools. "
            "Use tools when calculations, weather, or date information is needed. "
            "Always use tools for calculations rather than computing mentally."
        )
        # BUG 2 FIX: use SafeToolExecutor instead of registry.execute() directly
        _guard = guard or ToolGuard()
        self.executor = SafeToolExecutor(registry=registry, guard=_guard)

    def run(self, user_message: str) -> AgentResult:
        """Run the agent loop for a single user message."""

        result = AgentResult(final_message="", termination_reason="")

        # ── BEFORE LLM ── security: scan user message ──────────────
        injection_warnings = check_user_message(user_message)
        if injection_warnings:
            logger.warning(f"Suspicious user input detected: {injection_warnings}")

        history = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

        for iteration in range(self.max_iterations):
            result.iteration = iteration + 1

            # ── LLM CALL ───────────────────────────────────────────
            response_data = self._call_ollama(history)
            if response_data is None:
                result.final_message = "Error: Could not reach Ollama. Is it running?"
                result.termination_reason = "error"
                return result

            msg = response_data.get("message", {})
            result.prompt_tokens    += response_data.get("prompt_eval_count", 0)
            result.completion_tokens += response_data.get("eval_count", 0)

            tool_calls = msg.get("tool_calls")
            content    = msg.get("content", "")

            if tool_calls:
                # Execute the first tool call via SafeToolExecutor (BUG 2 FIX)
                tc        = tool_calls[0]["function"]
                tool_name = tc.get("name", "")
                arguments = tc.get("arguments", {})

                logger.info(f"[iter {iteration+1}] Tool call: {tool_name}({arguments})")

                # ── BETWEEN LLM CALLS ── guard + validate + timeout
                tool_result, success = self.executor.execute(tool_name, arguments)

                # ── BETWEEN LLM CALLS ── sanitize before feeding back
                safe_result = sanitize_tool_result(tool_result)

                record = ToolCallRecord(
                    tool_name=tool_name,
                    arguments=arguments,
                    result=safe_result,
                    success=success,
                    iteration=iteration + 1,
                )
                result.tool_calls_made.append(record)
                logger.info(f"[iter {iteration+1}] Tool result: {safe_result[:100]}")

                history.append(msg)
                history.append({"role": "tool", "content": safe_result})

            elif content:
                # Final text answer
                result.final_message = content
                result.termination_reason = "answer"
                logger.info(f"[iter {iteration+1}] Final answer: {content[:100]}")
                return result

            else:
                logger.warning(f"[iter {iteration+1}] Empty response from model")
                result.final_message = "I could not generate a response. Please try rephrasing."
                result.termination_reason = "error"
                return result

        # Max iterations reached
        result.final_message = (
            f"I was unable to complete the task within {self.max_iterations} steps. "
            f"Tools used: {[r.tool_name for r in result.tool_calls_made]}"
        )
        result.termination_reason = "max_iterations"
        return result
    
    def _call_ollama(self, history: list[dict]) -> dict | None:
        """Make a single call to the Ollama API."""
        try:
            response = httpx.post(
                OLLAMA_URL,
                json={
                    "model": self.model,
                    "messages": history,
                    "tools": self.registry.get_schemas(),
                    "stream": False,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama")
            return None
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return None









            



