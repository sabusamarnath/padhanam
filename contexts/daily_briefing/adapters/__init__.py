"""Daily-briefing adapters (D146, S54).

The LLM composer adapter (LiteLLM-backed, via StructuredOutputPort per
D130) lands at S54 commit 6. The directory exists at commit 5 so the
``layers-daily-briefing`` import-linter contract spans a real module
tree (adapters -> application -> domain).
"""
