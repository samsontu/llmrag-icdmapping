"""Tests for the ICD-10-CM -> WHO ICD-10 bridge (pure function, no files)."""

from __future__ import annotations

import pytest

from icd_mapper.who_map import who_ancestor_for_cm

WHO = {"A00", "A00.0", "S72", "S72.0", "F32", "F32.0"}


@pytest.mark.parametrize(
    ("cm", "expected"),
    [
        ("A00.0", ("A00.0", "exact")),
        ("A000", ("A00.0", "exact")),
        ("S72.001A", ("S72.0", "ancestor")),
        ("F32.A", ("F32", "ancestor")),
        ("Z99.9", (None, "none")),
        ("A0", (None, "none")),
    ],
)
def test_who_ancestor_for_cm(cm: str, expected: tuple[str | None, str]) -> None:
    assert who_ancestor_for_cm(cm, WHO) == expected


def test_add_flags_silver_target_type() -> None:
    import pandas as pd

    from icd_mapper.who_map import add_flags

    base = "http://id.who.int/icd/release/11/2026-01/mms/"
    df = pd.DataFrame(
        {
            "foundation_uri": [
                "http://id.who.int/icd/entity/257068234",  # same as MMS
                "http://id.who.int/icd/entity/1205958647",  # aggregated + cluster
                "http://id.who.int/icd/entity/588616678",  # aggregated, bare
                "http://id.who.int/icd/entity/1",  # no code
            ],
            "mms_uri": [f"{base}257068234", f"{base}257068234", f"{base}1688127370", ""],
            "icd11_code": ["1A00", "1A00&XN8P1", "1A40", ""],
        }
    )
    out = add_flags(df)
    assert list(out.silver_target_type) == [
        "foundation_is_mms",
        "aggregated_postcoordinated",
        "aggregated_bare",
        "none",
    ]
