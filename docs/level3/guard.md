# `guard.py` — Abuse Prevention

## Purpose

An LLM can get stuck calling the same tool forever, or a malicious prompt can attempt to invoke hundreds of tools in one session. `guard.py` is the **bouncer** — it decides whether a tool call is allowed *before* any code runs.

It contains two classes that work together:

```
LoopDetector  →  detects repeated identical calls
ToolGuard     →  combines allowlist + rate limits + LoopDetector into one gate
```

---

## `class LoopDetector`

Detects when the model is calling the same tool with the same arguments repeatedly.

### Constructor

```python
LoopDetector(max_repeat: int = 3)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_repeat` | `int` | `3` | Number of identical calls allowed before flagging a loop |

**Internal state:**
- `_history: list[str]` — ordered log of call fingerprints

---

### `_key(tool_name, arguments) → str`

**Why we need it:** Stores a compact, deterministic fingerprint for each (tool, args) pair so we can count repetitions without storing full argument dicts.

**How it works:** Serializes `arguments` to sorted JSON, hashes it with MD5, and prepends the tool name.

```
Input:
    tool_name  = "calculate"
    arguments  = {"expression": "12*8", "precision": 2}

Output:
    "calculate:a1b2c3d4"
    ─────────────────────
    tool name + first 8 hex chars of MD5(sorted JSON)
```

> **Note:** Sorting keys ensures `{"a":1,"b":2}` and `{"b":2,"a":1}` produce the same fingerprint.

---

### `is_looping(tool_name, arguments) → bool`

**Why we need it:** The main public check. Returns `True` the instant a call fingerprint has been seen `max_repeat` times. Also **records** the call to history in the same step.

| Parameter | Type | Description |
|---|---|---|
| `tool_name` | `str` | Name of the tool being called |
| `arguments` | `dict` | Raw arguments dict from the LLM |

**Returns:** `True` if looping, `False` if safe.

**Example — loop triggered on 3rd repeat:**

```python
detector = LoopDetector(max_repeat=3)

detector.is_looping("calculate", {"expression": "12*8"})  # → False (seen 0 times before)
detector.is_looping("calculate", {"expression": "12*8"})  # → False (seen 1 time before)
detector.is_looping("calculate", {"expression": "12*8"})  # → False (seen 2 times before)
detector.is_looping("calculate", {"expression": "12*8"})  # → True  ← BLOCKED
```

**Example — different args are not a loop:**

```python
detector.is_looping("calculate", {"expression": "3+3"})   # → False (different fingerprint)
```

---

### `reset() → None`

**Why we need it:** Clears the history between agent runs so one session's calls don't affect the next.

```python
detector.reset()
# _history is now []
```

---

## `class ToolGuard`

A single safety checkpoint combining **all** guard rules into one `.check()` call. The executor calls this before every tool execution.

### Constructor

```python
ToolGuard(
    allowed_tools: set[str] | None = None,
    max_calls_per_tool: int = 5,
    max_total_calls: int = 20,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `allowed_tools` | `set[str] \| None` | `None` | Explicit allowlist of permitted tool names. `None` = allow all registered tools |
| `max_calls_per_tool` | `int` | `5` | Maximum times any single tool can be called per run |
| `max_total_calls` | `int` | `20` | Maximum total tool calls across all tools per run |

**Internal state:**
- `_call_counts: dict[str, int]` — per-tool call counter
- `_total_calls: int` — global call counter
- `loop_detector: LoopDetector` — embedded loop detector instance

---

### `check(tool_name, arguments) → str | None`

**Why we need it:** One gate that enforces all rules in priority order. Returns an error string if the call should be blocked, or `None` if it is safe to proceed.

**Checks performed (in order):**

| # | Check | Error returned if blocked |
|---|---|---|
| 1 | Allowlist | `"Error: Tool 'X' is not permitted"` |
| 2 | Total call limit | `"Error: Maximum total tool calls (N) reached"` |
| 3 | Per-tool call limit | `"Error: Tool 'X' has been called too many times (N max)"` |
| 4 | Loop detection | `"Error: Loop detected — tool 'X' called repeatedly with identical arguments"` |

**Example — all passing:**

```python
guard = ToolGuard(allowed_tools={"calculate", "get_weather"}, max_calls_per_tool=5)
guard.check("calculate", {"expression": "12*8"})  # → None  (safe to proceed)
```

**Example — blocked by allowlist:**

```python
guard.check("delete_files", {})
# → "Error: Tool 'delete_files' is not permitted"
```

**Example — blocked by per-tool limit:**

```python
# After "calculate" has been called 5 times already:
guard.check("calculate", {"expression": "1+1"})
# → "Error: Tool 'calculate' has been called too many times (5 max)"
```

---

### `record(tool_name) → None`

**Why we need it:** Increments counters **after** a successful execution. Deliberately separate from `check()` — a tool that passes the guard but then fails at runtime should not count against the limit.

```python
guard.record("calculate")
# _call_counts = {"calculate": 1}
# _total_calls = 1
```

> **Important:** Always call `record()` only after `check()` returns `None` **and** the tool executes successfully. `SafeToolExecutor` handles this automatically.

---

### `reset() → None`

**Why we need it:** Resets all counters and loop history between runs. Essential if you reuse the same `ToolGuard` instance across multiple conversations.

```python
guard.reset()
# _call_counts = {}
# _total_calls = 0
# loop_detector._history = []
```

---

## Usage Pattern

```python
guard = ToolGuard(
    allowed_tools={"calculator", "get_weather", "get_date"},
    max_calls_per_tool=5,
    max_total_calls=20,
)

# Before each tool call:
error = guard.check(tool_name, arguments)
if error:
    return error, False          # blocked — return error to agent

result = run_the_tool(...)       # execute the tool

guard.record(tool_name)          # only record if execution succeeded
```

In practice, `SafeToolExecutor.execute()` wraps this entire pattern for you.
