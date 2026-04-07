"""Tests for automation.prompts.context_size — priority tier management."""

from automation.prompts.context_size import estimate_tokens, reduce_context


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_single_word(self):
        assert estimate_tokens("hello") == 1  # 1 * 1.3 = 1.3 → int = 1

    def test_multiple_words(self):
        result = estimate_tokens("one two three four five")
        assert result == 6  # 5 * 1.3 = 6.5 → int = 6

    def test_long_text(self):
        text = " ".join(["word"] * 1000)
        result = estimate_tokens(text)
        assert result == 1300  # 1000 * 1.3


class TestReduceContext:
    def test_no_reduction_when_under_budget(self):
        context = {"subsections": [
            {"label": "A", "content": "short text"},
        ]}
        result, strategies = reduce_context(context, "header", token_budget=10000)
        assert strategies == []
        assert result["subsections"][0]["content"] == "short text"

    def test_priority_4_reduced_first(self):
        context = {"subsections": [
            {"label": "P2", "content": "important data " * 100, "priority": 2},
            {"label": "P4", "content": "background " * 100, "priority": 4},
        ]}
        result, strategies = reduce_context(context, "h" * 50, token_budget=300)
        assert any("Priority 4" in s for s in strategies)
        p4 = next(s for s in result["subsections"] if s["label"] == "P4")
        assert p4.get("summarized") is True

    def test_priority_3_reduced_before_2(self):
        context = {"subsections": [
            {"label": "P2", "content": "important " * 200, "priority": 2},
            {"label": "P3", "content": "adjacent " * 200, "priority": 3},
        ]}
        result, strategies = reduce_context(context, "h", token_budget=200)
        strategy_labels = " ".join(strategies)
        # P3 should be reduced before P2
        if "Priority 3" in strategy_labels and "Priority 2" in strategy_labels:
            p3_idx = strategy_labels.index("Priority 3")
            p2_idx = strategy_labels.index("Priority 2")
            assert p3_idx < p2_idx

    def test_priority_1_never_reduced(self):
        # Priority 1 is passed as separate text, not in context subsections
        p1_text = "instructions " * 1000
        context = {"subsections": [
            {"label": "P4", "content": "bg " * 100, "priority": 4},
        ]}
        result, strategies = reduce_context(context, p1_text, token_budget=500)
        # Should summarize P4 but p1 is never touched
        assert any("Priority 4" in s for s in strategies)

    def test_warns_when_still_over_budget(self):
        # Even after all reductions, still over budget
        p1_text = "word " * 10000  # ~13000 tokens
        context = {"subsections": [
            {"label": "P2", "content": "data " * 5000, "priority": 2},
        ]}
        _, strategies = reduce_context(context, p1_text, token_budget=100)
        assert any("WARNING" in s for s in strategies)

    def test_list_content_summarized_with_count(self):
        context = {"subsections": [
            {"label": "Items", "content": [{"a": 1}, {"b": 2}, {"c": 3}], "priority": 4},
        ]}
        result, _ = reduce_context(context, "h", token_budget=10)
        sub = result["subsections"][0]
        assert "3 items" in sub["content"]

    def test_dict_content_summarized_with_keys(self):
        context = {"subsections": [
            {"label": "Obj", "content": {"alpha": 1, "beta": 2}, "priority": 4},
        ]}
        result, _ = reduce_context(context, "h", token_budget=10)
        sub = result["subsections"][0]
        assert "alpha" in sub["content"]
