"""
Verify our model supports native tool calling.
Demonstrates: raw Ollama API call, tool schema format, response parsing
"""


import httpx
import json


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:7b"

CALCULATOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": (
            "Evaluate a mathematical expression and return the numeric result. "
            "Use this tool when the user asks to calculate, compute, or do arithmetic. "
            "Returns a float."
        ),

        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A safe math expression using only digits and operators: + - * / ( ) ."
                }
            },
            "required": ["expression"]
        }
    }
}



def call_ollama_with_tool(user_message: str) -> dict:
    """Send a message to Ollama Model with a tool schema"""
    response = httpx.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": user_message}],
            "tools": [CALCULATOR_SCHEMA],
            "stream": False,
        },
        timeout=120.0,  # 2-minute timeout for local LLM inference
    )

    response.raise_for_status()
    return response.json()


def analyze_response(data: dict) -> None :

    """
    Analyze the Ollama response and explain what happened.
    """

    msg = data.get("message",{})

    print("=" * 60)
    print(f"Model: {data.get('model', 'Unknown')}")
    print(f"Role: {msg.get('role', 'Unknown')}")
    print()

    tool_calls = msg.get("tool_calls", [])
    content = msg.get("content", "")

    if tool_calls:
        print("Tool CALL detected (native tool calling supported)")
        for tc in tool_calls:
            fn = tc.get("function", {})
            print(f"   Tool name: {fn.get('name')}")
            print(f"   Arguments: {json.dumps(fn.get('arguments', {}), indent=4)}")
            print()
            print("What this means:")
            print("  → The model REQUESTED the tool. It did NOT execute it.")
            print("  → Your Python code must execute the function and return the result.")
            print()
    
    elif content:
        print("MODEL ANSWERED DIRECTLY (no tool call produced)")
        print(f"   Content: {content[:200]}")
        print()
        print("What this means:")
        print("  → The model answered without using a tool.")
        print("  → This may mean: model doesn't support native tools, or")
        print("    the question didn't trigger tool use.")
    else:
        print("EMPTY RESPONSE")
        print(f"   Full response: {json.dumps(data, indent=2)}")



if __name__ == "__main__":
    test_messages = [
        "What is 144 divided by 12?",
        "Calculate 7 times 8 for me please",
        "What is the capital of France?",  # should NOT trigger tool
    ]

    for msg in test_messages:
        print(f"\n{'='*60}")
        print(f"USER: {msg}")

        try:
            data = call_ollama_with_tool(msg)
            analyze_response(data)
        except httpx.ReadTimeout:
            print(f"Error: Request timed out. Try increasing the timeout or check that Ollama is running.")
        except httpx.HTTPStatusError as e:
            print(f"Error: {e}")
            print(f"   Status: {e.response.status_code}")
            print(f"   Response: {e.response.text[:200]}")
        print(f"{'='*60}\n")


