# `src/level3` — Production-Grade Tool Calling Layer

## The Big Idea

Level 2 built a **working** agent. Level 3 makes it **safe, reliable, and measurable** — the three pillars required before deploying any LLM-powered tool system in production.

| Layer | Level 2 | Level 3 adds |
|---|---|---|
| Registry + Tools | ✅ | — |
| Agent Loop | ✅ | — |
| Abuse Prevention | ❌ | ✅ `guard.py` |
| Hardened Execution | ❌ | ✅ `executor.py` |
| Injection Defense | ❌ | ✅ `security.py` |
| Quality Measurement | ❌ | ✅ `evaluator.py` |

## Architecture — Request Flow

```
User message
    │
    ▼
[security.py]    ← Is this message trying to hijack the agent?
    │
    ▼
[guard.py]       ← Is this tool call within limits? Is it looping?
    │
    ▼
[executor.py]    ← Validate args, run with timeout, catch all errors
    │
    ▼
[evaluator.py]   ← (offline) Did the agent make the right decisions?
```

## Module Overview

| File | Responsibility | Key Class/Function |
|---|---|---|
| [`guard.md`](./guard.md) | Loop detection + rate limiting | `LoopDetector`, `ToolGuard` |
| [`executor.md`](./executor.md) | Safe, timeout-bounded execution | `SafeToolExecutor` |
| [`security.md`](./security.md) | Prompt injection defense | `detect_prompt_injection`, `sanitize_tool_result` |
| [`evaluator.md`](./evaluator.md) | Offline test harness + metrics | `EvalCase`, `evaluate_single`, `compute_metrics` |

## Design Principles

1. **Never raise, always return** — every public function returns a result string + success bool, never crashes the agent loop.
2. **Defense in depth** — multiple independent checks (guard → validation → timeout → exception), so a bypass of one layer is still caught by the next.
3. **Separation of concerns** — security, limiting, execution, and evaluation are completely independent modules with no circular dependencies.
4. **Measurable quality** — the evaluator makes agent behavior testable and comparable across model versions.
