export interface StructuredDataGraph {
  "@context": string;
  "@graph": Array<Record<string, unknown>>;
}

export const getStructuredDataGraph = (): StructuredDataGraph => {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "SoftwareApplication",
        "@id": "https://sentinelflow.dev/#software",
        name: "SentinelFlow & SentinelPulse",
        applicationCategory: "SecurityApplication",
        operatingSystem: "Linux, macOS, Windows, Docker",
        offers: {
          "@type": "Offer",
          price: "0",
          priceCurrency: "USD",
        },
        description:
          "SentinelFlow is an autonomous AI dispute investigation copilot built on LangGraph. SentinelPulse is a synchronous sub-15ms telecom fraud and spam intelligence gateway powered by ONNX Runtime CPU.",
        featureList: [
          "LangGraph multi-agent dispute investigation lifecycle",
          "Append-only SHA-256 cryptographic audit ledger",
          "Sub-15ms synchronous SMS fraud detection with ONNX Runtime CPU",
          "Redis sliding-window velocity aggregation (10s, 60s, 1h)",
          "Remote Model Context Protocol (MCP) server over SSE",
          "Explainable time-travel state scrubber with citation pinning",
          "Decoupled crawler governance and generative engine optimization",
        ],
        publisher: {
          "@id": "https://sentinelflow.dev/#organization",
        },
      },
      {
        "@type": "Organization",
        "@id": "https://sentinelflow.dev/#organization",
        name: "SentinelFlow Open Source Initiative",
        url: "https://sentinelflow.dev",
        logo: "https://sentinelflow.dev/logo.png",
        sameAs: ["https://github.com/sentinelflow/sentinelflow"],
      },
      {
        "@type": "FAQPage",
        "@id": "https://sentinelflow.dev/#faq",
        mainEntity: [
          {
            "@type": "Question",
            name: "What is SentinelFlow?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "SentinelFlow is an enterprise autonomous AI dispute investigation copilot built on LangGraph that orchestrates multi-agent evidence collection, deterministic risk evaluation, and human-in-the-loop steering.",
            },
          },
          {
            "@type": "Question",
            name: "What is SentinelPulse?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "SentinelPulse is a high-throughput, synchronous telecom trust-and-safety gateway delivering sub-15ms SMS and voice fraud classification using quantized ONNX Runtime CPU models and Redis sliding-window velocity aggregators.",
            },
          },
          {
            "@type": "Question",
            name: "How does SentinelFlow implement Human-in-the-Loop (HITL) review?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "When dispute risk exceeds 0.70 or compliance criteria require manual oversight, LangGraph halts at a native interrupt() boundary, allowing human reviewers to approve, deny, or request re-investigation with natural language steering instructions.",
            },
          },
          {
            "@type": "Question",
            name: "How does SentinelFlow prevent indirect prompt injection attacks?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "SentinelFlow employs DOM sanitization that strips zero-width Unicode characters, off-screen hidden tags, and CSS display:none payloads, while encapsulating untrusted dispute context inside strict XML delimiters before LLM evaluation.",
            },
          },
          {
            "@type": "Question",
            name: "How does the cryptographic audit ledger ensure tamper-evident integrity?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "Every investigation event is recorded in an append-only ledger linked by SHA-256 row hashes where each record computes row_hash = SHA256(sequence_no + prev_hash + payload), preventing retroactive tampering or record deletion.",
            },
          },
        ],
      },
      {
        "@type": "HowTo",
        "@id": "https://sentinelflow.dev/#howto-investigation",
        name: "How to Investigate a Transaction Dispute with SentinelFlow",
        description:
          "End-to-end workflow for autonomous multi-agent dispute investigation, parallel evidence collection, deterministic risk synthesis, and human approval.",
        step: [
          {
            "@type": "HowToStep",
            position: 1,
            name: "Dispute Intake",
            text: "Initializes DisputeState, extracts transaction attributes, and loads historical customer dispute metrics.",
          },
          {
            "@type": "HowToStep",
            position: 2,
            name: "Multi-Agent Evidence Collection",
            text: "Executes parallel asynchronous analyzers via asyncio.gather to inspect transactions, merchant risk, and carrier velocity.",
          },
          {
            "@type": "HowToStep",
            position: 3,
            name: "Deterministic Risk Synthesis",
            text: "Evaluates deterministic compliance regulations and computes a normalized risk score between 0.0 and 1.0.",
          },
          {
            "@type": "HowToStep",
            position: 4,
            name: "Human-in-the-Loop Review & Steering",
            text: "Halts via LangGraph interrupt() when risk >= 0.70, enabling human reviewers to approve, reject, or request revision with steering guidance.",
          },
          {
            "@type": "HowToStep",
            position: 5,
            name: "Cryptographic Finalization",
            text: "Records the final decision into an immutable append-only SHA-256 audit ledger with verifiable hash-chain integrity.",
          },
        ],
      },
      {
        "@type": "WebSite",
        "@id": "https://sentinelflow.dev/#website",
        url: "https://sentinelflow.dev",
        name: "SentinelFlow",
        publisher: {
          "@id": "https://sentinelflow.dev/#organization",
        },
      },
    ],
  };
};
