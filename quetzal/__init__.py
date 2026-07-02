"""Quetzal — codebase question-answering benchmark.

Measure how well *and how cheaply* a real coding-agent harness (Claude Code,
Codex, Cursor, ...) can answer questions about a target codebase. Quetzal drives
the actual CLI harness — its system prompt, tools, and planning loop — rather
than a raw-API reimplementation, then judges each answer against curated
ground truth and reports accuracy + token cost per suite.

Pipeline (each step is a standalone CLI reading the previous step's output):

    1. RUN     quetzal run     answer questions with the agent, store token usage
    2. SCORE   quetzal score   judge answers against ground truth
    3. REPORT  quetzal report  aggregate accuracy + tokens per suite
"""
