# `evaluator.py` — Offline Test Harness & Metrics

## Purpose

How do you know if your agent is actually working correctly? You can't just eyeball chat logs. `evaluator.py` provides a **systematic, repeatable way to measure agent quality** across four dimensions — without calling a real LLM.

It answers questions like:
- Did the model pick the right tool for this question?
- Did it pass the correct arguments?
- Did the tool execute successfully?
- Does the final answer contain the expected information?

```
EvalCase (test input + expected behavior)
        │
        ▼
evaluate_single()  ← runs agent with scripted (mock) LLM responses
        │
        ▼
EvalResult (what actually happened, pass/fail per dimension)
        │
        ▼
compute_metrics()  ← aggregates results into accuracy rates
        │
        ▼
EvalMetrics (tool_selection_accuracy, args_correctness_rate, ...)
```

**Key design:** Uses a **mock agent** with scripted responses — the evaluator never calls a real LLM. This makes tests fast, free, deterministic, and runnable in CI.

---

## Data Classes

---

### `@dataclass EvalCase`

**Why we need it:** Represents a single test case — what the user says, what tool the agent *should* call, and what the final answer *should* contain. This is your ground truth.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique identifier for this test case |
| `user_message` | `str` | The user's input message |
| `expected_tool` | `str` | Tool name the agent should call. `""` = no tool expected |
| `expected_args_subset` | `dict` | Key-value pairs that must appear in the actual arguments (subset match, not exact) |
| `expected_answer_keywords` | `list[str]` | Words that must appear in the final answer (case-insensitive) |

**Example:**
```python
EvalCase(
    id="calc-multiply-01",
    user_message="What is 12 times 8?",
    expected_tool="calculator",
    expected_args_subset={"expression": "12"},   # "12" must appear somewhere in the expression arg
    expected_answer_keywords=["96"],             # "96" must appear in the final answer
)

EvalCase(
    id="no-tool-capital-01",
    user_message="What is the capital of France?",
    expected_tool="",                             # no tool should be called
    expected_args_subset={},
    expected_answer_keywords=["paris"],
)
```

---

### `@dataclass EvalResult`

**Why we need it:** Stores what *actually happened* when the agent ran one `EvalCase`, broken down into four independent pass/fail dimensions. More informative than a single pass/fail — you can see exactly *which* aspect failed.

| Field | Type | Description |
|---|---|---|
| `case_id` | `str` | ID of the `EvalCase` this result corresponds to |
| `tool_selection_correct` | `bool` | Did the agent call the right tool (or correctly call none)? |
| `args_correct` | `bool` | Did the actual arguments contain all expected key-value pairs? |
| `execution_success` | `bool` | Did the tool execute without error? |
| `answer_keywords_present` | `bool` | Does the final answer contain all expected keywords? |
| `latency_ms` | `float` | Wall-clock time for the full agent run in milliseconds |
| `actual_tool` | `str` | The tool name actually called (empty string if none) |
| `actual_args` | `dict` | The actual arguments passed to the tool |
| `actual_answer` | `str` | The final answer text from the agent |
| `error` | `str \| None` | Error message if something went wrong at the harness level |

#### Property: `passed → bool`

**Why we need it:** A single boolean that is `True` only if **all four** dimensions passed. Used by `compute_metrics()` to count overall test pass rate.

```python
result.passed
# True only if:
#   tool_selection_correct AND
#   args_correct AND
#   execution_success AND
#   answer_keywords_present
```

---

### `@dataclass EvalMetrics`

**Why we need it:** Aggregates results across a full test suite into rates (0.0–1.0). Makes it easy to compare quality across model versions, tool changes, or prompt changes.

| Field | Type | Description |
|---|---|---|
| `total` | `int` | Total number of test cases evaluated |
| `passed` | `int` | Number of cases where `.passed == True` |
| `tool_selection_accuracy` | `float` | Fraction of cases where the correct tool was chosen |
| `args_correctness_rate` | `float` | Fraction of cases where arguments matched the expected subset |
| `execution_success_rate` | `float` | Fraction of cases where tool execution succeeded |
| `answer_keyword_hit_rate` | `float` | Fraction of cases where all expected keywords appeared in the answer |
| `avg_latency_ms` | `float` | Average wall-clock time per case in milliseconds |

**Example values:**
```python
EvalMetrics(
    total=10,
    passed=8,
    tool_selection_accuracy=0.9,    # 90% — picked the right tool 9/10 times
    args_correctness_rate=0.85,     # 85% — correct args 8.5/10 times
    execution_success_rate=1.0,     # 100% — all tools executed without error
    answer_keyword_hit_rate=0.8,    # 80% — expected keywords in answer 8/10 times
    avg_latency_ms=142.3,
)
```

---

## Functions

---

### `evaluate_single(case, registry, scripted_responses) → EvalResult`

