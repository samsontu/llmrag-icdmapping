# Plan: Learning Modern AI (RAG, Structured Output, Agents, MCP) via ICD-10-CM → ICD-11 Mapping

- **Audience:** experienced Python developer and ICD-11 specialist, new to building with LLMs
- **Time budget:** ~10 hours/week, 13 lessons, Nov 9, 2026 – Feb 21, 2027 (away Dec 24 – Jan 7)
- **Companion course:** the "Course" doc in the *AI learning* Claude project has the readings, practice and step-by-step build for every lesson. This file is the repo's version of the same plan: what gets built, where it lives, and when it is done.
- **Revision:** Nov 8, 2026. Supersedes the May 2026 draft (Chroma/Qdrant, hand-only gold set, single-target mapping). The `.docx` beside this file is generated from this markdown by `scripts/build_plan_docx.py`; edit the markdown, then rerun the script.

---

## The pipeline this repo builds

The approach is **Foundation first**: map the source to the best Foundation entity, derive the MMS target from it, then use postcoordination to express what the derived stem loses, and to compose a target when no Foundation entity exists.

| Step | Who does it | Module |
|---|---|---|
| 1. Retrieve Foundation candidates for an ICD-10-CM code + title | retriever (BM25 + dense, rerank) | `retrievers/`, `rerank.py` |
| 2. Choose Foundation entities, or say none fits | **Claude** (judgement) | `pipeline.py` |
| 3. Derive the MMS stem (the entity itself, an ancestor, or a residual) | **ICD-API** `mms/lookup` (deterministic) | `icd11_client.mms_lookup` |
| 4. Branch on the result (below) | pipeline | `pipeline.py`, `postcoord.py` |
| 5. Validate any cluster string | **ICD-API** `codeinfo` / `describe` | `icd11_client.codeinfo` |
| 6. Emit the mapping with its `target_type` | SSSOM rows + cluster | `sssom.py` |

The branch in step 4 sets `MappingProposal.target_type`:

| Situation after steps 2–3 | What happens | `target_type` |
|---|---|---|
| The Foundation entity is itself an MMS category | Done: the derived code is the target. | `foundation_is_mms` |
| The Foundation entity aggregates into another MMS entity (ancestor or residual) | Claude fills the stem's allowed axes **to express the Foundation entity**, plus any detail the CM code adds; the API validates the cluster. | `aggregated_postcoordinated` |
| …but no allowed axis expresses the difference | Keep the bare stem and record what was lost. | `aggregated_detail_lost` |
| No Foundation entity fits | Claude composes a cluster from candidate stems (`/`) and extension codes (`&`); the API validates it. | `composed` |
| Nothing in ICD-11 represents it | Decline. | `none` |

Claude never generates an MMS code: stems come from the linearization, axis values from each stem's `postcoordinationScale`, and every cluster is validated by the API.

**CodeFusion as a cluster proposer.** WHO's [CodeFusion](https://icd.who.int/docs/codefusion/en/user-guide/) (local copy: `/Users/tu/Downloads/codefusion_osx-x64`, version 1.1.1) matches phrases to ICD-11 and, with source `MMS`, reports postcoordination combinations (MatchType `PostCoordinationCombination`). `src/icd_mapper/codefusion.py` runs it in batch per chapter and caches the parsed output. Two modes, both run and compared:

- **default** (`useFreePostcoordinationMatching=false`): only the axes the classification suggests for an entity are tried.
- **free** (`useFreePostcoordinationMatching=true`): CodeFusion "tries to find any postcoordination combination"; it can match precoordinated source concepts only expressible as clusters (MatchLevel `GoodMatchWithFreePostcoordination`), at the cost of noisier proposals.

In the aggregated and composed branches, CodeFusion's clusters are passed to Claude as candidates alongside the stem's allowed axes. Claude accepts, edits or rejects them; `codeinfo` validates whatever is chosen; `MappingProposal.cluster_source` records where it came from (`claude`, `codefusion_default`, `codefusion_free`, or `codefusion_*+claude`). CodeFusion is never trusted unvalidated, and its Foundation URI is checked against the chosen entity.

## Chapter pilots

The work is organized by ICD-10-CM chapter. Each new chapter is chosen to break the previous design.

