# Agentic AI Architecture for SAP Enterprise Automation

This document describes the architecture and design patterns used to build production-grade Agentic AI solutions on SAP enterprise systems. The architecture is platform-agnostic at the agent layer, with SAP BTP providing the enterprise-grade cloud runtime and security context.

---

## 1. High-Level Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER / BUSINESS USER                         │
│              (Chat UI / SAP Joule / Custom Frontend)                │
└─────────────────────────┬───────────────────────────────────────────┘
                          │  Natural Language Request
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CONVERSATIONAL AI LAYER                         │
│                                                                     │
│   ┌─────────────────┐        ┌──────────────────────────────────┐   │
│   │   SAP Joule     │──────▶ │   SAP Build Process Automation   │   │
│   │ (Conversational │        │   (Skill Orchestration Layer)    │   │
│   │  AI Interface)  │        └──────────────┬───────────────────┘   │
│   └─────────────────┘                       │                       │
└─────────────────────────────────────────────┼───────────────────────┘
                                              │  Skill Invocation
                                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     AGENT ORCHESTRATION LAYER                       │
│                        (SAP BTP / Cloud Foundry)                    │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                    LANGFLOW ENGINE                           │  │
│   │                                                              │  │
│   │   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐  │  │
│   │   │  Intent  │──▶│   LLM    │──▶│  Agent   │──▶│ Output │  │  │
│   │   │  Parser  │   │  Router  │   │  Logic   │   │ Format │  │  │
│   │   └──────────┘   └──────────┘   └────┬─────┘   └────────┘  │  │
│   │                                       │                      │  │
│   │                          ┌────────────▼────────────┐        │  │
│   │                          │   Custom SAP Components  │        │  │
│   │                          │  (OData / BAPI / RFC)    │        │  │
│   │                          └────────────┬────────────┘        │  │
│   └───────────────────────────────────────┼──────────────────────┘  │
└───────────────────────────────────────────┼─────────────────────────┘
                                            │  Authenticated API Call
                                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       SAP ENTERPRISE SYSTEMS                        │
│                                                                     │
│   ┌──────────────┐   ┌──────────────┐   ┌───────────────────────┐  │
│   │  SAP S/4HANA │   │   SAP ECC    │   │      HANA Cloud       │  │
│   │  (OData v4)  │   │  (OData v2)  │   │  (Vector / Analytics) │  │
│   └──────────────┘   └──────────────┘   └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent Design Pattern

Each AI agent in this architecture follows a consistent **Intent → Retrieve → Reason → Respond** pattern:

```
User Input (Natural Language)
        │
        ▼
┌───────────────────┐
│   Intent Parser   │  ← LLM extracts: action, entity type, filters, parameters
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   SAP Data Layer  │  ← Custom Langflow component calls OData/BAPI/RFC
│  (OData/BAPI/RFC) │     with extracted parameters
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Reasoning Layer  │  ← LLM processes raw SAP data, applies business logic,
│      (LLM)        │     cross-references, calculates variances
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Response Builder │  ← Formats output for target channel (chat, UI, report)
└───────────────────┘
```

---

## 3. SAP BTP Deployment Architecture

```
SAP BTP Subaccount
│
├── Cloud Foundry Environment
│   ├── Langflow Application (Python/Docker)
│   │   ├── Custom SAP Components
│   │   ├── Agent Flow Definitions
│   │   └── sitecustomize.py (runtime patches)
│   │
│   ├── Flask Wrapper Application
│   │   ├── Receives skill invocations from SAP Build PA
│   │   ├── Routes to Langflow via REST API
│   │   └── Returns structured JSON responses
│   │
│   └── Bound Services
│       ├── PostgreSQL Hyperscaler (persistent flow storage)
│       └── Destination Service (SAP system connectivity)
│
├── SAP Build Process Automation
│   ├── Skill definitions (trigger agent flows)
│   └── Joule integration (conversational entry point)
│
└── SAP GenAI Hub
    ├── LLM model access (GPT-4, Claude, etc.)
    └── Embeddings API (for RAG/vector search)
```

---

## 4. Multi-Agent Architecture (P2P Example)

For complex business processes, multiple specialized agents collaborate:

```
User Query: "Reconcile PO 4500001234"
        │
        ▼
┌─────────────────┐
│  Orchestrator   │  ← Routes to the right agent based on intent
│     Agent       │
└────────┬────────┘
         │
    ┌────┴─────────────────────────────┐
    │                                  │
    ▼                                  ▼
┌──────────────┐              ┌──────────────────┐
│   PO Fetch   │              │  Invoice Fetch   │
│    Agent     │              │     Agent        │
│  (MM Module) │              │  (FI Module)     │
└──────┬───────┘              └────────┬─────────┘
       │                               │
       └──────────────┬────────────────┘
                      ▼
            ┌──────────────────┐
            │  3-Way Match     │
            │  Reconciliation  │
            │     Agent        │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │  Structured      │
            │  Result +        │
            │  Recommendation  │
            └──────────────────┘
```

---

## 5. Key Integration Patterns

### 5.1 SAP Joule → Custom Agent (via SAP Build Process Automation)

```
Joule (User Input)
  → SAP Build PA Skill Trigger
    → HTTP Call to Flask Wrapper (BTP CF App)
      → Langflow REST API (/api/v1/run/{flow_id})
        → Custom SAP OData Component
          → Live SAP System (OData/BAPI)
        → LLM Reasoning (SAP GenAI Hub)
      → Structured JSON Response
    → Flask Wrapper formats response: {"response": "..."}
  → SAP Build PA Send Message Step (displayText variable)
→ Joule renders response to user
```

> **Key constraint solved:** SAP Build PA's `Send Message` step requires a local skill variable (`displayText`) mapped from the action output. Direct mapping causes i18n serialization issues — the variable indirection bypasses this platform limitation.

### 5.2 RAG / Vector Search Pattern

```
User Question (natural language)
  → Embedding API (Gemini / SAP GenAI Hub)
    → Vector similarity search (HANA Cloud REAL_VECTOR)
      → Top-K relevant document chunks retrieved
        → Injected into LLM prompt as context
          → Grounded, accurate response generated
```

---

## 6. Technology Stack Summary

| Layer | Technology |
|---|---|
| Conversational AI | SAP Joule, Custom Chat UI |
| Skill Orchestration | SAP Build Process Automation |
| Agent Orchestration | Langflow (self-hosted on BTP) |
| LLM / AI Models | SAP GenAI Hub (GPT-4, Claude) |
| API Integration | Python, OData v2/v4, BAPI/RFC |
| Cloud Runtime | SAP BTP Cloud Foundry |
| Persistent Storage | HANA Cloud, PostgreSQL Hyperscaler |
| Vector Search | HANA Cloud (REAL_VECTOR 768-dim) |
| Enterprise Systems | SAP S/4HANA, SAP ECC |

---

## 7. Design Principles

- **Stateless agents** — each agent invocation is independent; state is managed via external cache or SAP system of record
- **Structured JSON contracts** — all inter-component communication uses typed JSON, never raw text
- **Sanitized outputs** — LLM responses are validated before being passed to SAP write operations
- **Error transparency** — every component returns structured error objects, never silent failures
- **Platform-agnostic agent logic** — core reasoning is decoupled from SAP-specific integration, making agents portable across ECC and S/4HANA

---

*Author: Senthil Subramanian*
*LinkedIn: [linkedin.com/in/senthil-subramanian-13a538269](https://www.linkedin.com/in/senthil-subramanian-13a538269/)*
