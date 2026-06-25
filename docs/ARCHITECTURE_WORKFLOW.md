# The Second Brain — Architecture & Workflow

> **An Open-Source Cognitive Operating System (CogOS)**  
> Multi-agent orchestration · hierarchical memory · graph-augmented hybrid retrieval · stream-native ingestion

---

## Table of Contents

1. [Vision & Design Principles](#1-vision--design-principles)
2. [System Context](#2-system-context)
3. [Layered Architecture](#3-layered-architecture)
4. [Cognitive Memory Model](#4-cognitive-memory-model)
5. [Core Workflows](#5-core-workflows)
6. [Multi-Agent Orchestration](#6-multi-agent-orchestration)
7. [Graph-RAG Hybrid Retrieval](#7-graph-rag-hybrid-retrieval)
8. [Data Ingestion Pipeline](#8-data-ingestion-pipeline)
9. [Target Use Cases](#9-target-use-cases)
10. [Technology Stack](#10-technology-stack)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Evaluation & SLOs](#12-evaluation--slos)
13. [Repository Layout](#13-repository-layout)

---

## 1. Vision & Design Principles

**The Second Brain** is a production-grade cognitive engine that unifies:


| Inspiration           | Contribution to CogOS                                                     |
| --------------------- | ------------------------------------------------------------------------- |
| **MemGPT**            | Self-managed context vs. archival memory; memory ops as first-class tools |
| **Generative Agents** | Importance-weighted recall, reflection, and episodic consolidation        |
| **Graph-RAG**         | Community-aware relational retrieval over knowledge graphs                |


### Design Principles


| Principle                 | Meaning                                                                            |
| ------------------------- | ---------------------------------------------------------------------------------- |
| **Tiered, not flat**      | Memory is partitioned by latency, durability, and cognitive role                   |
| **Relational + semantic** | Hybrid graph-vector search beats pure embedding retrieval on multi-hop queries     |
| **Stream-native**         | Real-time state (IoT, logs) flows through working memory before archival promotion |
| **Agent-specialized**     | No monolithic LLM loop — roles are explicit, auditable, and composable             |
| **Evidence-grounded**     | Every answer and action passes through a Critic with provenance requirements       |
| **Production-first**      | Observability, idempotency, and SLOs are first-class, not afterthoughts            |


---

## 2. System Context

C4 Level 1 view of The Second Brain and its external actors.

### Interactive diagram (Cursor / GitHub compatible)

```mermaid
flowchart TB
    user(["User / Operator"])
    cogos["The Second Brain<br/>(CogOS)"]

    subgraph external["External systems"]
        enterprise["Enterprise Systems"]
        iot["IoT Layer"]
        facility["Smart Facility"]
        llm["LLM Providers"]
    end

    user -->|"Queries and commands"| cogos
    enterprise -->|"Docs, logs, events"| cogos
    iot -->|"Telemetry"| cogos
    cogos -->|"Control actions"| facility
    cogos -->|"Reasoning and extraction"| llm
    cogos -->|"Tool calls and tickets"| enterprise

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef system fill:#1168bd,stroke:#0b4884,color:#fff
    classDef externalNode fill:#999,stroke:#666,color:#fff

    class user person
    class cogos system
    class enterprise,iot,facility,llm externalNode
```

### C4 diagram (pre-rendered)

Cursor’s markdown preview does **not** support the `C4Context` diagram type (it reports a syntax error even when the source is valid). Use the static export below, or render the source file with [Mermaid Live Editor](https://mermaid.live) or Mermaid CLI 10.7+.

![System Context C4 diagram](./diagrams/system-context-c4.svg)

**Source:** [`docs/diagrams/system-context.c4.mmd`](./diagrams/system-context.c4.mmd)

```bash
npx @mermaid-js/mermaid-cli -i docs/diagrams/system-context.c4.mmd -o docs/diagrams/system-context-c4.svg
```



---

## 3. Layered Architecture

```mermaid
flowchart TB
    subgraph L4["Layer 4 — Interfaces"]
        UI[Web / CLI / API Gateway]
        HOOK[Webhooks & Event Subscriptions]
    end

    subgraph L3["Layer 3 — Multi-Agent Orchestration"]
        ORCH[Orchestrator]
        MM[Memory Manager]
        PL[Planner]
        CR[Critic]
        TE[Tool Executor]
        SO[Stream Observer]
    end

    subgraph L2["Layer 2 — Cognitive Memory"]
        M0["M₀ Working Memory<br/><i>Ephemeral / stream state</i>"]
        M1["M₁ Short-Term Memory<br/><i>In-context window</i>"]
        M2["M₂ Long-Term Memory<br/><i>Graph + vector store</i>"]
    end

    subgraph L1["Layer 1 — Ingestion & Processing"]
        KAFKA[Apache Kafka]
        SPARK[Spark Streaming]
        FAUST[Faust Workers]
        ETL[NER / RE / Embedding]
    end

    subgraph L0["Layer 0 — Persistence & Observability"]
        NEO[(Neo4j + Vector Index)]
        REDIS[(Redis Streams)]
        S3[(Object Store)]
        OTEL[OpenTelemetry / Audit Log]
    end

    UI --> ORCH
    HOOK --> KAFKA

    ORCH --> MM & PL & CR & TE & SO
    MM <--> M0 & M1 & M2
    SO <--> M0
    PL --> MM
    TE --> HOOK

    KAFKA --> SPARK & FAUST --> ETL
    ETL --> NEO & REDIS & S3
    SPARK --> M0
    FAUST --> M0

    M2 --> NEO & S3
    M0 --> REDIS

    ORCH & TE & MM --> OTEL
```



### Layer Responsibilities


| Layer                | Responsibility                    | Key Components                         |
| -------------------- | --------------------------------- | -------------------------------------- |
| **L4 — Interfaces**  | Auth, routing, session management | FastAPI gateway, WebSocket for streams |
| **L3 — Agents**      | Reasoning, verification, action   | LangGraph state machine                |
| **L2 — Memory**      | Tiering, retrieval, compaction    | Memory Manager + policies              |
| **L1 — Ingestion**   | Real-time and batch data intake   | Kafka, Spark, Faust                    |
| **L0 — Persistence** | Durable storage, tracing          | Neo4j, Redis, S3, OTEL                 |


---

## 4. Cognitive Memory Model

### 4.1 Memory Tiers

```mermaid
flowchart LR
    subgraph M0["M₀ — Working Memory"]
        direction TB
        W1[Sliding IoT windows]
        W2[Live log aggregates]
        W3[Session scratch state]
    end

    subgraph M1["M₁ — Short-Term Memory"]
        direction TB
        S1[Core persona blocks]
        S2[Active dialogue turns]
        S3[Pinned retrieval bundle]
    end

    subgraph M2["M₂ — Long-Term Memory"]
        direction TB
        L1[Entity graph]
        L2[Document chunks + embeddings]
        L3[Reflections & community summaries]
    end

    M0 -->|"promote (importance / anomaly)"| M1
    M1 -->|"consolidate / reflect"| M2
    M2 -->|"retrieve on query"| M1
    M0 -->|"pin to context"| M1
```




| Tier       | Symbol | Store                | TTL             | Role                                               |
| ---------- | ------ | -------------------- | --------------- | -------------------------------------------------- |
| Working    | M_0    | Redis / Flink state  | Seconds–minutes | Real-time stream aggregates, anomaly buffers       |
| Short-term | M_1    | LLM context window   | Session         | Active reasoning surface; MemGPT-style core blocks |
| Long-term  | M_2    | Neo4j + vector index | Permanent       | Archival knowledge, relationships, reflections     |


### 4.2 Formal Memory State

At time t, system memory is:


\mathcal{M}_t = \big(M_0^{(t)}, M_1^{(t)}, M_2\big)


Each observation o_i is a tuple:


o_i = (\text{text}_i, t_i, \mathbf{e}_i, \phi_i, s_i)


where \mathbf{e}_i is the embedding, \phi_i is metadata (source, modality, agent), and s_i \in \text{observation}, \text{reflection}, \text{plan}.

### 4.3 Retrieval Score

When the agent issues query q at time t, each long-term unit m is ranked by:


R(m \mid q, t) = \alpha \cdot \text{sim}(q, m) + \beta \cdot e^{-(t - t_m)/\tau} + \gamma \cdot I(m) + \delta \cdot \Psi_G(m, q)



| Term              | Meaning                                         |
| ----------------- | ----------------------------------------------- |
| \text{sim}(q, m)  | Cosine similarity in embedding space            |
| e^{-(t-t_m)/\tau} | Recency decay (Generative Agents)               |
| I(m)              | Importance score \in [0, 1]                     |
| \Psi_G(m, q)      | Graph proximity (path length, typed edge match) |


Top-k retrieval: \mathcal{R}_k = \text{top-}k m \in M_2 : R(m \mid q, t) 

### 4.4 Context Assembly

Given token budget B, the Memory Manager assembles:


C_t = \arg\max_{C \subseteq \mathcal{U}*t,\ |C| \le B} \sum*{x \in C} w(x) \cdot \text{utility}(x, q)


**Hard constraints:**

- Pinned M_0 stream state is always included (IoT anomalies, live dashboards)
- System and persona core blocks are reserved
- Lowest-utility dialogue turns are evicted first (FIFO + utility hybrid)

### 4.5 Promotion & Consolidation

```mermaid
stateDiagram-v2
    [*] --> M0: Stream event / tool observation
    M0 --> M1: pin OR importance > θ_I
    M1 --> M2: reflect_and_consolidate()
    M2 --> M1: hybrid retrieve on query
    M1 --> M0: demote on session end (optional snapshot)
    M2 --> [*]: decay / archive (policy-driven)
```



**Promotion rule:**


\text{promote}(o) \iff I(o) > \theta_I \lor \text{repeataccess}(o) > \theta_a \lor \text{criticflag}(o)


**Reflection (episodic → semantic):**


r = f_{\text{LLM}}\big(o_j\big), \quad M_2 \leftarrow M_2 \cup r, \quad \text{link}(r, o_j)


---

## 5. Core Workflows

### 5.1 End-to-End Query Workflow

Primary path: user question → evidence-backed answer.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant GW as API Gateway
    participant OR as Orchestrator
    participant MM as Memory Manager
    participant M0 as M₀ Working
    participant M2 as M₂ Long-Term
    participant PL as Planner
    participant TE as Tool Executor
    participant CR as Critic
    participant AUD as Audit Log

    User->>GW: POST /query
    GW->>OR: Route task (type: QA)
    OR->>MM: Assemble context C_t
    MM->>M0: Fetch pinned stream state
    MM->>M2: Hybrid retrieve R_k
    MM-->>OR: Context bundle + evidence subgraph
    OR->>PL: Plan reasoning steps
    loop Tool loop (max N)
        PL->>TE: Execute tool (search, API, code)
        TE-->>PL: Observation
        PL->>MM: Update M₁ / queue promotion
    end
    PL->>CR: Draft answer + evidence
    alt Critic rejects
        CR-->>PL: Revision request
        PL->>PL: Re-plan with feedback
    else Critic accepts
        CR-->>OR: Approved response
    end
    OR->>AUD: Trace + provenance
    OR-->>GW: Answer + citations
    GW-->>User: Response
```



### 5.2 Real-Time Ingestion Workflow

Continuous path: external data → working memory → long-term graph.

```mermaid
flowchart TD
    A[Data Sources] --> B{Modality}
    B -->|Documents / Code / Logs| C[Kafka: raw.*]
    B -->|IoT Telemetry| D[Kafka: stream.iot]

    C --> E[Spark Structured Streaming]
    D --> F[Faust Workers]

    E --> G[Chunk + Parse]
    F --> H[Window Aggregate<br/>mean, σ, rate]

    G --> I[NER / Relation Extraction]
    I --> J[Embedding Service]
    J --> K[Neo4j MERGE<br/>nodes + edges]
    J --> L[Vector Index Update]

    H --> M[M₀ Redis<br/>keyed by device/zone]
    H --> N{Anomaly?}
    N -->|Yes| O[Stream Observer Alert]
    O --> P[Pin to M₁ + notify Orchestrator]
    N -->|No| M

    K --> Q[M₂ Long-Term]
    L --> Q

    I --> R{Importance > θ?}
    R -->|Yes| S[Promote to M₂ immediately]
    R -->|No| T[Batch archival job]
    T --> Q
```



### 5.3 Autonomous Action Workflow (IoT / Smart Facility)

Action path: anomaly → plan → policy check → actuate.

```mermaid
sequenceDiagram
    autonumber
    participant IoT as IoT Stream
    participant FA as Faust
    participant M0 as M₀ Working
    participant SO as Stream Observer
    participant OR as Orchestrator
    participant PL as Planner
    participant CR as Critic
    participant TE as Tool Executor
    participant ACT as Control Plane

    IoT->>FA: sensor reading
    FA->>M0: Update sliding window
    FA->>SO: Window stats
    SO->>SO: Detect |x - μ| > 3σ
    SO->>OR: Anomaly event (zone_id, metric)
    OR->>PL: Goal: restore nominal state
    PL->>M0: Read live state
    PL->>PL: Propose action (e.g. adjust setpoint)
    PL->>CR: Action + rationale
    CR->>CR: Check policy (comfort, tariff, safety)
    alt Policy violation
        CR-->>OR: Reject + escalate to operator
    else Approved
        CR->>TE: Execute actuation
        TE->>ACT: MQTT / BACnet command
        ACT-->>TE: Ack + new state
        TE->>M0: Write observation
        TE-->>OR: Success + audit trail
    end
```



### 5.4 Memory Lifecycle Workflow

Background path: session data → durable knowledge.

```mermaid
flowchart LR
    subgraph Session
        A1[Dialogue turns]
        A2[Tool observations]
        A3[Stream pins]
    end

    subgraph MemoryManager["Memory Manager Jobs"]
        B1[context_budget_enforce]
        B2[importance_score]
        B3[reflect_and_consolidate]
        B4[graph_upsert]
    end

    subgraph Stores
        C1[M₁ Context]
        C2[M₂ Neo4j]
        C3[Community Summaries]
    end

    A1 & A2 & A3 --> B1 --> C1
    C1 --> B2
    B2 -->|promote| B3
    B3 --> B4 --> C2
    C2 -->|nightly job| C3
    C3 --> C2
```



---

## 6. Multi-Agent Orchestration

### 6.1 Agent Roles

```mermaid
flowchart TB
    ORCH[Orchestrator<br/><i>Routes tasks, enforces policies</i>]

    ORCH --> MM[Memory Manager<br/><i>Read/write all tiers</i>]
    ORCH --> PL[Planner<br/><i>Decompose goals, CoT</i>]
    ORCH --> SO[Stream Observer<br/><i>Anomaly + delta summaries</i>]

    PL --> TE[Tool Executor<br/><i>Idempotent side effects</i>]
    PL --> CR[Critic<br/><i>Faithfulness + policy</i>]

    CR -->|revise| PL
    CR -->|accept| OUT[Response / Action]
    MM -.->|context| PL
    MM -.->|evidence| CR
    SO -.->|M₀ pins| MM
```




| Agent               | Inputs                        | Outputs                   | Tools                                                                |
| ------------------- | ----------------------------- | ------------------------- | -------------------------------------------------------------------- |
| **Orchestrator**    | Query, stream events, session | Subgraph selection        | `route_task`, `set_policy`                                           |
| **Memory Manager**  | Query, agent state            | C_t, evidence set         | `core_append`, `archival_search`, `graph_traverse`, `pin`, `reflect` |
| **Planner**         | C_t, tool schemas             | Plan steps, sub-queries   | reasoning only                                                       |
| **Tool Executor**   | Approved actions              | Observations              | repo search, APIs, IoT control                                       |
| **Critic**          | Draft + evidence subgraph     | accept / revise / reject  | NLI check, policy engine                                             |
| **Stream Observer** | Faust windows                 | Anomaly events, summaries | statistical templates                                                |


### 6.2 LangGraph Control Flow

```mermaid
stateDiagram-v2
    [*] --> Orchestrator
    Orchestrator --> MemoryLoad: task accepted
    MemoryLoad --> Planner: C_t ready
    Planner --> ToolExec: needs external data
    ToolExec --> MemoryLoad: observation recorded
    Planner --> Critic: draft ready
    Critic --> Planner: revision needed
    Critic --> Emit: accepted
    Critic --> HumanGate: high-risk action
    HumanGate --> ToolExec: approved
    HumanGate --> Emit: rejected
    Emit --> [*]
```



### 6.3 Shared State Schema

```python
class CogOSState(TypedDict):
    messages: Annotated[list, add_messages]
    task_type: str                          # "qa" | "action" | "anomaly"
    working_memory: dict                      # M₀ handles
    context_bundle: list[dict]                # assembled M₁ content
    retrieved_evidence: list[dict]            # M₂ subgraph
    plan: list[str]
    tool_results: list[dict]
    critic_verdict: Optional[str]             # accept | revise | reject
    audit_trail: list[dict]
```

---

## 7. Graph-RAG Hybrid Retrieval

### 7.1 Retrieval Pipeline

```mermaid
flowchart TD
    Q[Query q] --> QU[Query Understanding<br/>entities + intent]
    QU --> VP[Vector Phase<br/>ANN top-N seeds S_v]
    QU --> GP[Graph Phase<br/>expand S_v → subgraph G_q]
    VP --> GP
    GP --> CS{Global question?}
    CS -->|Yes| CM[Community Summary Lookup]
    CS -->|No| FU[Fusion Rank λ-weighted]
    CM --> FU
    FU --> EP[Evidence Package<br/>nodes, edges, provenance]
    EP --> MM[Memory Manager → M₁]
```



### 7.2 Fusion Score


\text{score}(n) = \lambda_1 \cdot \text{sim}(q, n) + \lambda_2 \cdot \text{PageRank}_G(n) + \lambda_3 \cdot \text{recency}(n) + \lambda_4 \cdot \text{importance}(n)


### 7.3 Graph Schema (Neo4j)

```mermaid
erDiagram
    Document ||--o{ Chunk : CONTAINS
    Chunk ||--o{ Entity : MENTIONS
    Entity ||--o{ Entity : RELATES_TO
    Entity ||--o{ Service : MAPS_TO
    Service ||--o{ Service : DEPENDS_ON
    Event ||--o{ Service : AFFECTS
    IoTDevice ||--o{ IoTReading : EMITS
    IoTReading }o--|| Zone : LOCATED_IN
    AgentObservation ||--o{ Entity : REFERENCES
    Reflection ||--o{ AgentObservation : SUMMARIZES
```




| Node Label   | Key Properties                     |
| ------------ | ---------------------------------- |
| `Document`   | `uri`, `title`, `updated_at`       |
| `Chunk`      | `text`, `embedding`, `chunk_id`    |
| `Entity`     | `name`, `type`, `canonical_id`     |
| `Service`    | `name`, `repo`, `owner`            |
| `Event`      | `type`, `timestamp`, `severity`    |
| `IoTDevice`  | `device_id`, `protocol`            |
| `Reflection` | `text`, `importance`, `created_at` |


---

## 8. Data Ingestion Pipeline

### 8.1 Kafka Topic Map


| Topic                 | Producer      | Consumer       | Partition Key |
| --------------------- | ------------- | -------------- | ------------- |
| `raw.documents`       | Doc crawler   | Spark          | `tenant_id`   |
| `raw.code`            | Git webhook   | Spark          | `repo_id`     |
| `raw.logs`            | Log shipper   | Spark          | `service_id`  |
| `stream.iot`          | MQTT bridge   | Faust          | `device_id`   |
| `derived.entities`    | NER pipeline  | Neo4j loader   | `entity_id`   |
| `memory.observations` | Agents        | Memory service | `session_id`  |
| `audit.actions`       | Tool Executor | Audit store    | `trace_id`    |


### 8.2 Processing Split

```mermaid
flowchart LR
    subgraph Batch["Batch Path (Spark)"]
        B1[Documents]
        B2[Code AST chunks]
        B3[Structured logs]
    end

    subgraph Stream["Stream Path (Faust)"]
        S1[IoT telemetry]
        S2[Live agent events]
    end

    Batch --> EMB[Embedding Service]
    Stream --> WM[M₀ Working Memory]

    EMB --> NEO[(Neo4j M₂)]
    EMB --> VEC[Vector Index]

    WM --> SO[Stream Observer]
    SO --> AG[Agent Orchestrator]
```



### 8.3 Ingestion Guarantees


| Guarantee                   | Mechanism                                       |
| --------------------------- | ----------------------------------------------- |
| **At-least-once delivery**  | Kafka consumer groups + offset commits          |
| **Idempotent graph writes** | `MERGE` on `(source_uri, chunk_id)`             |
| **Ordering per entity**     | Partition by `device_id` / `service_id`         |
| **Backpressure**            | Consumer lag alerts; auto-scale Spark executors |


---

## 9. Target Use Cases

### 9.1 Enterprise Knowledge Graph

**Goal:** Reason over docs, codebases, and deployment logs with multi-hop relational queries.

```mermaid
flowchart TD
    Q["Query: Why did checkout latency spike<br/>after yesterday's release?"] --> R[Hybrid Retrieve<br/>checkout service + recent deploys]
    R --> T[Graph Traverse<br/>DEPENDS_ON upstream services]
    T --> L[Log community summary<br/>error patterns]
    L --> P[Planner synthesizes timeline]
    P --> C[Critic verifies<br/>entity names + edges exist]
    C --> A["Answer with provenance chain<br/>Deploy v2.3 → Service B timeout → checkout p99 ↑"]
```



**Demonstration metrics:** faithfulness ≥ 0.85, graph grounding ≥ 0.90.

### 9.2 Autonomous Smart Infrastructure

**Goal:** Detect anomalies and act within policy bounds in sub-second latency.

```mermaid
flowchart TD
    S[Zone temperature drift] --> D[Faust 3σ detection]
    D --> O[Stream Observer alert]
    O --> PL[Planner: reduce load / adjust setpoint]
    PL --> CR[Critic: comfort + tariff policy]
    CR --> ACT[Tool Executor → MQTT/BACnet]
    ACT --> M[Update M₀ + audit log]
```



**Demonstration metrics:** p99 actuation latency < 2s, zero policy violations in eval harness.

---

## 10. Technology Stack


| Layer               | Primary Choice                           | Alternatives                   |
| ------------------- | ---------------------------------------- | ------------------------------ |
| Agent orchestration | **LangGraph**                            | CrewAI, AutoGen                |
| LLM                 | Llama 3.x / Mistral (self-hosted)        | OpenAI, Anthropic API          |
| Graph DB            | **Neo4j 5.x** (native vector)            | Memgraph, FalkorDB             |
| Message bus         | **Apache Kafka**                         | Redpanda, Pulsar               |
| Batch processing    | **Spark Structured Streaming**           | Flink batch                    |
| Stream processing   | **Faust**                                | Flink streaming, Kafka Streams |
| Working memory      | **Redis Streams**                        | Flink keyed state              |
| Embeddings          | BGE-M3                                   | OpenAI text-embedding-3        |
| API                 | FastAPI                                  | —                              |
| Observability       | OpenTelemetry + Prometheus + Grafana     | —                              |
| Eval                | RAGAS + custom graph benchmarks          | —                              |
| Infrastructure      | Docker Compose (dev) → Kubernetes (prod) | —                              |


---

## 11. Implementation Roadmap

```mermaid
gantt
    title The Second Brain — Implementation Phases
    dateFormat  YYYY-MM-DD
    section Phase 0 — Foundation
    Monorepo + Docker Compose           :p0a, 2026-06-24, 14d
    Schemas + baseline LangGraph agent    :p0b, after p0a, 7d
    section Phase 1 — Ingestion → M₂
    Kafka + Spark embedding pipeline      :p1a, after p0b, 21d
    NER/RE + Neo4j loader                 :p1b, after p1a, 14d
    section Phase 2 — Memory Tiering
    Memory Manager + context budget       :p2a, after p1b, 21d
    Hybrid retrieval + reflection jobs    :p2b, after p2a, 14d
    section Phase 3 — Streaming M₀
    Faust IoT + Stream Observer           :p3a, after p2b, 14d
    section Phase 4 — Full Agent Graph
    Critic + Tool Executor + audit        :p4a, after p3a, 21d
    section Phase 5 — Benchmarks & Paper
    Enterprise + IoT eval harness         :p5a, after p4a, 28d
```



### Phase Checklist

- [ ] **Phase 0** — Repo scaffold, Docker Compose (Kafka, Neo4j, Redis), Pydantic schemas, OTEL
- [ ] **Phase 1** — Ingestion pipelines, embedding service, Neo4j hybrid index, community summaries
- [ ] **Phase 2** — Memory Manager, R(m|q,t) retrieval, promotion/demotion, reflection consolidation
- [ ] **Phase 3** — Faust streaming, M_0 Redis, Stream Observer, anomaly → agent trigger
- [ ] **Phase 4** — Full LangGraph loop, Critic, human approval gate, tool registry
- [ ] **Phase 5** — Benchmarks, ablation study, paper draft, open-source release

---

## 12. Evaluation & SLOs

### 12.1 Quality Metrics


| Metric                 | Formula / Method                        | Target |
| ---------------------- | --------------------------------------- | ------ |
| **Faithfulness**       | NLI entailment: claims ⊆ evidence       | ≥ 0.85 |
| **Answer Relevance**   | RAGAS `answer_relevancy`                | ≥ 0.80 |
| **Graph Grounding**    | Cited nodes/edges exist in ground truth | ≥ 0.90 |
| **Hallucination Rate** | Unsupported entity mentions             | ≤ 5%   |
| **Action Correctness** | IoT actions vs oracle policy            | ≥ 95%  |



F = \frac{1}{N}\sum_{i=1}^{N} \mathbb{1}\left[\forall c \in \text{claims}(a_i), \exists e \in E_i: \text{entails}(e, c)\right]


### 12.2 Latency SLOs


| Path                        | p50     | p99     |
| --------------------------- | ------- | ------- |
| QA end-to-end               | < 2s    | < 5s    |
| Hybrid retrieval only       | < 100ms | < 300ms |
| IoT anomaly → actuation     | < 500ms | < 2s    |
| Context assembly            | < 50ms  | < 200ms |
| Kafka consumer lag (stream) | —       | < 1s    |


### 12.3 Ablation Matrix (Paper)


| Config            | M₀  | M₁        | M₂ Hybrid   | Multi-Agent | Expected Δ Faithfulness |
| ----------------- | --- | --------- | ----------- | ----------- | ----------------------- |
| Flat RAG baseline | ✗   | naive     | vector only | ✗           | —                       |
| + Graph           | ✗   | naive     | ✓           | ✗           | +5–10%                  |
| + Tiered memory   | ✓   | MemGPT    | ✓           | ✗           | +5–8%                   |
| **Full CogOS**    | ✓   | optimized | ✓           | ✓ + Critic  | +10–15%                 |


---

## 13. Repository Layout

```
Second_Brain/
├── docs/
│   └── ARCHITECTURE_WORKFLOW.md      ← this document
├── ingestion/
│   ├── kafka/                        # Producers, topic configs
│   ├── spark/                        # Batch/stream jobs
│   └── faust/                        # IoT stream workers
├── memory/
│   ├── tiers/                        # M₀, M₁, M₂ implementations
│   ├── retrieval/                    # Hybrid graph-vector search
│   └── consolidation/                # Reflection + promotion jobs
├── agents/
│   ├── graph/                        # LangGraph state machine
│   ├── roles/                        # MM, Planner, Critic, etc.
│   └── tools/                        # Tool registry
├── graph/
│   ├── schema/                       # Neo4j constraints, indexes
│   └── loader/                       # MERGE upsert logic
├── api/
│   └── gateway/                      # FastAPI entrypoint
├── eval/
│   ├── benchmarks/                   # Enterprise QA, IoT sim
│   └── metrics/                      # RAGAS + custom scorers
├── infra/
│   ├── docker-compose.yml
│   └── k8s/                          # Production manifests
└── observability/
    └── otel/                         # Tracing + audit
```

---

## Appendix A — Decision Log


| Decision          | Choice                      | Rationale                                                 |
| ----------------- | --------------------------- | --------------------------------------------------------- |
| Orchestrator      | LangGraph over CrewAI       | Stateful graphs, checkpointing, fine-grained control flow |
| Graph store       | Neo4j                       | Mature vector index, Cypher, GraphRAG community support   |
| Stream split      | Spark (batch) + Faust (IoT) | Right tool for throughput vs latency                      |
| Critic placement  | Post-planner gate           | Blocks unsafe actions before Tool Executor                |
| Human-in-the-loop | High-risk actuation only    | Balance autonomy and safety                               |


---

## Appendix B — References

- Packer et al., *MemGPT: Towards LLMs as Operating Systems* (2023)
- Park et al., *Generative Agents: Interactive Simulacra of Human Behavior* (2023)
- Edge et al., *From Local to Global: A Graph RAG Approach to Query-Focused Summarization* (2024)
- Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models* (2023)

---

*Document version: 1.0 · Project: The Second Brain · Last updated: 2026-06-24*