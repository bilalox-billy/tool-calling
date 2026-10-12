# src/level3/evaluator.py
"""
Evaluation harness for tool-calling systems.
Measures: tool selection accuracy, argument correctness, execution success.
"""
import time
import json
from dataclasses import dataclass, field
from level2.mock_adapter import MockAgentLoop, ScriptedResponse
from level2.registry import ToolRegistry


@dataclass
class EvalCase:
    id: str
    user_message: str
    expected_tool: str              # "" means no tool should be called
    expected_args_subset: dict      # these key-values must appear in actual args
    expected_answer_keywords: list[str]


@dataclass
class EvalResult:
    case_id: str
    tool_selection_correct: bool
    args_correct: bool
    execution_success: bool
    answer_keywords_present: bool
    latency_ms: float
    actual_tool: str
    actual_args: dict
    actual_answer: str
    error: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.tool_selection_correct and
            self.args_correct and
            self.execution_success and
            self.answer_keywords_present
        )


@dataclass
class EvalMetrics:
    total: int = 0
    passed: int = 0
    tool_selection_accuracy: float = 0.0
    args_correctness_rate: float = 0.0
    execution_success_rate: float = 0.0
    answer_keyword_hit_rate: float = 0.0
    avg_latency_ms: float = 0.0


def evaluate_single(
    case: EvalCase,
    registry: ToolRegistry,
    scripted_responses: list[ScriptedResponse],
) -> EvalResult:
    """Evaluate one test case using scripted responses."""
    start = time.perf_counter()

    loop = MockAgentLoop(registry=registry, responses=scripted_responses)
    agent_result = loop.run(case.user_message)

    latency = (time.perf_counter() - start) * 1000

    # What tool was actually called?
    actual_tool = ""
    actual_args = {}
    execution_success = True

    if agent_result.tool_calls_made:
        first_call = agent_result.tool_calls_made[0]
        actual_tool = first_call.tool_name
        actual_args = first_call.arguments
        execution_success = first_call.success

    # Tool selection correct?
    tool_selection_correct = actual_tool == case.expected_tool

    # Arguments correct? (subset check)
    args_correct = True
    if case.expected_args_subset:
        for key, expected_value in case.expected_args_subset.items():
            actual_value = str(actual_args.get(key, ""))
            if str(expected_value) not in actual_value:
                args_correct = False
                break

    # Answer keywords present?
    answer_lower = agent_result.final_answer.lower()
    keywords_present = all(
        kw.lower() in answer_lower
        for kw in case.expected_answer_keywords
    )

    return EvalResult(
        case_id=case.id,
        tool_selection_correct=tool_selection_correct,
        args_correct=args_correct,
        execution_success=execution_success,
        answer_keywords_present=keywords_present,
        latency_ms=latency,
        actual_tool=actual_tool,
        actual_args=actual_args,
        actual_answer=agent_result.final_answer,
    )


def compute_metrics(results: list[EvalResult]) -> EvalMetrics:
    n = len(results)
    if n == 0:
        return EvalMetrics()
    return EvalMetrics(
        total=n,
        passed=sum(r.passed for r in results),
        tool_selection_accuracy=sum(r.tool_selection_correct for r in results) / n,
        args_correctness_rate=sum(r.args_correct for r in results) / n,
        execution_success_rate=sum(r.execution_success for r in results) / n,
        answer_keyword_hit_rate=sum(r.answer_keywords_present for r in results) / n,
        avg_latency_ms=sum(r.latency_ms for r in results) / n,
    )
