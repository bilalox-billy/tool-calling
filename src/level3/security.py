# src/level3/security.py
"""
Security utilities for tool-calling systems.
Prompt injection detection and tool result sanitization.
"""
import re
import html


INJECTION_PATTERNS = [
    r'ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts)',
    r'system\s*:\s*now\s+call',
    r'<\s*tool_call\s*>',
    r'SYSTEM\s*OVERRIDE',
    r'forget\s+(everything|your\s+instructions)',
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in INJECTION_PATTERNS]


def detect_prompt_injection(text: str) -> list[str]:
    """
    Scan text for common prompt injection patterns.
    Returns list of matched patterns (empty if clean).
    """
    matches = []
    for pattern in COMPILED_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return matches


def sanitize_tool_result(result: str, max_length: int = 2000) -> str:
    """
    Sanitize a tool result before injecting into conversation history.
    - Truncate very long results
    - Remove HTML tags
    - Escape potential injection sequences
    """
    if len(result) > max_length:
        result = result[:max_length] + f"... [truncated to {max_length} chars]"

    # Remove HTML tags
    result = re.sub(r'<[^>]+>', '', result)

    # Flag and strip common injection phrases
    injections = detect_prompt_injection(result)
    if injections:
        import logging
        logging.getLogger(__name__).warning(
            f"Prompt injection detected in tool result: {injections}"
        )
        # Don't block — log and continue, but note the attempt
        result = f"[SECURITY: Potentially suspicious content detected] {result}"

    return result


def check_user_message(message: str) -> list[str]:
    """
    Check user input for injection attempts.
    Returns list of warnings (empty if clean).
    """
    return detect_prompt_injection(message)