| ICD-10-CM chapter | Range | ICD-11 home | What it forces you to learn | Lessons |
|---|---|---|---|---|
| 1 Infectious & parasitic | A00–B99 | 01 | Baseline: clean taxonomy, infectious-agent extensions | 1–5 |
| 5 Mental & behavioural | F01–F99 | 06 | Heavy restructuring: semantic, not lexical, alignment | 6–8 |
| 19 Injury & poisoning | S00–T88 | 22 (+23) | Postcoordination: laterality, encounter, fracture type | 9–10 |
| 21 Factors influencing health status | Z00–Z99 | 24 | Structural mismatch; scaling and cost | 11–12 |

## Gold and silver data: the WHO 2026 mapping table

`data/raw/10To11MapToOneCategory.xlsx` (WHO 2026 release; the local copy differs only in formatting) gives every WHO ICD-10 category its ICD-11 **Foundation URI**, **MMS URI** and **MMS code or cluster**. `src/icd_mapper/who_map.py` loads it (`load_10to11`) and bridges ICD-10-CM to it (`who_ancestor_for_cm`): S72.001A → S72.0, match level `ancestor`.

- 11,243 category rows. `load_10to11` labels each with `silver_target_type`: 4,081 `foundation_is_mms`, 351 `aggregated_postcoordinated` (the table gives a cluster), 6,731 `aggregated_bare` (aggregated, but the table gives only a residual or bare stem) and 80 `none`.
- **The table rarely postcoordinates.** All 351 clusters sit on aggregated rows, and they are only about 5% of the 7,082 aggregated rows; 5,403 point to residual categories and 1,427 to bare stems. So the table is good silver for `foundation_is_mms` rows, but **not** for postcoordinating aggregated targets: every `aggregated_bare` row in the gold set needs review, ending as `aggregated_postcoordinated` (with a cluster) or `aggregated_detail_lost`. This is where the pipeline can add most over the table.
- For an `exact` CM match the table target is a strong silver label. For an `ancestor` match it is the target of the WHO parent, so the CM-specific detail (laterality, 7th-character encounter, subtype) is what the Foundation choice or postcoordination must add.
- **The bridge vs the method.** Chaining ICD-10-CM → WHO ICD-10 → the WHO table to build silver labels resembles the map-chaining in Xu, Fung and Bodenreider ([MEDINFO 2021](https://ebooks.iospress.nl/pdf/doi/10.3233/SHTI220039)). The *mapping method* here is different: they map to MMS first, fall back to the Foundation when no MMS category matches, and postcoordinate only sources with neither. This project maps to the Foundation first, derives MMS, and postcoordinates both aggregated Foundation targets and sources with no Foundation target. Compare the two orders in the Lesson 13 write-up.
- Gold rows are silver rows **you have reviewed**. Never overwrite the silver columns; add reviewed and acceptable alternatives beside them.

**Gold CSV** (`eval/gold/chNN.csv`): `icd10cm_code, icd10cm_title, chapter, who_icd10_code, match_level, silver_foundation_uri, silver_mms_cluster, silver_target_type, foundation_uris, acceptable_foundation_uris, mms_cluster, target_type, lost_detail, stratum, split, note`.
Strata: exact vs ancestor match × `silver_target_type` × residual. Seek out `composed` cases on purpose (CM combination codes are a good source); the table cannot supply them. 30% `heldout`, stratified, untouched until Gates 2 and 3.
**Leakage:** CM and WHO titles often equal Foundation titles or synonyms. Report the exact-title subset separately.

## Metrics (every run)

1. **Foundation:** recall@1/5/10, MRR, partial credit for parent/child entities.
2. **MMS stem:** accuracy of the derived stem; count separately the cases where a wrong Foundation entity derives the right stem (it hides selection errors).
3. **Target path:** accuracy of `target_type` (did the pipeline take the right branch?).
4. **Cluster** (from Lesson 4 for aggregated targets; Lesson 9 for composed ones): exact match and per-axis accuracy, also broken down by `cluster_source` (Claude alone, CodeFusion default, CodeFusion free, combined).
Every metric is reported per `target_type`. Plus null precision/recall, cost per 1k codes and latency, broken down by chapter and stratum. Every run appends to `reports/results.csv`.

---

## Repo conventions

- **Package:** everything under `src/icd_mapper/`. Python 3.12, `uv`, `ruff`, `pytest` (respx for HTTP mocks).
- **LLM:** Claude via `llm_clients.py` (OpenAI wrapper kept as an optional comparison). Cost logged on every call; a hard budget cap from Lesson 4 (`DAILY_LLM_BUDGET_USD`).
- **ICD-API:** release `2026-01` (matches the mapping table). Disk-cached; treat the API as build-time after the first harvest.
- **Store:** DuckDB for vectors (`vss`, HNSW, cosine) and BM25 (`fts`), rebuilt from parquet at start-up (HNSW persistence is experimental).
- **CodeFusion:** `CODEFUSION_PATH` in `.env`; version `2026`, source `MMS`; run once per chapter per mode and cache to `data/codefusion/chNN_{default,free}.parquet`. It is a desktop binary, so these runs happen on your Mac.
- **Embeddings:** `BAAI/bge-m3`, `cambridgeltl/SapBERT-from-PubMedBERT-fulltext`, plus a general baseline; an API embedding model is optional.
- **Prompts:** versioned files in `prompts/`; never change a prompt without re-running the gold set.
- **Weekly discipline:** a tagged commit, `notes/wkNN.md` (one page), and one number or artifact you can point to.
- **Claude Code:** scaffold plumbing freely; write retrieval, scoring and prompt logic yourself (see `CLAUDE.md` if you add one).

## Target layout (grows lesson by lesson)

```
src/icd_mapper/
  config.py  types.py  llm_clients.py  icd10cm_loader.py     # existing
  icd11_client.py      # W0  Foundation + mms_lookup, postcoordination axes, codeinfo
  who_map.py           # W0  WHO 10->11 table loader + ICD-10-CM bridge
  codefusion.py        # W0  run WHO CodeFusion in batch; parse clusters (default/free)
  mapper_v0.py         # L1  LLM-only baseline (structured output)
  harvest.py           # L2  walk Foundation chapter roots, cache mms_lookup per entity
  embed.py             # L2  embedding models
  store.py             # L3  DuckDB: vectors + metadata (+ FTS in L6)
  retrievers/          # L3  dense; L6 lexical, fuse (RRF), multi-vector
  pipeline.py          # L4  retrieve -> choose Foundation -> derive MMS -> branch
  budget.py            # L4  cost cap and daily tracker
  queryops/hyde.py     # L8  HyDE query expansion
  rerank.py context.py # L8  cross-encoder / Claude rerank; polyhierarchy context
  postcoord.py         # L4  express aggregated entities; L9 harder axes + composition
  sssom.py             # L9  SSSOM rows + TSV export
  agents/              # L10 tool-using agent; ontology critic (owl-mcp)
  mcp_server.py        # L11 MCP server
  tracing.py           # L11 JSONL traces, prompt caching stats
eval/harness.py  eval/gold/ch01.csv ...                       # L5
reports/  dashboards/icd_mapping.html                          # L12-13
```

---

# Module 1 — Foundations (Nov 9 – Dec 6)

## Week 0 (Nov 6–8) — done in commit `f108492`, plus this revision
Config, ICD-10-CM loader, ICD-11 client, LLM smoke test. This revision adds release `2026-01`, `mms_lookup` / `get_postcoordination_axes` / `codeinfo`, `who_map.py`, and new fields on `MappingProposal`.
**To do:** run `CodeFusion --help` once to confirm the command-line flags `codefusion.py` uses, and that they override the folder's `parameters.json` (which sets `matchThreshold` 0.5 and free matching on); the WHO table is already in `data/raw/`; put the CDC ICD-10-CM 2026 codes file in `data/raw/`; run `scripts/load_icd10cm_ch01.py` and `scripts/pull_icd11_ch01.py`.

## Lesson 1 (Nov 9–15) — LLM mental model, prompting, structured output
- Finish `notes/wk01_llm_mental_model.md` in your own words.
- Grounding experiment on 20 Ch. 1 codes: no context vs the right Foundation entity pasted vs a plausible wrong one.
- `mapper_v0.py`: LLM-only baseline returning `MappingProposal` via structured outputs; zero-shot vs few-shot vs reasoning-first on 50 codes, scored against the silver table.
- **Done when:** `reports/l1_baseline.csv` exists with silver-scored results and cost per strategy.

## Lesson 2 (Nov 16–22) — Embeddings and the Foundation harvest
- `harvest.py`: walk the ICD-11 chapter 01 root through the polyhierarchy (dedupe by URI, keep all parents); save `data/foundation_ch01.parquet`; call `mms_lookup` once per entity into `data/mms_lookup_ch01.parquet`.
- `embed.py`: three models; entity-level vs term-level vectors; top-5 printouts for 20 CM titles.
- **Done when:** 10 failure cases logged with an explanation each.

## Lesson 3 (Nov 23–29, light, ~6 h) — DuckDB vector store
- `store.py` and `retrievers/dense.py`: HNSW cosine index, chapter filter; overlap with brute force ≥ 0.95.
- Recall@5/10/20 of the silver Foundation URI for all `exact`-match Ch. 1 codes.
- Non-LLM baseline: run CodeFusion (default and free) on all Ch. 1 CM titles, cache both, and score its top Foundation URI and its codes against the silver labels. This is the bar the pipeline has to beat.

## Lesson 4 (Nov 30 – Dec 6) — First pipeline on all of Chapter 1 · **Gate 1**
- `pipeline.py`: top-20 Foundation candidates → Claude chooses 0–3 URIs with quoted evidence → `mms_lookup` derives the stem → branch and set `target_type`.
- `postcoord.py` v0 (aggregated targets): `get_postcoordination_axes` for the derived stem → a per-stem JSON schema (enums of allowed codes) → Claude picks the axis values that express the **chosen Foundation entity** (e.g. Foundation 1205958647 on stem 1A00 → `1A00&XN8P1`), with CodeFusion's clusters for the same code (`cluster_candidates`, default and free) offered as candidates → `codeinfo` validates → `cluster_source` recorded. If no allowed value captures the difference, set `aggregated_detail_lost` and record what was lost.
- `budget.py`: per-run and daily caps; bounded `asyncio` concurrency.
- Run **all Ch. 1 CM codes** → `outputs/ch01_v1.csv`; review 50 rows into `notes/wk04_error_taxonomy_v1.md` (retrieval, selection, derivation, postcoordination, structural).
- **Gate 1 (Dec 6):** full Ch. 1 run within budget, every chosen URI from the candidate list, every code derived, every cluster validated, and every output carrying a `target_type`. Tag `v0.1.0`.

# Module 2 — Measure and improve (Dec 7 – Jan 17)

## Lesson 5 (Dec 7–13) — Evaluation harness and gold set
- Build `eval/gold/ch01.csv` (150–200 rows) by stratified sampling through `who_map` on `silver_target_type`; review each row; 30% held out.
- Review every `aggregated_bare` row by hand: write the cluster that expresses the Foundation entity, or mark `aggregated_detail_lost` with the lost detail. Add a few `composed` cases.
- `eval/harness.py`: all four metric levels, by `target_type`, stratum and `cluster_source`; results appended to `reports/results.csv`.
- Ablation on the dev split: clusters from Claude alone, CodeFusion default alone, CodeFusion free alone, and Claude with CodeFusion candidates.
- Optional: a small Gradio review UI (`eval` extra).

## Lesson 6 (Dec 14–20) — Hybrid retrieval · onboard Chapter 5
- BM25 via DuckDB FTS (or your Lucene setup), RRF fusion, multi-vector (title / definition / synonyms).
- Pull ICD-11 chapter 06; build `eval/gold/ch05.csv` (100 rows); run dense / lexical / hybrid on Ch. 1 and Ch. 5.
- **Done when:** ablation table by chapter in `reports/`, and a note on how Ch. 5 fails differently.

## Lesson 7 (Dec 21–23, ~4 h) — Reading before the break
HyDE, cross-encoder reranking, contextual retrieval, GraphRAG. Write two testable hypotheses in `notes/wk07.md`. Commit and push before leaving.

## Lesson 8 (Jan 8–17) — Re-entry, query and context improvements · **Gate 2**
- Re-entry (Jan 8–10): reproduce December's numbers before changing anything.
- `queryops/hyde.py`, `rerank.py` (cross-encoder and Claude listwise), `context.py` (polyhierarchy-enriched chunks), graph hop (all parents + children of the top 3).
- One-at-a-time ablation on Ch. 1 + Ch. 5 dev splits.
- **Gate 2 (Jan 17):** one held-out run per configuration; Foundation recall@10, MRR, MMS stem accuracy; hypotheses confirmed or refuted. Tag `v0.2.0`.

# Module 3 — Tools and agents (Jan 18 – Feb 21)

## Lesson 9 (Jan 18–24) — Harder postcoordination and composition with Chapter 19 · SSSOM
- Pull ICD-11 chapters 22 (+23); `eval/gold/ch19.csv` (100 rows), many `ancestor` matches whose CM detail must become extension codes, plus `composed` cases (e.g. injury + external cause).
- `postcoord.py` v1: required axes, multi-value axes, CM detail (laterality, encounter, fracture subtype) alongside the Foundation entity's own detail.
- Composition for sources with no Foundation target: Claude proposes a cluster from candidate stems (`/`) and extension codes (`&`), each stem retrieved and derived as usual, with CodeFusion **free**-mode combinations (`GoodMatchWithFreePostcoordination`) as candidates; `codeinfo` / `describe` validates; otherwise `none`.
- Repeat the default-vs-free CodeFusion ablation on Ch. 19, where free matching should matter most.
- `sssom.py`: rows + TSV export; validate with `sssom-py`. Decide and document how a cluster is represented.
- **Done when:** every output validates; cluster exact and per-axis accuracy reported.

## Lesson 10 (Jan 25–31) — Agents, tested skeptically
- `agents/mapper_agent.py`: tools `search_foundation`, `get_entity`, `mms_lookup`, `get_axes`, `validate_cluster`; the agent must follow the same branches and set `target_type`; capped loop; traces.
- Optional `agents/critic.py`: an ontology critic using owl-mcp (exclusions, sibling plausibility).
- Head-to-head vs the Lesson 8 pipeline on Ch. 5 and Ch. 19 gold: accuracy, cost, latency. Keep the simpler system if it wins.

## Lesson 11 (Feb 1–7) — MCP server, observability, Chapter 21
- `mcp_server.py` (FastMCP): the Lesson 10 tools plus `propose_mappings(icd10cm_code)`; register in Claude Desktop and Claude Code; use alongside owl-mcp.
- `tracing.py`: JSONL traces (or Langfuse); prompt caching on the stable system prompt; throughput and cost per 1k codes.
- Pull ICD-11 chapter 24; `eval/gold/ch21.csv`; first Ch. 21 run.

## Lesson 12 (Feb 8–14) — Full runs and error analysis
- Final configuration on Ch. 1, 5, 19, 21 → `outputs/final/chNN.csv` + SSSOM files.
- Every dev-split miss gets a category and a stage (retrieval, selection, derivation, wrong branch, postcoordination, composition) in `reports/error_analysis.md`. Report how many aggregated targets were expressed with a validated cluster by the pipeline, by CodeFusion default, by CodeFusion free, and by the WHO table (about 5%). Keep derivation findings in a separate list: some are findings about the classification, worth raising through WHO-FIC channels.

## Lesson 13 (Feb 15–21) — Dashboard and write-up · **Gate 3**
- `dashboards/icd_mapping.html`: filter by chapter, stratum, confidence and error stage.
- `report/final_report.md`: problem, architecture, results by `target_type` across all gates, a comparison of Foundation-first with the MMS-first order of Xu et al., failure taxonomy, RAG vs long context vs fine-tuning, what scaling to 22 chapters would take.
- **Gate 3 (Feb 21):** MCP tool working, valid SSSOM, four-chapter held-out results, write-up sent to one colleague. Tag `v1.0.0`.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| ICD-API quotas and slow harvests | Disk cache; harvest per chapter overnight; never call the API in the eval loop. |
| Silver labels mistaken for gold | Separate silver and reviewed columns; report `exact` and `ancestor` matches separately. |
| LLM-invented codes | Claude chooses only Foundation URIs from the candidate list; codes come from `mms_lookup`; clusters from `codeinfo`. |
| Tuning on the test set | 30% held out per chapter, opened only at Gates 2 and 3. |
| Agent complexity creep | Lesson 10 is a test; keep the pipeline if it wins. |
| Cost overrun | Budget cap from Lesson 4, not Lesson 11. |
| Losing the thread over the break | Lesson 7 hypotheses + re-entry checklist on Jan 8. |

## Weekly rhythm (~10 h)
- **Mon (1.5 h):** readings from the course doc.
- **Tue–Thu (6 h):** build, in 2–3 hour blocks.
- **Fri (1.5 h):** run the gold set, write `notes/wkNN.md`, commit, tag.
- **Sat (1 h, optional):** one extra paper or talk.

## What "done" looks like on Feb 21
A fresh checkout of `v1.0.0` can pull terminologies, build indexes for four chapters, map ICD-10-CM codes to Foundation entities with derived MMS codes and validated clusters, export SSSOM, serve the same pipeline over MCP, and reproduce the final report and dashboard from the gold sets.
