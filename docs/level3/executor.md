# `executor.py` — Hardened Tool Execution

## Purpose

Level 2's registry runs tools but can crash, hang, or leak exceptions into the agent loop. `SafeToolExecutor` wraps every tool execution in **four independent layers of defense** so the agent loop can always continue regardless of what goes wrong inside a tool.

```
Incoming call
     │
     ▼
┌─────────────────────────────────────┐
│  Layer 1: Guard check               │ ← allowlist, rate limits, loop detection
│  Layer 2: Registry lookup           │ ← is this tool known?
│  Layer 3: Pydantic validation       │ ← are the arguments correct types/values?
│  Layer 4: Threaded execution        │ ← timeout + exception catching
└─────────────────────────────────────┘
     │
     ▼
(result_string, success_bool)  ← ALWAYS returned, NEVER raises
```

**Core contract:** `execute()` **never raises an exception**. Every possible failure mode returns a descriptive error string with `success=False`.

---

## `class SafeToolExecutor`

### Constructor

```python
SafeToolExecutor(
    registry,                    # ToolRegistry instance
    guard: ToolGuard,            # ToolGuard instance
    timeout_seconds: float = 10.0
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `registry` | `ToolRegistry` | required | The tool registry holding all registered tools |
| `guard` | `ToolGuard` | required | The guard that enforces limits and detects loops |
| `timeout_seconds` | `float` | `10.0` | Max seconds to wait for a tool to finish before aborting |

---

## `execute(tool_name, raw_arguments) → tuple[str, bool]`

**Why we need it:** The single, unified entry point for all tool execution. Replaces calling `registry.execute()` directly. Returns `(result, success)` where result is always a string and success is `True` only if the tool ran without any errors.

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `tool_name` | `str` | Name of the tool to call (as returned by the LLM) |
| `raw_arguments` | `dict` | Raw arguments dict from the LLM, before any validation |

### Returns

`tuple[str, bool]` — `(result_string, success_bool)`

| `success` | Meaning |
|---|---|
| `True` | Tool executed successfully, result is the tool's output |
| `False` | Something went wrong, result is a descriptive error message |

---

### Internal 5-Step Pipeline

#### Step 1 — Guard Check
```python
guard_error = self.guard.check(tool_name, raw_arguments)
if guard_error:
    return guard_error, False
```
Calls `ToolGuard.check()`. If the call is blocked (not allowlisted, rate limit hit, loop detected), returns the error immediately without touching the tool.

#### Step 2 — Registry Lookup
```python
if tool_name not in self.registry:
    return f"Error: Unknown tool '{tool_name}'", False
tool = self.registry.get(tool_name)
```
Verifies the tool name exists. Handles cases where the LLM hallucinates a non-existent tool name.

#### Step 3 — Pydantic Validation
```python
validated = tool.input_schema.model_validate(raw_arguments)
```
Runs the tool's Pydantic schema against the raw arguments. Catches wrong types, missing required fields, values out of range, and extra fields (if `extra="forbid"` is set). Returns a human-readable validation error if it fails.

#### Step 4 — Threaded Execution with Timeout
```python
thread = threading.Thread(target=run_tool, daemon=True)
thread.start()
thread.join(timeout=self.timeout)

if thread.is_alive():
    return f"Error: Tool '{tool_name}' timed out after {self.timeout}s", False
```
Runs the tool in a **daemon thread**. If the thread doesn't finish within `timeout_seconds`, the executor gives up and returns a timeout error. The thread continues in the background but the agent loop is unblocked.

> **Why threading?** Python has no built-in timeout for arbitrary function calls. Running in a daemon thread with `thread.join(timeout=N)` is the standard portable solution.

#### Step 5 — Record & Return
```python
self.guard.record(tool_name)
return result_container[0], success
```
Only records the call to the guard counters after a successful execution (so failed calls don't count against rate limits). Returns the tool's string result.

---

### Input / Output Examples

**Happy path:**
```python
executor.execute("calculate", {"expression": "12 * 8", "precision": 2})
# → ("96.0", True)
```

**Blocked by guard (rate limit):**
```python
# "calculate" has already been called 5 times
executor.execute("calculate", {"expression": "1+1"})
# → ("Error: Tool 'calculate' has been called too many times (5 max)", False)
```

**Unknown tool (LLM hallucinated a tool name):**
```python
executor.execute("send_email", {"to": "boss@company.com"})
# → ("Error: Unknown tool 'send_email'", False)
```

**Invalid arguments (Pydantic validation failure):**
```python
executor.execute("calculate", {"expression": ""})
# → ("Error: Invalid arguments: expression: String should have at least 1 character", False)

executor.execute("get_weather", {"city": "Paris", "unit": "kelvin"})
# → ("Error: Invalid arguments: unit: Input should be 'celsius' or 'fahrenheit'", False)
```

**Tool timed out:**
```python
executor.execute("slow_external_api", {"query": "..."})
# → ("Error: Tool 'slow_external_api' timed out after 10.0s", False)
```

**Runtime exception inside the tool:**
```python
executor.execute("calculate", {"expression": "1/0"})
# → ("Error: Tool execution failed: ZeroDivisionError: division by zero", False)
```

---

## Usage Pattern

```python
from level2.registry import make_default_registry
from level3.guard import ToolGuard
from level3.executor import SafeToolExecutor

registry = make_default_registry()
guard = ToolGuard(allowed_tools={"calculator", "get_weather", "get_date"})
executor = SafeToolExecutor(registry=registry, guard=guard, timeout_seconds=10.0)

# In the agent loop, replace direct registry.execute() with:
result, success = executor.execute(tool_name, arguments)
# result is always a string — safe to inject into conversation history
# success tells you whether to inform the LLM of a failure
```
