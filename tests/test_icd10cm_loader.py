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


def test_chapter_for_codes_with_letter_in_third_position() -> None:
    assert chapter_for_icd10cm_code("D3A") == 2  # neuroendocrine tumors, in D00-D49
    assert chapter_for_icd10cm_code("D3A01") == 2
    assert chapter_for_icd10cm_code("H59") == 7
    assert chapter_for_icd10cm_code("H60") == 8


TTL_SAMPLE = '''@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .

<http://purl.bioontology.org/ontology/ICD10CM/>
    a owl:Ontology ;
    owl:versionInfo "2026" .

<http://purl.bioontology.org/ontology/ICD10CM/ICD-10-CM> a owl:Class ;
\tskos:prefLabel """ICD-10-CM TABULAR LIST of DISEASES and INJURIES"""@en ;
\tskos:notation """ICD-10-CM"""^^xsd:string ;
\trdfs:subClassOf owl:Thing ;
 .

<http://purl.bioontology.org/ontology/ICD10CM/A00-B99> a owl:Class ;
\tskos:prefLabel """Certain infectious and parasitic diseases (A00-B99)"""@en ;
\tskos:notation """A00-B99"""^^xsd:string ;
\trdfs:subClassOf owl:Thing ;
 .

<http://purl.bioontology.org/ontology/ICD10CM/A00-A09> a owl:Class ;
\tskos:prefLabel """Intestinal infectious diseases (A00-A09)"""@en ;
\tskos:notation """A00-A09"""^^xsd:string ;
\trdfs:subClassOf <http://purl.bioontology.org/ontology/ICD10CM/A00-B99> ;
 .

<http://purl.bioontology.org/ontology/ICD10CM/A00> a owl:Class ;
\tskos:prefLabel """Cholera"""@en ;
\tskos:notation """A00"""^^xsd:string ;
\trdfs:subClassOf <http://purl.bioontology.org/ontology/ICD10CM/A00-A09> ;
 .

<http://purl.bioontology.org/ontology/ICD10CM/A00.0> a owl:Class ;
\tskos:prefLabel """Cholera due to Vibrio cholerae 01, biovar cholerae"""@en ;
\tskos:notation """A00.0"""^^xsd:string ;
\tskos:altLabel """Classical cholera"""@en , """\\"Asiatic\\" cholera"""@en , """Classical cholera"""@en ;
\trdfs:subClassOf <http://purl.bioontology.org/ontology/ICD10CM/A00> ;
 .

<http://purl.bioontology.org/ontology/ICD10CM/A00.1> a owl:Class ;
\tskos:prefLabel """Cholera due to Vibrio cholerae 01, biovar eltor"""@en ;
\tskos:notation """A00.1"""^^xsd:string ;
\trdfs:subClassOf <http://purl.bioontology.org/ontology/ICD10CM/A00> ;
 .

<http://purl.bioontology.org/ontology/ICD10CM/D3A.01> a owl:Class ;
\tskos:prefLabel """Benign carcinoid tumors of the small intestine"""@en ;
\tskos:notation """D3A.01"""^^xsd:string ;
\trdfs:subClassOf owl:Thing ;
 .
'''


def _write_ttl(tmp_path: Path) -> Path:
    path = tmp_path / "ICD10CM.ttl"
    path.write_text(TTL_SAMPLE, encoding="utf-8")
    return path


def test_load_ttl_levels_leaves_and_synonyms(tmp_path: Path) -> None:
    from icd_mapper.icd10cm_loader import load_ttl

    df = load_ttl(_write_ttl(tmp_path)).set_index("code")
    assert "ICD-10-CM" not in df.index  # root class skipped
    assert df.loc["A00-B99", "kind"] == "chapter"
    assert df.loc["A00-A09", "kind"] == "block"
    assert df.loc["A00", "kind"] == "category"
    assert not df.loc["A00", "is_leaf"]
    assert df.loc["A00.0", "is_leaf"]
    assert df.loc["A00.0", "parent"] == "A00"
    assert df.loc["A00.0", "code_nodot"] == "A000"
    assert df.loc["A00.0", "synonyms"] == ["Classical cholera", '"Asiatic" cholera']
    assert df.loc["A00.1", "synonyms"] == []
    assert df.loc["D3A.01", "chapter"] == 2


def test_load_chapter_from_ttl_and_default_path(tmp_path: Path, monkeypatch) -> None:
    from icd_mapper import icd10cm_loader
    from icd_mapper.config import settings

    ttl = _write_ttl(tmp_path)
    leaves = icd10cm_loader.load_chapter(ttl, 1)
    assert leaves["code"].tolist() == ["A00.0", "A00.1"]
    all_levels = icd10cm_loader.load_chapter(ttl, 1, leaves_only=False)
    assert set(all_levels["code"]) == {"A00-B99", "A00-A09", "A00", "A00.0", "A00.1"}

    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(settings, "icd_data_dir", tmp_path)
    (raw / "ICD10CM.ttl").write_text(TTL_SAMPLE, encoding="utf-8")
    assert icd10cm_loader.default_codes_path().name == "ICD10CM.ttl"
    (raw / "icd10cm-codes-2026.txt").write_text("A000    Cholera\n", encoding="utf-8")
    assert icd10cm_loader.default_codes_path().name == "icd10cm-codes-2026.txt"
