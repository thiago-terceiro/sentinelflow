Important considerations

- "All reasoning" means all data actually emitted to and observable by application code. Some providers intentionally do not expose private chain-of-thought; the application must not promise, infer, or fabricate it.
- Raw prompts, responses, and provider-visible reasoning may contain sensitive data. Maximum visibility therefore belongs in an explicitly privileged, audited view rather than general operational telemetry.
- Ollama is the simplest local runtime because it offers an OpenAI-compatible API with minimal infrastructure. vLLM and llama.cpp add deployment or hardware complexity without strengthening the Foundry story. Foundry Local can be documented as an optional future local provider, but it should not block the reproducible Podman path.
- The multi-agent design is intentionally bounded. More agents do not automatically improve quality; each agent must have a distinct responsibility, schema, tool set, and evaluation.
- PostgreSQL is the durable source for workflow and audit state. Redis is omitted initially unless load testing proves a need for cross-instance fan-out or queues; unnecessary state stores increase audit and security complexity.
- No real payment API, customer system, or external web-browsing tool is included.
- The project should avoid implying regulatory compliance. It demonstrates controls and evidence suitable for further review.
