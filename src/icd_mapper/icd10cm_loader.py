"""Parse the CDC ICD-10-CM codes file and filter by chapter.

The CDC publishes a fixed-width-ish `icd10cm-codes-YYYY.txt` file with one
code per line in the form:

    A000     Cholera due to Vibrio cholerae 01, biovar cholerae
    A001     Cholera due to Vibrio cholerae 01, biovar eltor
    ...

Codes are stored *without* the decimal point. We restore the dotted form
(`A00.1`) because that's what humans use.

Download the latest file from CMS / CDC and drop it in `data/raw/`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from icd_mapper.config import settings
from icd_mapper.types import chapter_for_icd10cm_code

log = logging.getLogger(__name__)


def insert_dot(code_nodot: str) -> str:
    """Restore the period after the third character.

    'A001'   -> 'A00.1'
    'A00'    -> 'A00'
    'S72001A' -> 'S72.001A'
    """
    code_nodot = code_nodot.strip().upper()
    if len(code_nodot) <= 3:
        return code_nodot
    return code_nodot[:3] + "." + code_nodot[3:]


def load_codes_file(path: Path) -> pd.DataFrame:
    """Parse the CDC codes file into a DataFrame.

    Returns columns: code, code_nodot, title, chapter.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"ICD-10-CM codes file not found at {path}. "
            "Download icd10cm-codes-YYYY.txt from the CMS release page "
            "and place it under data/raw/."
        )

    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            # Split on first whitespace block: "CODE   TITLE"
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                log.warning("Skipping malformed line: %r", line[:60])
                continue
            code_nodot, title = parts[0].strip(), parts[1].strip()
            if not code_nodot or not code_nodot[0].isalpha():
                continue
            try:
                chapter = chapter_for_icd10cm_code(code_nodot)
            except ValueError:
                log.warning("Skipping code with unknown chapter: %r", code_nodot)
                continue
            rows.append(
                {
                    "code_nodot": code_nodot,
                    "code": insert_dot(code_nodot),
                    "title": title,
                    "chapter": chapter,
                }
            )

    df = pd.DataFrame(rows)
    log.info("Loaded %d ICD-10-CM codes from %s", len(df), path)
    return df


def load_chapter(path: Path, chapter: int) -> pd.DataFrame:
    """Convenience: load codes file and filter to a single chapter."""
    df = load_codes_file(path)
    out = df[df["chapter"] == chapter].reset_index(drop=True)
    log.info("Chapter %d contains %d codes", chapter, len(out))
    return out


def default_codes_path() -> Path:
    """Heuristic: the most recently-modified file in data/raw/ that matches the pattern."""
    raw = settings.icd_data_dir / "raw"
    candidates = sorted(raw.glob("icd10cm-codes-*.txt"))
    if not candidates:
        raise FileNotFoundError(
            f"No icd10cm-codes-*.txt found in {raw}. Download the official file from CMS/CDC."
        )
    return candidates[-1]  # latest year wins lexicographically
