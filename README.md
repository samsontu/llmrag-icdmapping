# icd-mapper

Map **ICD-10-CM** to **ICD-11** the way ICD-11 coding is meant to work: find the best **Foundation** entity first, derive the **MMS** stem code through the linearization, then add the **postcoordination** the ICD-10-CM code supports. The project uses LLMs, retrieval-augmented generation (RAG), structured output, agents and MCP.

The learning plan is [`docs/icd_mapping_3month_plan.md`](docs/icd_mapping_3month_plan.md): 13 lessons at about 10 hours/week, Nov 9, 2026 – Feb 21, 2027. Readings and step-by-step build instructions for each lesson are in the companion course doc.

> Scope: chapter pilots, not all 22. ICD-10-CM Ch. 1 first, then Ch. 5, 19 and 21.

## How a code gets mapped

Foundation first: map to the best Foundation entity, derive the MMS target, then postcoordinate to express what the derived stem loses, or compose a target when no Foundation entity fits.

```
ICD-10-CM code + title
  -> retrieve ICD-11 Foundation candidates      (BM25 + dense in DuckDB, rerank)
  -> Claude chooses a Foundation entity         (judgement; may find none)
  -> ICD-API mms/lookup derives the MMS stem    (deterministic)
  -> branch, setting MappingProposal.target_type:
       entity is an MMS category   -> done                                foundation_is_mms
       entity aggregates           -> Claude fills allowed axes to        aggregated_postcoordinated
                                      express it; API validates cluster   (or aggregated_detail_lost)
       no Foundation entity        -> Claude composes stems + extensions; composed
                                      API validates cluster               (or none)
  -> SSSOM rows + cluster
```

Claude never writes an MMS code. Stems come from the linearization, axis values from each stem's allowed `postcoordinationScale`, and every cluster is checked by `codeinfo`.

