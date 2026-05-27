# 3-Month Plan: Learning Modern AI (LLMs, RAG, Agentic Coding) via ICD-10-CM → ICD-11 Foundation Mapping

**Audience:** experienced Python developer, new to LLMs
**Time budget:** ~10 hours/week (≈120 hours total)
**Outcome:** working prototype that maps selected ICD-10-CM chapters to ICD-11 Foundation, plus solid conceptual understanding of LLMs, RAG, and agents
**Target date range:** 12 weeks, starting the week of May 26, 2026

---

## Why ICD-10-CM → ICD-11 Foundation is a great learning vehicle

The mapping problem stresses every layer of a modern AI system:

- **LLM reasoning** — many ICD-10-CM concepts split, merge, or get re-parented in ICD-11.
- **RAG** — ICD-11 Foundation has ~85,000 entities with rich metadata (definitions, inclusions, exclusions, synonyms, multi-parent hierarchy). You cannot fit it in context, so retrieval is essential.
- **Structured output** — mappings are typed objects with confidence, rationale, post-coordinated extensions.
- **Tools / agents** — looking up parents, children, exclusions, and existing partial maps are natural tool calls.
- **Evaluation** — there are known partial gold mappings (WHO, UMLS) so you can measure precision/recall honestly.
- **Domain stretch** — post-coordination in ICD-11 (extension codes for laterality, anatomy, severity, temporality, agent) forces you beyond "pick the best candidate" into compositional mapping.

You will not try to map all 22 chapters. The plan organizes work **by chapter**, piloting on Chapter 1, then deliberately picking three more chapters that each break the previous design.

### Pilot chapters and what each forces you to learn

| Chapter | ICD-10-CM range | Why this chapter |
|---|---|---|
| **Ch. 1 — Certain infectious & parasitic diseases** | A00–B99 | Clean taxonomy, moderate size. Baseline pilot. |
| **Ch. 5 — Mental, behavioral & neurodevelopmental disorders** | F01–F99 | Heavily restructured in ICD-11; tests semantic alignment, not lexical match. |
| **Ch. 19 — Injury, poisoning, external causes** | S00–T88 | Post-coordination heavy in ICD-11; compositional mapping. |
| **Ch. 21 — Factors influencing health status (Z-codes)** | Z00–Z99 | Different shape in ICD-11 (Ch. 24); tests structural mismatch. |

---

## High-level shape

| Phase | Weeks | Theme | Project state at end |
|---|---|---|---|
| **1. Foundations** | 1–4 | LLM fluency, embeddings, first end-to-end map | Two-stage retrieve+verify pipeline working on Ch. 1 |
| **2. RAG depth + evaluation** | 5–8 | Production-grade retrieval, eval harness, hard chapters | Pipeline working on Ch. 1 + Ch. 5 + Ch. 19, with rigorous eval |
| **3. Agentic systems + capstone** | 9–12 | Tool-using agents, observability, full writeup | Multi-agent mapper across 4 chapters with results dashboard |

---

## Repo and tooling conventions

Set these up in Week 1 and keep them stable:

- **Repo:** `icd-mapper/` — one Git repo, branch per phase, tagged releases at end of each week.
- **Layout:** `src/` (modules), `notebooks/` (exploration), `eval/` (gold sets + scripts), `data/` (raw + processed ICD files, git-ignored), `prompts/` (versioned `.md` or `.toml`), `notes/` (concept notes).
- **Python:** 3.12, managed with `uv`; `ruff` for lint; `pytest` for tests.
- **LLM:** Anthropic Claude (primary), OpenAI as alternate. Track cost in every script.
- **Embeddings:** `text-embedding-3-large` baseline + at least one biomedical model (`MedCPT` or `BGE-M3`).
- **Vector store:** Chroma (week 3), Qdrant (week 5+).
- **Structured outputs:** Pydantic + Instructor or Anthropic native tool use.
- **Observability:** Langfuse or LangSmith from week 11; before that, a simple JSONL trace logger.
- **Ontology tooling:** `pyhornedowl`, `oaklib` (Ontology Access Kit); the `owl-mcp` MCP server you already have is well-suited for ICD-11 axiom queries.
- **Discipline:** every week ends with (a) a tagged commit, (b) a one-page note in `notes/wkNN.md`, (c) a metric or artifact you can point to.

---

# Phase 1 — Foundations (Weeks 1–4)

## Week 1 — LLM mental model + ICD landscape

**Objectives**

