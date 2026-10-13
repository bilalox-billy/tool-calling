# Tool Calling with Local LLMs

A hands-on course project that teaches how to build production-grade tool-calling systems with local LLMs using [Ollama](https://ollama.com). Built level by level — from raw HTTP calls to a safe, observable agent loop.

---

## What You Will Learn

- How tool calling actually works (the LLM never runs code — it just describes what to run)
- Why two LLM calls are needed for every tool interaction
- How to build a reusable tool registry with Pydantic validation
- How to protect an agent with guards, rate limiting, and loop detection
- How to defend against prompt injection attacks
- How to measure agent quality with an offline evaluation harness

---

## Project Structure

```
tool-calling/
│
├── src/
│   ├── level1/                  # Raw foundations
│   │   ├── verify_model.py      # Verify your model supports tool calling
│   │   └── message_trace.py     # Trace the full JSON message cycle
│   │
│   ├── level2/                  # Working agent
│   │   ├── tools.py             # Tool definitions with Pydantic schemas
│   │   ├── registry.py          # Central tool registry
│   │   ├── agent.py             # Bounded agent loop (with Level 3 safety)
│   │   └── mock_adapter.py      # Scripted mock LLM for testing
│   │
│   └── level3/                  # Production safety layer
│       ├── guard.py             # Loop detection + rate limiting
│       ├── executor.py          # Safe execution: validate + timeout + catch
│       ├── security.py          # Prompt injection detection + sanitization
│       └── evaluator.py         # Offline evaluation harness + metrics
│
├── notebook/
│   ├── agent.ipynb              # Interactive Level 2 agent demo
│   └── loop.ipynb               # Full end-to-end Level 3 pipeline demo
│
├── tests/
│   ├── level1/                  # Message format tests
│   └── level2/                  # Tool + registry tests
│
└── docs/
    ├── blog-tool-calling-explained.md   # Deep-dive blog post
    └── level3/
        ├── README.md            # Level 3 architecture overview
        ├── guard.md             # Guard documentation
        ├── executor.md          # Executor documentation
        ├── security.md          # Security documentation
        └── evaluator.md         # Evaluator documentation
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | ≥ 3.12 | Uses `str \| None` union syntax |
| [Ollama](https://ollama.com) | latest | Must be running locally |
| Model | `qwen2.5:7b` | Best tool-calling support |

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd tool-calling

# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Pull the model

```bash
ollama pull qwen2.5:7b
```

### 3. Verify Ollama is running

```bash
ollama list
# Should show qwen2.5:7b in the list
```

### 4. Set up environment

```bash
cp .env.example .env
# Edit .env if needed
```

---

## Quick Start

### Verify your model supports tool calling

```bash
python src/level1/verify_model.py
```

Expected output:
```
Tool CALL detected (native tool calling supported)
   Tool name: calculate
   Arguments: {"expression": "144 / 12"}
```

### Trace the full message cycle

```bash
python src/level1/message_trace.py
```

This prints the exact JSON at every step: what goes to the LLM, what comes back, what your code does, and what gets sent on the 2nd call.

### Run the full agent (notebook)

Open `notebook/loop.ipynb` and run all cells. It demonstrates:

| Run | Question | What it tests |
|---|---|---|
| 1 | `"144 divided by 12, then multiplied by 7?"` | Calculator tool + 2-LLM cycle |
| 2 | `"What is the weather in Paris?"` | Weather tool |
| 3 | `"What is the capital of France?"` | No tool — direct LLM answer |
| 4 | Injection attempt | Security detection |
| 5 | Call a blocked tool | Allowlist enforcement |
| 6 | Call a tool 4× with limit=2 | Rate limit enforcement |

---

## Architecture

### The Tool Calling Cycle

Every tool interaction follows this exact pattern — no exceptions:

```
User message
    │
    ▼
[security]  check_user_message()          ← BEFORE 1st LLM call
    │
    ▼
┌─────────────────────────┐
│      1st LLM Call       │  LLM decides: "I need the calculator tool"
└─────────────────────────┘
    │
    ▼ (LLM returned tool_calls JSON)
[guard]     check()                       ← allowlist? rate limit? loop?
[executor]  execute()                     ← validate args + run + timeout
[security]  sanitize_tool_result()        ← truncate + strip HTML + scan
    │
    ▼
┌─────────────────────────┐
│      2nd LLM Call       │  LLM sees result → gives final answer
└─────────────────────────┘
    │
    ▼
Final answer to user
```

> **Key insight:** The LLM never runs code. It produces a JSON description of the call it wants. Your Python code reads that and executes it.

### Levels Overview

#### Level 1 — Raw Foundations
Direct `httpx` calls to Ollama. No abstractions. Shows exactly what is sent and received at the JSON level.

#### Level 2 — Working Agent
- `ToolRegistry` — stores tools, provides schemas, dispatches calls
- `AgentLoop` — bounded loop (max iterations), tracks token usage and tool call history
- Tools: `CalculatorTool`, `WeatherTool`, `DateTool` — each with Pydantic input schemas

#### Level 3 — Production Safety

| Module | Responsibility |
|---|---|
| `LoopDetector` | Fingerprints calls with MD5 hash; blocks if same call repeats N times |
| `ToolGuard` | Combines allowlist + per-tool limit + total limit + loop detection into one `.check()` |
| `SafeToolExecutor` | 5-step pipeline: guard → registry lookup → Pydantic validation → threaded timeout → record |
| `security.py` | Regex-based injection detection; sanitizes tool results before they enter conversation history |
| `evaluator.py` | Offline harness using mock LLM; measures tool selection accuracy, arg correctness, execution success |

---

## Key Concepts

### LLM Call vs Tool Call

These are two completely different things:

| | LLM Call | Tool Call |
|---|---|---|
| **Triggered by** | Your loop (every iteration) | The LLM (only when it decides) |
| **Executed by** | Ollama server (GPU) | Your Python code (CPU) |
| **Takes** | 1–60 seconds | Milliseconds |
| **Every iteration?** | ✅ Always | ❌ Only sometimes |

**Rule:** Every tool call needs an LLM call first, but not every LLM call results in a tool call.

### Counting Calls

```
"What is 144 / 12 * 7?"           → LLM calls: 2,  tool calls: 1
"What is the capital of France?"  → LLM calls: 1,  tool calls: 0
"Weather + math question"          → LLM calls: 3,  tool calls: 2
```

`Tool calls made` = how many times Python ran a tool function  
`Call breakdown` = per-tool counts (always sums to `Tool calls made`)

---

## Running Tests

```bash
# Run all unit tests
pytest

# Run only fast tests (no Ollama required)
pytest -m "not integration"

# Run with output
pytest -v
```

---

## Available Tools

| Tool | Name in registry | Description |
|---|---|---|
| `CalculatorTool` | `calculator` | Evaluates safe math expressions. Returns a float. |
| `WeatherTool` | `get_weather` | Simulated weather for major cities. Returns JSON. |
| `DateTool` | `get_date` | Date operations: today, days_until, days_since, day_of_week. |

### Adding a new tool

1. Create a Pydantic input schema class in `src/level2/tools.py`
2. Create a tool class with `name`, `description`, `input_schema`, `get_ollama_schema()`, and `execute()`
3. Register it in `make_default_registry()` in `src/level2/registry.py`

---

## Further Reading

- [`docs/blog-tool-calling-explained.md`](docs/blog-tool-calling-explained.md) — Complete explanation of every concept in this project
- [`docs/level3/README.md`](docs/level3/README.md) — Level 3 architecture and design principles
- [`docs/level3/guard.md`](docs/level3/guard.md) — Guard system deep-dive
- [`docs/level3/executor.md`](docs/level3/executor.md) — Executor pipeline documentation
- [`docs/level3/security.md`](docs/level3/security.md) — Prompt injection defense
- [`docs/level3/evaluator.md`](docs/level3/evaluator.md) — Evaluation harness guide

---

## Model Compatibility

Tested with `qwen2.5:7b`. Other models that support native tool calling:

| Model | Tool Calling | Notes |
|---|---|---|
| `qwen2.5:7b` | ✅ Native | Recommended |
| `llama3.2:latest` | ✅ Native | Also works |
| `llama3:latest` | ✅ Native | Slower |
| `gemma:2b` | ⚠️ Limited | May not trigger tools reliably |

To switch models, change the `model` parameter when creating `AgentLoop`:

```python
agent = AgentLoop(registry=registry, model="llama3.2:latest")
```