WHO [CodeFusion](https://icd.who.int/docs/codefusion/en/user-guide/) also proposes clusters. `src/icd_mapper/codefusion.py` runs it in batch (source `MMS`, version 2026) in its default mode and with `useFreePostcoordinationMatching=true`, and its clusters are offered to Claude as candidates. `MappingProposal.cluster_source` records which proposal was kept.

The WHO table postcoordinates only about 5% of the rows whose Foundation entity aggregates into another MMS entity (351 of 7,082), so those rows are reviewed by hand in the gold set. This order differs from the MMS-first sequential approach of Xu, Fung and Bodenreider (MEDINFO 2021); see the plan.

## Layout

```
.
├── docs/                       # learning plan (+ old .docx draft)
├── src/icd_mapper/             # the installable package
│   ├── config.py               # env loading, settings, paths (ICD-11 release 2026-01)
│   ├── types.py                # ICD10CMCode, ICD11Entity, MmsDerivation, MappingProposal, ...
│   ├── icd10cm_loader.py       # parse the CDC ICD-10-CM codes file, filter by chapter
│   ├── icd11_client.py         # async WHO ICD-API client with disk cache:
│   │                           #   Foundation entities, mms_lookup, postcoordination axes, codeinfo
│   ├── who_map.py              # WHO 2026 ICD-10 -> ICD-11 table loader + ICD-10-CM bridge
│   ├── codefusion.py           # run WHO CodeFusion in batch; parse clusters (default/free)
│   └── llm_clients.py          # thin Anthropic (+ optional OpenAI) wrappers
├── scripts/                    # runnable entry points (load, pull, smoke test)
├── notebooks/                  # exploration (jupytext .py mirrors)
├── prompts/                    # versioned prompt files
├── notes/                      # weekly notes (wk01.md, wk02.md, ...)
├── eval/                       # harness + gold sets (Lesson 5)
├── tests/                      # pytest (respx mocks; no network)
└── data/                       # raw + cached terminologies (gitignored)
```

Modules added lesson by lesson (`harvest.py`, `store.py`, `retrievers/`, `pipeline.py`, `postcoord.py`, `sssom.py`, `agents/`, `mcp_server.py`, ...) are listed in the plan's "Target layout". The empty `src/ui/` and `infra/` folders are left over from the initial commit and are not used yet.

## Quickstart

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Core + dev dependencies; add extras as lessons need them
uv sync --dev
uv sync --dev --extra rag            # Lessons 2-8: DuckDB, sentence-transformers
uv sync --dev --extra mapping --extra mcp   # Lessons 9-11: sssom, mcp

# Secrets
cp .env.example .env
$EDITOR .env

# Smoke tests
uv run python scripts/smoke_test_llm.py
uv run pytest

# Source data (see below), then:
uv run python scripts/load_icd10cm_ch01.py
uv run python scripts/pull_icd11_ch01.py
```

## Source data

### ICD-10-CM
Either source in `data/raw/` works; `scripts/load_icd10cm_ch01.py` picks it up automatically (CDC file first if both are present).

- **BioPortal/UMLS2RDF Turtle, `ICD10CM.ttl`** (in use; ICD-10-CM 2026 from UMLS 2025AB). Every level of the classification, with synonyms (`skos:altLabel`) and the hierarchy. `load_ttl` parses all 98,505 classes in about a second; `load_chapter` keeps the 74,719 leaf (billable) codes by default (`--all-levels` adds chapters, blocks and headers). The CSV gains `synonyms` (pipe-separated), `parent`, `kind` and `is_leaf`.
- **CDC codes file, `icd10cm-codes-YYYY.txt`**: billable codes and titles only, `CODE  TITLE` per line with periods stripped (`A001` → `A00.1`).

### ICD-11 (WHO ICD-API)
1. Register at <https://icd.who.int/icdapi>.
2. Put `ICD11_CLIENT_ID` / `ICD11_CLIENT_SECRET` in `.env`. Keep `ICD11_RELEASE_ID=2026-01` so API results match the mapping table.

The client uses OAuth 2.0 client credentials and caches responses under `data/.cache/`.

### WHO ICD-10 → ICD-11 mapping table (gold/silver source)
Copy `10To11MapToOneCategory.xlsx` from the WHO 2026 release mapping tables into `data/raw/` (or set `WHO_MAPPING_TABLE` in `.env`). Each WHO ICD-10 category has its ICD-11 Foundation URI, MMS URI and MMS code or cluster.

```python
from icd_mapper.who_map import load_10to11, who_ancestor_for_cm

table = load_10to11()                       # 11,243 category rows
who_code, level = who_ancestor_for_cm("S72.001A", set(table.icd10_code))
# -> ("S72.0", "ancestor"): the table target is for the WHO parent;
#    the CM detail must come from the Foundation choice or postcoordination.
table.silver_target_type.value_counts()
# foundation_is_mms 4081, aggregated_postcoordinated 351, aggregated_bare 6731, none 80
```

### WHO CodeFusion (optional, for cluster proposals)
Set `CODEFUSION_PATH` in `.env` to the CodeFusion binary (here `/Users/tu/Downloads/codefusion_osx-x64/CodeFusion`) and run `CodeFusion --help` once to confirm the flags. The wrapper passes its settings on the command line (version 2026, source MMS). That folder's `parameters.json` (CodeFusion 1.1.1) already uses version 2026, but it also sets `matchThreshold` 0.5 (the default is 0.43) and `useFreePostcoordinationMatching` true. The wrapper passes the free-matching flag explicitly; pass `match_threshold` too if you want a fixed value, and check on the first run that command-line values override the file.

```python
from pathlib import Path
from icd_mapper import codefusion as cf

inp = cf.write_input(ch01_df.rename(columns={"code": "id"}), Path("data/codefusion/ch01.txt"))
free = cf.CodeFusionConfig(use_free_postcoordination=True)
out = cf.run(inp, free)                    # writes ch01-checked.xlsx beside the input
df = cf.read_output(out)
cf.cluster_candidates(df, "A00.0")         # postcoordination proposals, best first
```

## Milestones

- `v0.1.0`: **Gate 1, Dec 6.** Pipeline on all of Ch. 1: Foundation choice, derived MMS stem, validated clusters for aggregated targets, a `target_type` on every output.
- `v0.2.0`: **Gate 2, Jan 17.** Hybrid retrieval, reranking, HyDE; held-out scores on Ch. 1 and Ch. 5.
- `v1.0.0`: **Gate 3, Feb 21.** Harder postcoordination and composed targets (Ch. 19), SSSOM, agent comparison, MCP server, four chapters, dashboard and write-up.

## License

MIT — see `LICENSE`.