**Why we need it:** Runs the agent on one `EvalCase` and returns a detailed `EvalResult`. Uses a mock agent with scripted responses so no real LLM is needed.

| Parameter | Type | Description |
|---|---|---|
| `case` | `EvalCase` | The test case to evaluate |
| `registry` | `ToolRegistry` | The tool registry (real tools, real execution) |
| `scripted_responses` | `list[ScriptedResponse]` | Pre-scripted LLM responses for this test case |

**Returns:** `EvalResult`

**How the evaluation logic works:**

```
1. Run MockAgentLoop with scripted_responses
        ↓
2. Extract first tool call made (if any)
        ↓
3. tool_selection_correct = (actual_tool == case.expected_tool)
        ↓
4. args_correct = all expected_args_subset key-values appear in actual_args
        ↓
5. answer_keywords_present = all keywords appear (case-insensitive) in final answer
```

**Important — subset matching for args:**
`expected_args_subset` uses a **substring check**, not an exact match:
```python
expected_args_subset = {"expression": "12"}
actual_args = {"expression": "12 * 8", "precision": 2}
# → args_correct = True  (because "12" appears in "12 * 8")
```
This is intentional — LLMs may format expressions slightly differently and still be correct.

**Example:**
```python
case = EvalCase(
    id="calc-01",
    user_message="What is 6 * 7?",
    expected_tool="calculator",
    expected_args_subset={"expression": "6"},
    expected_answer_keywords=["42"],
)

scripted = [
    ScriptedResponse(tool_name="calculator", arguments={"expression": "6 * 7"}),
    ScriptedResponse(content="The answer is 42."),
]

result = evaluate_single(case, registry, scripted)
# EvalResult(
#     case_id="calc-01",
#     tool_selection_correct=True,
#     args_correct=True,
#     execution_success=True,
#     answer_keywords_present=True,
#     latency_ms=12.4,
#     actual_tool="calculator",
#     actual_args={"expression": "6 * 7"},
#     actual_answer="The answer is 42.",
# )
# result.passed → True
```

---

### `compute_metrics(results) → EvalMetrics`

**Why we need it:** Aggregates a list of `EvalResult` objects into summary statistics. Gives you the big picture across your entire test suite.

| Parameter | Type | Description |
|---|---|---|
| `results` | `list[EvalResult]` | All results from your test suite |

**Returns:** `EvalMetrics`

**Handles edge case:** If `results` is empty, returns a zeroed `EvalMetrics()` instead of dividing by zero.

**Example:**
```python
results = [result1, result2, result3, ...]  # from evaluate_single()

metrics = compute_metrics(results)
print(f"Pass rate:              {metrics.passed}/{metrics.total}")
print(f"Tool selection:         {metrics.tool_selection_accuracy:.0%}")
print(f"Argument correctness:   {metrics.args_correctness_rate:.0%}")
print(f"Execution success:      {metrics.execution_success_rate:.0%}")
print(f"Answer keyword hit:     {metrics.answer_keyword_hit_rate:.0%}")
print(f"Avg latency:            {metrics.avg_latency_ms:.1f}ms")

# Pass rate:              8/10
# Tool selection:         90%
# Argument correctness:   85%
# Execution success:      100%
# Answer keyword hit:     80%
# Avg latency:            142.3ms
```

---

## Full Usage Pattern

```python
from level2.registry import make_default_registry
from level3.evaluator import EvalCase, evaluate_single, compute_metrics

registry = make_default_registry()

# 1. Define your test suite
test_suite = [
    EvalCase(
        id="calc-01",
        user_message="What is 6 * 7?",
        expected_tool="calculator",
        expected_args_subset={"expression": "6"},
        expected_answer_keywords=["42"],
    ),
    EvalCase(
        id="no-tool-01",
        user_message="What is the capital of France?",
        expected_tool="",
        expected_args_subset={},
        expected_answer_keywords=["paris"],
    ),
]

# 2. Evaluate each case
results = []
for case in test_suite:
    scripted = get_scripted_responses(case)   # your mock responses
    result = evaluate_single(case, registry, scripted)
    results.append(result)
    status = "✅ PASS" if result.passed else "❌ FAIL"
    print(f"{status} [{case.id}]")

# 3. Compute aggregate metrics
metrics = compute_metrics(results)
print(f"\nOverall pass rate: {metrics.passed}/{metrics.total}")
print(f"Tool selection accuracy: {metrics.tool_selection_accuracy:.0%}")
```

---

## Why This Matters

Without an evaluator you are flying blind — you only know if the agent works by manually chatting with it. The evaluator lets you:

| Use case | How evaluator helps |
|---|---|
| **Regression testing** | Run the suite after every code change to catch breakage |
| **Model comparison** | Compare `qwen2.5:7b` vs `llama3.2` on identical test cases |
| **Prompt tuning** | Measure whether a system prompt change improved tool selection accuracy |
| **CI/CD integration** | Fail the build if `tool_selection_accuracy` drops below 0.9 |
