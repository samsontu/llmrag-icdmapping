"""Week-1 smoke test: 5 cheap completions across Anthropic + OpenAI.

Run:
    uv run python scripts/smoke_test_llm.py

Prints output, token counts, and rough cost. Refuses if a provider key is missing.
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.table import Table

from icd_mapper.config import settings
from icd_mapper.llm_clients import claude_complete, openai_complete

PROMPTS = [
    "In one sentence, what is ICD-10-CM?",
    "List 3 differences between ICD-10-CM and ICD-11.",
    "What is post-coordination in ICD-11? Answer in 2 sentences.",
    "Give the ICD-10-CM block range for the chapter on Mental, behavioral, and neurodevelopmental disorders.",
    "Why is ICD-10-CM to ICD-11 mapping non-trivial? 3 bullet reasons.",
]


def main() -> int:
    console = Console()

    if not settings.anthropic_api_key and not settings.openai_api_key:
        console.print(
            "[red]No LLM keys configured. Set ANTHROPIC_API_KEY and/or OPENAI_API_KEY in .env.[/red]"
        )
        return 1

    table = Table(title="LLM smoke test")
    table.add_column("Provider", style="cyan")
    table.add_column("Model")
    table.add_column("Prompt", style="dim", max_width=40)
    table.add_column("In", justify="right")
    table.add_column("Out", justify="right")
    table.add_column("$", justify="right", style="green")

    total_cost = 0.0

    for prompt in PROMPTS:
        if settings.anthropic_api_key:
            r = claude_complete(prompt)
            total_cost += r.cost_usd
            table.add_row(
                "Anthropic",
                r.model,
                prompt,
                str(r.input_tokens),
                str(r.output_tokens),
                f"{r.cost_usd:.5f}",
            )
            console.print(f"[cyan]Anthropic:[/cyan] {r.text.strip()[:200]}")
        if settings.openai_api_key:
            r = openai_complete(prompt)
            total_cost += r.cost_usd
            table.add_row(
                "OpenAI",
                r.model,
                prompt,
                str(r.input_tokens),
                str(r.output_tokens),
                f"{r.cost_usd:.5f}",
            )
            console.print(f"[magenta]OpenAI:[/magenta] {r.text.strip()[:200]}")
        console.print()

    console.print(table)
    console.print(f"[bold green]Total cost: ${total_cost:.4f}[/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
