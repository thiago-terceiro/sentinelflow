---
name: Review SentinelFlow Change
description: "Review SentinelFlow workspace changes for bugs, regressions, test gaps, schema drift, and invalid command assumptions."
agent: "sentinelflow-reviewer"
model: "GPT-5 (copilot)"
argument-hint: "Describe the change or ask for a review of current edits"
---
Review the current SentinelFlow changes.

Return findings first and focus on:

- Functional regressions
- Backend and frontend contract drift
- Missing focused validation
- Missing tests or incorrect test scope
- Security or reliability risks