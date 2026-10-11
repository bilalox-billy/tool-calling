import httpx
import json

def verify():
    resp = httpx.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "qwen2.5:7b",
            "messages": [{"role": "user", "content": "What is 6 times 7?"}],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Evaluate a mathematical expression. Use when asked to calculate numbers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "A safe math expression like '6 * 7'"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            }],
            "stream": False,
        },
        timeout=60.0,
    )

    data = resp.json()
    msg = data["message"]

    if msg.get("tool_calls"):
        tool_call = msg["tool_calls"][0]["function"]
        print(f"Tool call detected: {tool_call['name']}({tool_call['arguments']})")
    elif msg.get("content"):
        print(f"Model answered directly (no tool call): {msg['content'][:100]}")
        print("This may be normal — try rephrasing as 'calculate 6 * 7 for me'")
    else:
        print("Empty response — check Ollama is running")


verify()