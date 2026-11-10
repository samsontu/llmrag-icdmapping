"""Load ICD-10-CM from either source and filter by chapter.

Two sources are supported (both in `data/raw/`):

1. The BioPortal/UMLS2RDF Turtle file `ICD10CM.ttl` (`load_ttl`). It has every
   level of the classification (chapters, blocks, header categories, billable leaf
   codes), dotted codes in `skos:notation`, titles in `skos:prefLabel`, synonyms in
   `skos:altLabel` and the hierarchy in `rdfs:subClassOf`.
2. The CDC codes file `icd10cm-codes-YYYY.txt` (`load_codes_file`): billable codes
   and titles only.

`load_chapter` accepts either; for the TTL file it returns leaf codes by default, which
matches the CDC file's billable codes.

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
import re
from collections.abc import Iterator
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


# ---- Turtle (BioPortal / UMLS2RDF) ----

TTL_NS = "http://purl.bioontology.org/ontology/ICD10CM/"
_SUBJECT = re.compile(r"^<" + re.escape(TTL_NS) + r"([^>]+)>\s+a\s+owl:Class\s*;\s*$")
# Triple-quoted literal; escapes like \" may appear inside.
_LITERAL = re.compile(r'"""((?:[^"\\]|\\.|"(?!""))*)"""')
# A code ('A00', 'D3A.01', 'QA0.1', 'S72.001A') or a range ('A00-B99', 'Q00-QA0').
_CODE_SHAPE = re.compile(r"^[A-Z][0-9A-Z]{2}(\.[0-9A-Z]+)?(-[A-Z][0-9A-Z]{2})?$")
_PARENT = re.compile(r"rdfs:subClassOf\s+<" + re.escape(TTL_NS) + r"([^>]+)>")


def _unescape(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


def _literals(line: str) -> list[str]:
    return [_unescape(m.group(1)) for m in _LITERAL.finditer(line)]


def _iter_ttl_classes(path: Path) -> Iterator[dict[str, object]]:
    """Yield one dict per ICD-10-CM owl:Class block in a UMLS2RDF Turtle file."""
    current: dict[str, object] | None = None
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if current is None:
                m = _SUBJECT.match(line)
                if m:
                    current = {"iri_code": m.group(1), "title": None, "code": None,
                               "synonyms": [], "parent": None}
                continue
            if line.strip() == ".":
                yield current
                current = None
                continue
            stripped = line.strip()
            if stripped.startswith("skos:prefLabel"):
                vals = _literals(stripped)
                current["title"] = vals[0] if vals else None
            elif stripped.startswith("skos:notation"):
                vals = _literals(stripped)
                current["code"] = vals[0] if vals else None
            elif stripped.startswith("skos:altLabel"):
                current["synonyms"].extend(_literals(stripped))  # type: ignore[union-attr]
            elif stripped.startswith("rdfs:subClassOf"):
                m = _PARENT.search(stripped)
                current["parent"] = m.group(1) if m else None  # owl:Thing -> None
    if current is not None:
        yield current


def _chapter_for(code: str) -> int:
    """Chapter number for a code or a range such as 'A00-B99' (uses the first code)."""
    return chapter_for_icd10cm_code(code.split("-", 1)[0].replace(".", ""))


def load_ttl(path: Path) -> pd.DataFrame:
    """Parse the BioPortal/UMLS2RDF ICD10CM.ttl file into a DataFrame.

    Returns columns:
      code, code_nodot, title, chapter,
      synonyms  (list[str]; altLabels, deduplicated, title excluded),
      parent    (dotted code of the rdfs:subClassOf parent; None for chapters),
      kind      ('chapter' | 'block' | 'category'; chapters and blocks are ranges),
      is_leaf   (True when no other class has this code as parent; = billable).
    """
    if not path.exists():
        raise FileNotFoundError(f"ICD-10-CM Turtle file not found at {path}.")
    rows: list[dict[str, object]] = []
    for cls in _iter_ttl_classes(path):
        code = str(cls["code"] or cls["iri_code"])
        if not _CODE_SHAPE.match(code):
            continue  # e.g. the root class 'ICD-10-CM' (TABULAR LIST)
        title = str(cls["title"] or "")
        synonyms: list[str] = []
        for syn in cls["synonyms"]:  # type: ignore[union-attr]
            if syn != title and syn not in synonyms:
                synonyms.append(syn)
        is_range = "-" in code
        parent = cls["parent"]
        kind = ("block" if parent else "chapter") if is_range else "category"
        try:
            chapter = _chapter_for(code)
        except ValueError:
            log.warning("Skipping code with unknown chapter: %r", code)
            continue
        rows.append({
            "code": code,
            "code_nodot": code.replace(".", "") if not is_range else code,
            "title": title,
            "chapter": chapter,
            "synonyms": synonyms,
            "parent": parent,
            "kind": kind,
        })
    df = pd.DataFrame(rows).sort_values("code", kind="stable").reset_index(drop=True)
    parents = set(df["parent"].dropna())
    df["is_leaf"] = (df["kind"] == "category") & ~df["code"].isin(parents)
    log.info("Loaded %d ICD-10-CM classes (%d leaf codes) from %s",
             len(df), int(df["is_leaf"].sum()), path)
    return df


# ---- either source ----


def load_chapter(path: Path, chapter: int, *, leaves_only: bool = True) -> pd.DataFrame:
    """Load ICD-10-CM codes for one chapter from a CDC .txt or a UMLS2RDF .ttl file.

    For .ttl, `leaves_only=True` (default) keeps billable leaf codes, matching the CDC
    codes file; set it False to include chapters, blocks and header categories.
    The CDC file contains only billable codes, so `leaves_only` has no effect there.
    """
    if path.suffix.lower() == ".ttl":
        df = load_ttl(path)
        if leaves_only:
            df = df[df["is_leaf"]]
    else:
        df = load_codes_file(path)
    out = df[df["chapter"] == chapter].reset_index(drop=True)
    log.info("Chapter %d contains %d codes", chapter, len(out))
    return out


def default_codes_path() -> Path:
    """The ICD-10-CM source in data/raw/: the latest CDC codes file, else ICD10CM*.ttl."""
    raw = settings.icd_data_dir / "raw"
    candidates = sorted(raw.glob("icd10cm-codes-*.txt"))
    if candidates:
        return candidates[-1]  # latest year wins lexicographically
    ttl = sorted(raw.glob("ICD10CM*.ttl")) + sorted(raw.glob("icd10cm*.ttl"))
    if ttl:
        return ttl[0]
    raise FileNotFoundError(
        f"No ICD-10-CM source found in {raw}. Add the CDC icd10cm-codes-YYYY.txt "
        "file or the BioPortal ICD10CM.ttl file."
    )
