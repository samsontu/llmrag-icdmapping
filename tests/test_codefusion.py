"""Tests for the CodeFusion wrapper: command line and output parsing (no binary needed)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from icd_mapper.codefusion import (
    CodeFusionConfig,
    build_command,
    cluster_candidates,
    find_output,
    read_output,
)


def _flag(cmd: list[str], name: str) -> str:
    return cmd[cmd.index(name) + 1]


def test_build_command_free_and_default() -> None:
    exe = Path("/opt/codefusion/CodeFusion")
    inp = Path("/tmp/ch01.txt")
    default = build_command(inp, CodeFusionConfig(executable=exe, use_free_postcoordination=False))
    free = build_command(
        inp,
        CodeFusionConfig(
            executable=exe,
            version="2026",
            use_free_postcoordination=True,
            subtree_filter=["http://id.who.int/icd/entity/1435254666"],
        ),
    )
    assert default[0] == str(exe)
    assert _flag(default, "--useFreePostcoordinationMatching") == "false"
    assert _flag(free, "--useFreePostcoordinationMatching") == "true"
    assert _flag(free, "--source") == "MMS"
    assert _flag(free, "--version") == "2026"
    assert _flag(free, "--columnNo") == "2"
    assert _flag(free, "--subtreeFilter").endswith("1435254666")
    assert CodeFusionConfig(use_free_postcoordination=True).mode == "free"


def test_read_output_and_cluster_candidates(tmp_path: Path) -> None:
    inp = tmp_path / "ch01.txt"
    inp.write_text("id\ttitle\n")
    out = tmp_path / "ch01-checked.xlsx"
    pd.DataFrame(
        {
            "id": ["A00.0", "A00.0", "A01.0"],
            "title": ["Cholera due to ...", "Cholera due to ...", "Typhoid fever"],
            "MatchLevel": ["GoodMatch", "GoodMatchWithFreePostcoordination", "GoodMatch"],
            "Score": ["0.81", "0.93", "0.97"],
            "MatchType": ["PostCoordinationCombination", "PostCoordinationCombination", "Real"],
            "BestMatchPhrase": ["cholera", "cholera vibrio", "typhoid fever"],
            "LinearizationURI": ["", "", ""],
            "Code": ["1A00&XN8P1", "1A00&XN8P1&XN6D2", "1A07.Z"],
            "FoundationURI": [
                "http://id.who.int/icd/entity/1205958647",
                "http://id.who.int/icd/entity/1205958647",
                "http://id.who.int/icd/entity/1",
            ],
        }
    ).to_excel(out, index=False)

    assert find_output(inp) == out
    df = read_output(out)
    assert df.is_cluster.tolist() == [True, True, False]
    assert df.is_free_postcoordination.tolist() == [False, True, False]
    cands = cluster_candidates(df, "A00.0")
    assert [c["code"] for c in cands] == ["1A00&XN8P1&XN6D2", "1A00&XN8P1"]
    assert cluster_candidates(df, "A01.0") == []
