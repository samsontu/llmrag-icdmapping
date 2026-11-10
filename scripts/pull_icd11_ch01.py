"""Cache a slice of the ICD-11 Foundation locally for a single chapter.

For Week 1 we just need Chapter 1 (Certain infectious or parasitic diseases).
WHO assigns ICD-11 chapter IDs in the Foundation; you can find the right root
entity by looking up the chapter on https://icd.who.int/browse11 and copying
the entity ID from the URL.

By default we use the ICD-11 Foundation root for Chapter 1 (Infectious or
parasitic diseases). You may want to override on the command line as you
move to other chapters.

Run:
    uv run python scripts/pull_icd11_ch01.py
    uv run python scripts/pull_icd11_ch01.py --root-id 334423054 --out data/icd11_ch01.json
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console

from icd_mapper.config import settings
from icd_mapper.icd11_client import ICD11Client

app = typer.Typer(add_completion=False)
console = Console()

# ICD-11 Foundation entity ID for "01 Certain infectious or parasitic diseases".
# Verify on https://icd.who.int/browse11 — WHO occasionally renumbers.
DEFAULT_CH01_ROOT = "1435254666"


async def _run(root_id: str, out: Path, max_nodes: int) -> int:
    settings.ensure_dirs()
    async with ICD11Client() as client:
        console.print(f"Walking ICD-11 descendants from [bold]{root_id}[/bold]...")
        entities = await client.walk_descendants(root_id, max_nodes=max_nodes)
    console.print(f"[green]Fetched[/green] {len(entities)} entities")
    payload = [e.model_dump(mode="json") for e in entities]
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    console.print(f"Wrote {out}")
    return 0


@app.command()
def main(
    root_id: str = typer.Option(DEFAULT_CH01_ROOT, help="ICD-11 Foundation root entity ID"),
    out: Path | None = typer.Option(None, help="Output JSON path"),
    max_nodes: int = typer.Option(5000, help="Safety cap on BFS"),
) -> None:
    if out is None:
        out = settings.icd_data_dir / "icd11_foundation_ch01.json"
    asyncio.run(_run(root_id, out, max_nodes))


if __name__ == "__main__":
    app()
