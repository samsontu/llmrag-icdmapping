# ---
# jupyter:
#   jupytext:
#     formats: py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
# ---

# %% [markdown]
# # Week 1 — First contact
#
# Goals:
# 1. Confirm Anthropic + OpenAI API keys work and you understand pricing.
# 2. Sanity-check the ICD-10-CM loader on Chapter 1.
# 3. Pull a small slice of ICD-11 Foundation and inspect the shape.
#
# Open this file in VS Code / Cursor and run cells; or convert with
# `jupytext --to ipynb notebooks/wk01_first_contact.py`.

# %%
from rich import print as rprint

from icd_mapper.config import settings
from icd_mapper.llm_clients import claude_complete, openai_complete

settings.ensure_dirs()
rprint("Has Anthropic key:", settings.anthropic_api_key is not None)
rprint("Has OpenAI key:", settings.openai_api_key is not None)
rprint("Has ICD-11 client_id:", settings.icd11_client_id is not None)

# %% [markdown]
# ## 1. LLM first contact
#
# We send the same prompt to both Claude and GPT and compare.

# %%
prompt = "In two sentences, what is ICD-11 post-coordination?"

if settings.anthropic_api_key:
    r = claude_complete(prompt)
    rprint(f"[cyan]Claude[/cyan] ({r.input_tokens}→{r.output_tokens} tok, ${r.cost_usd:.5f})")
    rprint(r.text)

if settings.openai_api_key:
    r = openai_complete(prompt)
    rprint(f"[magenta]GPT[/magenta] ({r.input_tokens}→{r.output_tokens} tok, ${r.cost_usd:.5f})")
    rprint(r.text)

# %% [markdown]
# ## 2. ICD-10-CM loader
#
# Drop `icd10cm-codes-2026.txt` (from CMS) into `data/raw/` first.

# %%
from icd_mapper.icd10cm_loader import default_codes_path, load_chapter  # noqa: E402

try:
    df = load_chapter(default_codes_path(), chapter=1)
    rprint(df.head(10))
    rprint("Total Ch.1 codes:", len(df))
except FileNotFoundError as e:
    rprint(f"[yellow]Skipping (file missing): {e}[/yellow]")

# %% [markdown]
# ## 3. ICD-11 Foundation sample
#
# Requires `ICD11_CLIENT_ID` / `ICD11_CLIENT_SECRET` in `.env`.

# %%
import asyncio  # noqa: E402

from icd_mapper.icd11_client import ICD11Client  # noqa: E402


async def _sample() -> None:
    async with ICD11Client() as client:
        # Walk just a small slice for the notebook
        entities = await client.walk_descendants("1435254666", max_nodes=50)
        for e in entities[:10]:
            rprint(f"[bold]{e.entity_id}[/bold] {e.title}")
        rprint(f"Fetched {len(entities)} entities")


if settings.icd11_client_id:
    asyncio.run(_sample())
else:
    rprint("[yellow]Skipping ICD-11 sample — credentials not set.[/yellow]")
