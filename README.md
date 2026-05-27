# icd-mapper

Map **ICD-10-CM** to the **ICD-11 Foundation** using LLMs, retrieval-augmented generation (RAG), and agentic pipelines.

Companion to the 12-week learning plan in [`docs/icd_mapping_3month_plan.md`](docs/icd_mapping_3month_plan.md).

> Scope: pilot on selected ICD-10-CM chapters (Ch. 1 first, then Ch. 5, 19, 21), not all 22.

## Layout

```
.
├── docs/                       # the 3-month plan + future writeups
├── src/icd_mapper/             # the installable Python package (active)
│   ├── config.py               # env loading, settings, paths
│   ├── types.py                # Pydantic models (ICD10CMCode, ICD11Entity, MappingProposal)
│   ├── icd10cm_loader.py       # parse CDC ICD-10-CM tabular file, filter by chapter
│   ├── icd11_client.py         # async WHO ICD-11 API client with disk cache
│   └── llm_clients.py          # thin Anthropic + OpenAI wrappers
├── scripts/                    # runnable entry points
│   ├── pull_icd11_ch01.py      # cache ICD-11 Ch. 1 (Infectious & parasitic) locally
│   ├── load_icd10cm_ch01.py    # parse CDC file → CSV of Ch. 1 codes
│   └── smoke_test_llm.py       # first 5 LLM API calls (Anthropic + OpenAI)
├── notebooks/                  # exploratory work, weekly first-contact notebooks
├── prompts/                    # versioned prompt files (text or .toml)
├── notes/                      # weekly concept notes (wk01.md, wk02.md, ...)
├── eval/                       # eval harness + gold sets (populated week 7)
├── tests/                      # pytest
├── data/                       # raw + cached terminologies (gitignored)
└── src/{data,index,llm,pipeline,retriever,ui}/  # empty placeholders from initial commit
                                                 # — keep, repurpose, or delete; not used yet
```

The empty `src/{data,index,...}/` directories were created in the original initial commit. The active code lives under `src/icd_mapper/` instead, because a single installable package is simpler to import and test.

## Quickstart

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies into a local venv
uv sync --dev

# Copy and fill in secrets
cp .env.example .env
$EDITOR .env

# Run the LLM smoke test (5 cheap completions, prints cost)
uv run python scripts/smoke_test_llm.py

# Pull ICD-10-CM Chapter 1 from the official codes file
# (download icd10cm-codes-2026.txt from CDC into data/raw/ first)
uv run python scripts/load_icd10cm_ch01.py

# Pull ICD-11 Foundation entries under Chapter 1 (infectious & parasitic)
uv run python scripts/pull_icd11_ch01.py

# Tests
uv run pytest
```

## Getting source terminology files

### ICD-10-CM (CDC / NCHS, USA)

Download the latest **codes file** (a fixed-width `.txt` like `icd10cm-codes-2026.txt`) from the CDC FTP / CMS release page and drop it in `data/raw/`. The loader handles the standard `CODE  TITLE` format with periods stripped (e.g. `A001` → `A00.1`).

### ICD-11 Foundation (WHO)

1. Register a free API account at <https://icd.who.int/icdapi>.
2. Note your `client_id` and `client_secret`.
3. Put them in `.env` as `ICD11_CLIENT_ID` / `ICD11_CLIENT_SECRET`.

The client uses OAuth 2.0 client-credentials and caches token + responses on disk under `data/.cache/`.

## Weekly tagging

The 3-month plan tags releases at the end of each phase:

- `v0.1.0` — end of Phase 1 (Week 4): two-stage retrieve + verify on Ch. 1
- `v0.2.0` — end of Phase 2 (Week 8): production retrieval + eval + Ch. 5 + Ch. 19
- `v1.0.0` — end of Phase 3 (Week 12): multi-agent pipeline + dashboard + writeup

## License

MIT — see `LICENSE`.
