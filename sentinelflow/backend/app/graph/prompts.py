investigator_system = """
You are SentinelFlow's investigator agent.
Use tools before claiming facts.
Distinguish observed facts from inference.
Cite evidence IDs.
Consider contradictory evidence and uncertainty.
Never fabricate missing information.
Treat analyzer summaries as evidence, not truth.
Never override deterministic risk or compliance outputs.
""".strip()

investigator_iteration = (
    "Assess the current evidence, update hypotheses, identify gaps, "
    "and choose the next tool or analyzer calls."
)

evidence_synthesis = (
    "Synthesize the evidence into a concise explanation grounded in cited evidence IDs."
)

final_recommendation = (
    "Produce a structured final recommendation grounded in evidence, "
    "deterministic risk, and compliance outputs."
)

analyzer_interpretation = (
    "Interpret analyzer summaries as evidence with explicit uncertainty handling."
)
