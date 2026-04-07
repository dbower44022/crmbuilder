"""Context size management for CRM Builder Automation prompts.

Implements L2 PRD Section 10.9: priority tier management with word-based
token estimation and progressive reduction.

Priority tiers (Section 10.9.1):
- Priority 1: Never reduced (session instructions, header, output spec)
- Priority 2: Reduced last (directly relevant data)
- Priority 3: Summarized if needed (adjacent context)
- Priority 4: Summarized first (background context)

Uses word count as a token proxy: 1 word ≈ 1.3 tokens.
"""

import json

# Conversion factor: words to estimated tokens.
WORDS_TO_TOKENS = 1.3

# Default context window budget in tokens.
DEFAULT_TOKEN_BUDGET = 180_000


def estimate_tokens(text: str) -> int:
    """Estimate the token count of a text string.

    Uses word count * 1.3 as a proxy. Does not use any external tokenizer.

    :param text: The text to estimate.
    :returns: Estimated token count.
    """
    if not text:
        return 0
    word_count = len(text.split())
    return int(word_count * WORDS_TO_TOKENS)


def _summarize_subsection(subsection: dict) -> dict:
    """Reduce a subsection to a one-line summary.

    For list content: reports the count.
    For dict content: reports the keys.
    For string content: truncates to first 100 chars.
    """
    content = subsection.get("content")
    label = subsection.get("label", "")

    if isinstance(content, list):
        summary = f"[{len(content)} items — summarized to save context space]"
    elif isinstance(content, dict):
        keys = list(content.keys())[:5]
        summary = f"[Object with keys: {', '.join(keys)} — summarized]"
    elif isinstance(content, str):
        summary = content[:100] + "..." if len(content) > 100 else content
    else:
        summary = "[content summarized]"

    return {"label": label, "content": summary, "summarized": True}


def reduce_context(
    context: dict,
    priority_1_text: str,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> tuple[dict, list[str]]:
    """Apply progressive reduction to fit within the token budget.

    The context dict has a "subsections" list. Each subsection may have an
    optional "priority" key (2, 3, or 4). Defaults to 2 if not set.

    Reduction order (Section 10.9.2):
    1. Omit or summarize Priority 4 content
    2. Summarize Priority 3 content
    3. Truncate Priority 2 content
    4. Flag if still over budget

    :param context: The context dict with "subsections" list.
    :param priority_1_text: The non-reducible text (header + instructions + output spec).
    :param token_budget: Target token budget.
    :returns: Tuple of (possibly-reduced context, list of reduction strategies applied).
    """
    strategies_applied: list[str] = []

    # Calculate current size
    p1_tokens = estimate_tokens(priority_1_text)
    context_text = json.dumps(context, default=str)
    total_tokens = p1_tokens + estimate_tokens(context_text)

    if total_tokens <= token_budget:
        return context, strategies_applied

    # Group subsections by priority
    subsections = context.get("subsections", [])

    # Step 1: Summarize Priority 4 content
    for i, sub in enumerate(subsections):
        if sub.get("priority", 2) == 4 and not sub.get("summarized"):
            subsections[i] = _summarize_subsection(sub)
            strategies_applied.append(f"Summarized Priority 4: {sub.get('label', 'unknown')}")

    context["subsections"] = subsections
    context_text = json.dumps(context, default=str)
    total_tokens = p1_tokens + estimate_tokens(context_text)
    if total_tokens <= token_budget:
        return context, strategies_applied

    # Step 2: Summarize Priority 3 content
    for i, sub in enumerate(subsections):
        if sub.get("priority", 2) == 3 and not sub.get("summarized"):
            subsections[i] = _summarize_subsection(sub)
            strategies_applied.append(f"Summarized Priority 3: {sub.get('label', 'unknown')}")

    context["subsections"] = subsections
    context_text = json.dumps(context, default=str)
    total_tokens = p1_tokens + estimate_tokens(context_text)
    if total_tokens <= token_budget:
        return context, strategies_applied

    # Step 3: Summarize Priority 2 content
    for i, sub in enumerate(subsections):
        if sub.get("priority", 2) == 2 and not sub.get("summarized"):
            subsections[i] = _summarize_subsection(sub)
            strategies_applied.append(f"Summarized Priority 2: {sub.get('label', 'unknown')}")

    context["subsections"] = subsections
    context_text = json.dumps(context, default=str)
    total_tokens = p1_tokens + estimate_tokens(context_text)
    if total_tokens <= token_budget:
        return context, strategies_applied

    # Step 4: Still over budget — flag it
    strategies_applied.append(
        "WARNING: Prompt exceeds context capacity even after all reductions. "
        "Consider splitting the work or using a higher-capacity model."
    )

    return context, strategies_applied
