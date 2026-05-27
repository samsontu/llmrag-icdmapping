"""Unit tests for the ICD-10-CM loader — no network, no API keys required."""

from __future__ import annotations

from pathlib import Path

from icd_mapper.icd10cm_loader import insert_dot, load_chapter, load_codes_file
from icd_mapper.types import chapter_for_icd10cm_code


def test_insert_dot_short_codes_unchanged() -> None:
    assert insert_dot("A00") == "A00"
    assert insert_dot("B99") == "B99"


def test_insert_dot_inserts_after_third_char() -> None:
    assert insert_dot("A001") == "A00.1"
    assert insert_dot("S72001A") == "S72.001A"


def test_chapter_for_icd10cm_code_basics() -> None:
    assert chapter_for_icd10cm_code("A001") == 1
    assert chapter_for_icd10cm_code("B99") == 1
    assert chapter_for_icd10cm_code("C50") == 2
    assert chapter_for_icd10cm_code("D49") == 2  # neoplasms
    assert chapter_for_icd10cm_code("D50") == 3  # blood
    assert chapter_for_icd10cm_code("F32") == 5
    assert chapter_for_icd10cm_code("S72") == 19
    assert chapter_for_icd10cm_code("Z00") == 21
    assert chapter_for_icd10cm_code("U07") == 22


def test_load_codes_file_and_chapter_filter(tmp_path: Path) -> None:
    sample = tmp_path / "icd10cm-codes-2026.txt"
    sample.write_text(
        "\n".join(
            [
                "A000     Cholera due to Vibrio cholerae 01, biovar cholerae",
                "A001     Cholera due to Vibrio cholerae 01, biovar eltor",
                "C509     Malignant neoplasm of breast of unspecified site",
                "F329     Major depressive disorder, single episode, unspecified",
                "",  # blank line should be skipped
            ]
        )
    )
    df = load_codes_file(sample)
    assert len(df) == 4
    assert set(df.columns) == {"code", "code_nodot", "title", "chapter"}
    assert df.iloc[0]["code"] == "A00.0"
    assert df.iloc[0]["chapter"] == 1

    ch1 = load_chapter(sample, 1)
    assert len(ch1) == 2
    assert all(ch1["chapter"] == 1)