- Have a working mental model of how LLMs are trained, inferenced, and priced.
- Understand the structural differences between ICD-10-CM, ICD-10 (WHO), ICD-11 Foundation, and ICD-11 MMS.

**Concepts (~4 hrs)**

- Tokenization, attention at a high level, context windows, sampling parameters (temperature, top-p), instruction tuning vs. RLHF, why LLMs hallucinate.
- Pricing model: input vs. output tokens, prompt caching.
- ICD-10-CM (CDC/NCHS), ICD-10 (WHO), ICD-11 Foundation (multi-parent semantic network), ICD-11 MMS (tabular linearization), post-coordination, the ICD-11 API (`id.who.int`).

**Hands-on (~6 hrs)**

- Set up `icd-mapper/` repo with `uv`, `ruff`, `pytest`.
- Provision Anthropic + OpenAI API keys; store in `.env`; never commit.
- Pull and cache: full ICD-10-CM 2026 release (CSV); full ICD-11 Foundation via the WHO API for Chapters 1, 6, 22, 24 (the rough ICD-11 equivalents of the four pilot chapters).
- 10 first-contact API calls to Claude with varying parameters; note the cost and latency.

**Deliverable**

- `notebooks/wk01_first_contact.ipynb`
- `data/icd10cm_ch01.csv`, `data/icd11_foundation_ch01.json`
- `notes/wk01_llm_mental_model.md` (1 page, your own words)

**Resources**

- Karpathy, "Intro to Large Language Models" (1-hr talk).
- Anthropic docs: API reference, prompt caching, pricing.
- WHO ICD-11 Reference Guide; ICD-11 API getting-started.
- CDC ICD-10-CM 2026 release files.

---

## Week 2 — Prompting, structured outputs, function calling

**Objectives**

- Reliably get typed objects back from an LLM.
- Build a baseline mapper that uses *only* the LLM's prior knowledge.

**Concepts (~4 hrs)**

- Zero-shot vs few-shot vs CoT; when each helps.
- Structured outputs: JSON schema, Pydantic models, Anthropic tool use as a JSON-output mechanism, `Instructor`.
- System prompts, role prompting, prompt versioning.
- "Eval-driven prompting": never tune a prompt without a metric.

**Hands-on (~6 hrs)**

- Define Pydantic types: `ICD10CMCode`, `ICD11Candidate`, `MappingProposal(candidates: list[ICD11Candidate], chosen: ICD11Candidate, rationale: str, confidence: float)`.
- Write `mapper_v0.py`: input one ICD-10-CM code+title, output `MappingProposal` from LLM knowledge alone.
- Sample 50 codes from Ch. 1 and run zero-shot, few-shot (5 in-context examples), and CoT variants. Manually grade.

**Deliverable**

- `src/mapper_v0.py` + `prompts/v0_*.md`
- `eval/wk02_baseline.csv` — 50 codes × 3 prompt strategies
- `notes/wk02_prompting.md` — which strategy won and why, with token costs

**Resources**

- Anthropic "Prompt engineering" guide and prompt library.
- `Instructor` library docs.
- Lilian Weng, "Prompt Engineering" (blog post).

---

## Week 3 — Embeddings + semantic search

**Objectives**

- Understand embedding spaces and what they capture.
- Stand up a vector store of ICD-11 Foundation entries and query it.

**Concepts (~3 hrs)**

- Dense vs sparse representations; cosine similarity; the geometry intuition.
- Choosing embedding models — MTEB leaderboard, dimensionality vs. quality, latency.
- Biomedical embedding models: MedCPT, BGE-M3, S-PubMedBert.
- ANN indexes (HNSW), exact vs approximate search.

**Hands-on (~7 hrs)**

- Embed all ICD-11 Foundation entries in the Ch. 1 equivalent branch using `text-embedding-3-large`; store in Chroma with metadata (entity_id, title, definition, synonyms, parents).
- Build `retriever_v0.py` — given an ICD-10-CM title, return top-k candidates.
- Compute **recall@5, @10, @20** by checking whether at least one plausible match appears (use the 50 hand-graded examples from week 2 as a tiny gold set).
- Repeat with one biomedical embedding model; compare.

**Deliverable**

- `src/retriever_v0.py`
- `notebooks/wk03_embedding_compare.ipynb` with recall numbers
- `notes/wk03_embeddings.md`

**Resources**

- HuggingFace MTEB leaderboard.
- OpenAI embeddings guide.
- Chroma quickstart; intro to HNSW.

---

## Week 4 — First end-to-end pipeline for Chapter 1

