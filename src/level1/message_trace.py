# src/level1/message_trace.py
"""
Exercise 2: Trace the complete message format through a single tool call.
This demonstrates the exact JSON structure at every step.
"""
import json
import httpx

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"


def trace_full_tool_call(user_question: str) -> None:
    """
    Perform a complete single-tool-call cycle and print the exact messages.
    """
    # ── Step 1: Initial messages ───────────────────────────────────────────────
    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to a calculator and a clock."},
        {"role": "user", "content": user_question},
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Evaluate a safe math expression. Returns a float.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression like '12 * 8'"}
                    },
                    "required": ["expression"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Return the current local date and time as a formatted string.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]

    print("═" * 70)
    print("STEP 1: Sending messages to Ollama")
    print("Messages:")
    print(json.dumps(messages, indent=2))
    print("\nTools injected:")
    print(json.dumps([t["function"]["name"] for t in tools]))

    # ── Step 2: First LLM call ─────────────────────────────────────────────────
    response = httpx.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "tools": tools, "stream": False},
        timeout=60.0,
    )
    data = response.json()
    assistant_msg = data["message"]

    print("\n" + "═" * 70)
    print("STEP 2: Ollama response (raw)")
    print(json.dumps(assistant_msg, indent=2))

    # ── Step 3: Check for tool call ────────────────────────────────────────────
    tool_calls = assistant_msg.get("tool_calls")
    if not tool_calls:
        print("\n⚠️  No tool call — model answered directly:")
        print(assistant_msg.get("content"))
        return

    # ── Step 4: Simulate tool execution ───────────────────────────────────────
    tc = tool_calls[0]["function"]
    tool_name = tc["name"]
    args = tc["arguments"]

    print("\n" + "═" * 70)
    print(f"STEP 3: Tool call detected → {tool_name}({args})")
    print("Now YOUR CODE executes the tool (not the model!)")

    # Execute the tool
    import re
    from datetime import datetime

    if tool_name == "calculate":
        expression = args.get("expression", "")
        if re.match(r'^[\d\s\+\-\*\/\.\(\)]+$', expression):
            result = str(eval(expression))
        else:
            result = "Error: Unsafe expression"
    elif tool_name == "get_current_time":
        result = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        result = f"Error: Unknown tool '{tool_name}'"

    print(f"Tool result: {result!r}")

    # ── Step 5: Append messages ────────────────────────────────────────────────
    messages.append(assistant_msg)  # assistant message with tool_calls
    messages.append({"role": "tool", "content": result})  # tool result

    print("\n" + "═" * 70)
    print("STEP 4: Updated message history (sent back to model)")
    print(json.dumps(messages, indent=2))

    # ── Step 6: Second LLM call ────────────────────────────────────────────────
    response2 = httpx.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "tools": tools, "stream": False},
        timeout=60.0,
    )
    final_msg = response2.json()["message"]

    print("\n" + "═" * 70)
    print("STEP 5: Final Ollama response")
    print(f"Role: {final_msg['role']}")
    print(f"Content: {final_msg.get('content')}")
    print(f"Tool calls: {final_msg.get('tool_calls')}")
    print("\n✅ COMPLETE CYCLE TRACED!")


if __name__ == "__main__":
    trace_full_tool_call("What is 2+2 and what time is it?")
