---
name: Plan SentinelFlow Change
description: "Create an implementation-ready plan for a SentinelFlow task by tracing owning files, constraints, and the cheapest validation path."
agent: "sentinelflow-researcher"
model: "GPT-5 (copilot)"
argument-hint: "Describe the feature, bug, or behavior to trace"
---
Investigate the user's requested SentinelFlow task and produce an implementation-ready plan.

Include:

- The owning files and why they control the behavior
- Backend and frontend boundaries that matter
- The smallest safe change that could solve the problem
- The cheapest validation that could falsify the plan
- Any schema, state, or API contract updates that must stay aligned