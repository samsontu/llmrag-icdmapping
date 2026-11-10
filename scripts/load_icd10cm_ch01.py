"""Load ICD-10-CM for one chapter and emit a CSV.

Source (in `data/raw/`, picked automatically): the CDC `icd10cm-codes-YYYY.txt`
file if present, otherwise the BioPortal/UMLS2RDF `ICD10CM.ttl` file. The TTL
source adds `synonyms` (pipe-separated), `parent`, `kind` and `is_leaf` columns.

Run:
    uv run python scripts/load_icd10cm_ch01.py
    uv run python scripts/load_icd10cm_ch01.py --chapter 5           # other chapters
    uv run python scripts/load_icd10cm_ch01.py --all-levels          # TTL: + blocks, headers
    uv run python scripts/load_icd10cm_ch01.py --codes-file data/raw/ICD10CM.ttl
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
        None,
        help="CDC icd10cm-codes-YYYY.txt or ICD10CM.ttl; defaults to what data/raw/ holds.",
    ),
    all_levels: bool = typer.Option(
        False, help="TTL only: include chapters, blocks and header categories, not just leaves."
    ),
    out: Path | None = typer.Option(
        None, help="Output CSV path; defaults to data/icd10cm_chNN.csv"
    ),
) -> None:
    settings.ensure_dirs()
    path = codes_file or default_codes_path()
    df = load_chapter(path, chapter, leaves_only=not all_levels)
    if "synonyms" in df.columns:
        df["synonyms"] = df["synonyms"].map(" | ".join)
    if out is None:
        out = settings.icd_data_dir / f"icd10cm_ch{chapter:02d}.csv"
    df.to_csv(out, index=False)
    console.print(
        f"[green]Wrote[/green] {len(df)} Chapter-{chapter} codes from {path.name} → [bold]{out}[/bold]"
    )
    if len(df):
        console.print("Sample:")
        console.print(df.head(5).to_string(index=False))


if __name__ == "__main__":
    app()