**Objectives**

- Combine retriever + LLM verifier into a real RAG pipeline.
- Have a runnable mapper for an entire chapter.

**Concepts (~3 hrs)**

- The RAG pattern: retrieve → augment → generate.
- Two-stage retrieval+verification; when verification helps vs. when it just re-ranks noise.
- Score calibration and confidence.

**Hands-on (~7 hrs)**

- `pipeline_v1.py`: retrieve top-20 ICD-11 candidates → LLM picks best with rationale and confidence → emits `MappingProposal`.
- Run on **all of ICD-10-CM Chapter 1** (~1,100 codes); parallelize with `asyncio` and bounded concurrency.
- Output: `outputs/ch01_v1.csv` with `(icd10cm, top_candidates, chosen_icd11, rationale, confidence, cost_usd)`.
- Manually review 50 random rows; categorize errors (missed in retrieval, wrong choice by verifier, structural mismatch, post-coord needed).

**Deliverable**

- `src/pipeline_v1.py`
- `outputs/ch01_v1.csv`
- `notes/wk04_error_taxonomy_v1.md` — first error taxonomy, the document you will revisit every later week.

**Phase 1 retro (30 min):** what surprised you about LLM behavior on real codes? Where is the retriever the bottleneck vs. the verifier?

---

# Phase 2 — RAG depth + evaluation (Weeks 5–8)

## Week 5 — Production-grade retrieval

**Objectives**

- Move beyond naive embedding search.
- Exploit ICD-11's rich structure (definition, inclusions, exclusions, synonyms, multi-parent).

**Concepts (~3 hrs)**

- Chunking strategies: semantic, hierarchical, parent-child, contextual chunks.
- Multi-vector retrieval: separate vectors for title, definition, synonyms; aggregate at query time.
- Hybrid search: BM25 + dense, reciprocal rank fusion.
- Metadata filtering (e.g., restrict to a chapter or branch).

**Hands-on (~7 hrs)**

- Switch storage to Qdrant (or pgvector) to get hybrid search.
- Build three retrievers: `dense_only`, `bm25_only`, `hybrid_rrf`.
- Add multi-vector for ICD-11 entries.
- Ablation: each retriever × {dense embeddings, biomedical embeddings} on Ch. 1.

**Deliverable**

- `src/retrievers/` with a clean interface.
- `eval/wk05_retrieval_ablation.md` — table of recall@k across all variants.

---

## Week 6 — Query understanding, HyDE, rerank, and introducing Chapter 5

**Objectives**

- Improve queries themselves, not just the index.
- See how a chapter with heavy semantic restructuring exposes weaknesses.

**Concepts (~3 hrs)**

- Query rewriting; multi-query expansion; RAG-Fusion.
- HyDE (Hypothetical Document Embeddings) — let an LLM imagine the target description first, then embed that.
- Cross-encoder rerankers (Cohere Rerank, Voyage); when reranking saves you and when it doesn't.
- Self-querying retrievers (LLM emits structured filters).

**Hands-on (~7 hrs)**

- Implement HyDE: LLM drafts a "what would the ICD-11 entry look like?" passage from an ICD-10-CM code, then embed and retrieve.
- Add a cross-encoder reranker on top-50 → top-10.
- **Onboard Ch. 5 (F-codes).** Pull ICD-11 Ch. 6 (Mental, behavioural, or neurodevelopmental disorders). Run the full pipeline on a 100-code sample.
- Manual error analysis: how does Ch. 5 fail differently from Ch. 1?

**Deliverable**

- `src/queryops/hyde.py`, `src/rerank.py`
- `outputs/ch05_v1_sample.csv`
- `notes/wk06_ch5_error_analysis.md`

**Resources**

- Anthropic "Contextual Retrieval" blog post.
- HyDE paper (Gao et al., 2022).
- Cohere Rerank docs.

---

## Week 7 — Evaluation methodology

**Objectives**

- Build an evaluation harness you trust enough to ship numbers in a paper.
- Have a small but real gold set.

**Concepts (~3 hrs)**

- Retrieval metrics: precision, recall, F1, MRR, NDCG.
- End-to-end metrics: top-1 accuracy, top-k accuracy, calibrated confidence.
- LLM-as-judge: when valid, when biased; cost vs. human review.
- `ragas` and `DeepEval`; their pitfalls.
- Gold-set construction: stratified sampling, inter-rater agreement, the cost of being honest.

**Hands-on (~7 hrs)**

