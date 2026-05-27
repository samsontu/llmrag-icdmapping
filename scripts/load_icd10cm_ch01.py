"""Parse the CDC ICD-10-CM codes file and emit a Chapter-1 CSV.

Prereq: drop `icd10cm-codes-YYYY.txt` (downloaded from CMS / CDC) into
`data/raw/`.

Run:
    uv run python scripts/load_icd10cm_ch01.py
    uv run python scripts/load_icd10cm_ch01.py --chapter 5   # other chapters too
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from icd_mapper.config import settings
from icd_mapper.icd10cm_loader import default_codes_path, load_chapter

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def main(
    chapter: int = typer.Option(1, help="ICD-10-CM chapter number (1..22)"),
    codes_file: Path | None = typer.Option(
        None, help="Path to icd10cm-codes-YYYY.txt; defaults to latest in data/raw/."
    ),
    out: Path | None = typer.Option(
        None, help="Output CSV path; defaults to data/icd10cm_chNN.csv"
    ),
) -> None:
    settings.ensure_dirs()
    path = codes_file or default_codes_path()
    df = load_chapter(path, chapter)
    if out is None:
        out = settings.icd_data_dir / f"icd10cm_ch{chapter:02d}.csv"
    df.to_csv(out, index=False)
    console.print(f"[green]Wrote[/green] {len(df)} Chapter-{chapter} codes → [bold]{out}[/bold]")
    if len(df):
        console.print("Sample:")
        console.print(df.head(5).to_string(index=False))


if __name__ == "__main__":
    app()
