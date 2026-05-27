"""Shared Pydantic types used across loaders, clients, and pipelines.

Conventions:
- ICD-10-CM codes are stored *with* the period (e.g. "A00.1") in `code`,
  and *without* (e.g. "A001") in `code_nodot`. The CDC tabular files use the
  no-dot form; humans use the dotted form.
- ICD-11 Foundation entries are identified by their full IRI
  (e.g. "http://id.who.int/icd/entity/1435254666"). The trailing integer is
  the `entity_id`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class ICD10CMCode(BaseModel):
    """A single ICD-10-CM code with title."""

    code: str = Field(description="Dotted form, e.g. 'A00.1'")
    code_nodot: str = Field(description="No-dot form, e.g. 'A001'")
    title: str = Field(description="Short description from the CDC codes file")
    chapter: int = Field(description="ICD-10-CM chapter number (1..22)")
    block: str | None = Field(default=None, description="Block prefix (e.g. 'A00-A09')")


class ICD11Entity(BaseModel):
    """A node in the ICD-11 Foundation (or MMS linearization)."""

    entity_id: str = Field(description="Trailing integer of the IRI, e.g. '1435254666'")
    iri: HttpUrl
    title: str
    definition: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    inclusions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    parents: list[str] = Field(default_factory=list, description="Entity IDs of parent nodes")
    children: list[str] = Field(default_factory=list, description="Entity IDs of child nodes")
    code: str | None = Field(default=None, description="MMS code if this is a linearized entity")


class ICD11Candidate(BaseModel):
    """One candidate ICD-11 entity proposed for a given ICD-10-CM code."""

    entity_id: str
    title: str
    score: float = Field(ge=0.0, le=1.0, description="Retriever / verifier score")
    rationale: str | None = None


class MappingProposal(BaseModel):
    """Final mapping proposal from a pipeline run."""

    icd10cm_code: str = Field(description="Dotted ICD-10-CM code")
    candidates: list[ICD11Candidate] = Field(default_factory=list)
    chosen: ICD11Candidate | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    rationale: str = ""
    # For post-coordinated mappings (Ch. 19+). axis -> entity_id.
    extensions: dict[str, str] = Field(default_factory=dict)
    # Cost accounting
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


def chapter_for_icd10cm_code(code: str) -> int:
    """Return the ICD-10-CM chapter number (1..22) for a code's letter prefix.

    Based on the 2026 ICD-10-CM chapter ranges. Z codes → Ch. 21,
    U codes → Ch. 22 (special purposes).
    """
    if not code:
        raise ValueError("Empty code")
    first = code[0].upper()
    if first == "A" or first == "B":
        return 1
    if first == "C":
        return 2
    if first == "D":
        # D00-D49 → Ch. 2 (neoplasms), D50-D89 → Ch. 3 (blood)
        try:
            num = int(code[1:3])
        except ValueError as exc:
            raise ValueError(f"Cannot parse D-code chapter for {code!r}") from exc
        return 2 if num <= 49 else 3
    if first == "E":
        return 4
    if first == "F":
        return 5
    if first == "G":
        return 6
    if first == "H":
        try:
            num = int(code[1:3])
        except ValueError as exc:
            raise ValueError(f"Cannot parse H-code chapter for {code!r}") from exc
        return 7 if num <= 59 else 8  # H00-H59 eye, H60-H95 ear
    if first == "I":
        return 9
    if first == "J":
        return 10
    if first == "K":
        return 11
    if first == "L":
        return 12
    if first == "M":
        return 13
    if first == "N":
        return 14
    if first == "O":
        return 15
    if first == "P":
        return 16
    if first == "Q":
        return 17
    if first == "R":
        return 18
    if first in ("S", "T"):
        return 19
    if first in ("V", "W", "X", "Y"):
        return 20
    if first == "Z":
        return 21
    if first == "U":
        return 22
    raise ValueError(f"Unknown ICD-10-CM letter prefix for code {code!r}")