- Build an `eval/` harness: takes a gold CSV `(icd10cm, expected_icd11_set, rationale)` and a pipeline output, returns metrics.
- Build a tiny Gradio or Streamlit review UI for you to annotate 100 cases from Ch. 1 + 100 from Ch. 5 as gold.
- Source silver labels where available (WHO partial mappings, UMLS cross-walks if licensed).
- Integrate `ragas` for retrieval+generation metrics; cross-check against your custom metrics.

**Deliverable**

- `eval/harness.py`, `eval/gold/ch01.csv`, `eval/gold/ch05.csv`
- `eval_report_v1.md` — first honest numbers: top-1 accuracy, recall@10, calibration, by chapter.

---

## Week 8 — Compositional mapping: Chapter 19 and post-coordination

**Objectives**

- Handle ICD-11's post-coordination, which has no analogue in ICD-10-CM mapping as a single-target lookup.

**Concepts (~3 hrs)**

- ICD-11 stem codes + extension codes for laterality, anatomy, severity, temporality, causal agent.
- Compositional / decompositional mapping: a single ICD-10-CM code may map to a *cluster* in ICD-11.
- Structured generation with constrained outputs.
- This is also a natural moment to use `owl-mcp`: ICD-11 ships as an ontology and the axioms describe legal post-coordination axes.

**Hands-on (~7 hrs)**

- Define `PostCoordinatedMapping(stem_icd11: str, extensions: dict[axis, code])`.
- Build a `decomposer` that proposes stem + extensions from an ICD-10-CM code like `S72.001A`.
- Use `owl-mcp` (or OAK) to validate that proposed extensions are allowed axes for the chosen stem.
- Run on 100 sampled Ch. 19 codes; document failure modes.

**Deliverable**

- `src/decomposer.py`
- `outputs/ch19_v1_sample.csv`
- `notes/wk08_postcoord.md`

**Phase 2 retro:** which retrieval move bought the most accuracy? Which chapter still scares you?

---

# Phase 3 — Agents + capstone (Weeks 9–12)

## Week 9 — Agent fundamentals

**Objectives**

- Build your first tool-using agent.
- Understand when an agent is the right tool and when a plain chain is fine.

**Concepts (~4 hrs)**

- Anthropic's "Building Effective Agents" essay — the workflow vs. agent distinction.
- ReAct loop; tool definitions; tool-call schema; scratchpad; loop termination.
- Failure modes: loops, runaway costs, hallucinated tool calls.
- Frameworks survey: Claude Agent SDK, LangGraph, AutoGen, CrewAI; pick one (Claude Agent SDK or LangGraph recommended).

**Hands-on (~6 hrs)**

- Define tools:
  - `search_icd11(query, branch=None) -> list[Entity]`
  - `get_icd11_entity(id) -> Entity`
  - `get_parents(id) / get_children(id)`
  - `get_postcoord_axes(id)`
  - `lookup_existing_mapping(icd10_code)` (WHO/UMLS silver maps if available)
  - `search_pubmed(term)` (optional)
- Build a single-agent ReAct mapper that uses these tools.
- Run on 20 hard cases from Ch. 5 and Ch. 19; inspect traces.

**Deliverable**

- `src/agents/mapper_agent_v1.py`
- `outputs/wk09_hard_cases_traces.jsonl`
- `notes/wk09_when_agents_help.md`

**Resources**

- Anthropic, "Building Effective Agents".
- Claude Agent SDK docs.
- LangGraph quickstart.

---

## Week 10 — Multi-agent design (with skepticism)

**Objectives**

- Build a multi-agent pipeline.
- **Honestly** test whether it beats Phase 2's RAG pipeline.

**Concepts (~3 hrs)**

- Orchestrator-worker pattern; critic / verifier loops; debate.
- Why multi-agent often makes things worse: latency, cost, error propagation, prompt drift.
- The Anthropic stance: prefer the simplest thing that works.

**Hands-on (~7 hrs)**

- Architecture: Retriever-Mapper proposes a `MappingProposal` → Ontology Critic uses `owl-mcp` to check structural consistency (e.g., exclusion notes, sibling plausibility) → Coordinator finalizes or sends back.
- Run head-to-head vs. Week 7 pipeline on all Ch. 1 + Ch. 5 gold sets.
- Write up: did agents help? On which case classes?

**Deliverable**

- `src/agents/multi_agent_pipeline.py`
- `eval_report_v2.md` with head-to-head.
- `notes/wk10_did_agents_actually_help.md`

---

## Week 11 — Productionization, observability, scaling

**Objectives**

- Make the pipeline operable: cached, observable, parallel, cheap.

**Concepts (~3 hrs)**

- Prompt caching (Anthropic) and response caching.
- Observability: Langfuse / LangSmith / Helicone; trace, span, evaluator, dataset.
- Parallelism with `asyncio` and concurrency limits; rate-limit handling; retry/backoff.
- Prompt versioning and regression testing.

**Hands-on (~7 hrs)**

- Instrument with Langfuse.
- Add prompt caching for the long ICD-11 context blocks (where applicable).
- Parallelize across chapters; benchmark throughput and cost per 1k codes.
- Run the **full pipeline on Ch. 1, Ch. 5, Ch. 19, Ch. 21**.

**Deliverable**

- `outputs/final/ch01.csv, ch05.csv, ch19.csv, ch21.csv`
- `notes/wk11_cost_and_throughput.md`

---

## Week 12 — Capstone: evaluation, dashboard, writeup

**Objectives**

- Ship a defensible final deliverable.
- Be able to answer: how good is it, where does it fail, what would it take to scale to 22 chapters?

**Concepts (~2 hrs)**

- Error taxonomy revisited; the difference between *mappable* and *unmappable* cases.
- Honest reporting; calibration plots.

**Hands-on (~8 hrs)**

- Final eval across all four chapters against gold + silver sets.
- Build a results dashboard (the `data:build-dashboard` skill is perfect here) — filterable by chapter, confidence band, error class.
- Write a 10-page summary doc covering: problem, approach, results, error taxonomy, lessons, what's needed to scale.
- Tag `v1.0` in the repo.

**Deliverable**

- `report/final_report.md` (or `.docx`)
- `dashboards/icd_mapping.html`
- Tagged repo release with reproducible README.

**Final retro:** what would you build differently from scratch? Which chapter would be hardest to extend to?

---

## Risks and how to mitigate them

| Risk | Mitigation |
|---|---|
| Spending Week 1–2 wrestling with WHO ICD-11 API quotas | Cache aggressively to disk on first pull; treat the API as build-time only after that. |
| Building a fancier system without measuring | Lock the eval harness in Week 7 and re-run it after every change. |
| Multi-agent complexity creep | Treat Week 10 as a *test* of multi-agent; be willing to keep the simpler Phase 2 pipeline. |
| Hallucinated ICD-11 codes | Always resolve LLM-proposed codes through `get_icd11_entity` before accepting them. |
| Gold set is too small to trust | Pre-commit to ≥100 cases per chapter; use stratified sampling across sub-blocks. |
| Cost overrun | Add a per-script cost ceiling and a daily budget tracker in Week 4 (not Week 11). |

---

## Suggested weekly rhythm

- **Mon (1 hr):** read concept materials, take notes.
- **Tue–Thu (6 hrs):** hands-on, in two- to three-hour blocks.
- **Fri (2 hrs):** writeup, commit, tag, update `notes/wkNN.md`.
- **Sat (1 hr, optional):** read one paper or watch one talk that connects to next week.

---

## Anchor reading list (curate as you go)

- Karpathy — *Intro to LLMs* (talk).
- Anthropic — *Building Effective Agents*; *Contextual Retrieval*; Prompt Engineering guide.
- Eugene Yan — *Patterns for Building LLM-based Systems & Products*.
- Lilian Weng — *Prompt Engineering*; *LLM Powered Autonomous Agents*.
- Gao et al. — *Precise Zero-Shot Dense Retrieval without Relevance Labels* (HyDE).
- Es et al. — *RAGAS: Automated Evaluation of Retrieval Augmented Generation*.
- WHO — *ICD-11 Reference Guide*; ICD-11 API docs.
- AMIA / JAMIA papers on terminology mapping (e.g., SNOMED–ICD; ICD-10 to ICD-11 pilots).

---

## What "done" looks like at week 12

A repo at `v1.0` that, on a fresh checkout, can:

1. Pull source terminologies into `data/`.
2. Build retrieval indexes for Ch. 1, 5, 19, 21.
3. Run a multi-agent (or carefully chosen simpler) mapping pipeline end to end.
4. Reproduce `eval_report_final.md` showing top-1 / top-5 accuracy, calibration, and error taxonomy on a gold set you constructed.
5. Open `dashboards/icd_mapping.html` and let a reviewer browse the results by chapter and error class.

And, more importantly: you can explain to another engineer *why* each component is there, what you tried that didn't work, and what you'd change.
