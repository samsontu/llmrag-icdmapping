"""WHO ICD-10 -> ICD-11 mapping table (2026 release) and the ICD-10-CM bridge.

The table `10To11MapToOneCategory.xlsx` gives, for every WHO ICD-10 code, the
ICD-11 Foundation URI and the MMS linearization URI + code (or cluster, e.g.
'1A00&XN8P1'). It is the gold/silver source for this project.

ICD-10-CM is a US clinical modification of WHO ICD-10, so most CM codes extend a
WHO category: S72.001A -> S72.0. `who_ancestor_for_cm()` walks a CM code up to the
nearest code present in the WHO table. Check titles when it matters: a few CM codes
reuse a position with a different meaning, and the WHO target is for the ancestor,
so the CM-specific detail (laterality, encounter) is what postcoordination must add.

In the 2026 table, all 351 clusters sit on rows whose Foundation entity aggregates
into another MMS entity, and those are only ~5% of the 7,082 aggregated rows; the
rest are residuals (5,403) or bare stems (1,427). So the table is silver for
"Foundation is MMS" rows but not for postcoordinating aggregated targets.

Usage:
    table = load_10to11()                 # categories only, snake_case columns
    who_code, level = who_ancestor_for_cm("S72.001A", set(table.icd10_code))
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from icd_mapper.config import settings

COLUMNS = {
    "10ClassKind": "icd10_class_kind",
    "10DepthInKind": "icd10_depth",
    "icd10Code": "icd10_code",
    "icd10Chapter": "icd10_chapter",
    "icd10Title": "icd10_title",
    "11ClassKind": "icd11_class_kind",
    "11DepthInKind": "icd11_depth",
    "ICD-11 FoundationURI": "foundation_uri",
    "Linearization (releaseURI)": "mms_uri",
    "icd11Code": "icd11_code",
    "icd11Chapter": "icd11_chapter",
    "icd11Title": "icd11_title",
}


def load_10to11(
    path: Path | None = None,
    *,
    class_kinds: tuple[str, ...] = ("category",),
) -> pd.DataFrame:
    """Load the WHO 10->11 table with snake_case columns and derived flags.

    By default keeps only `category` rows (drops chapters, blocks and
    `modifiedcategory`). Adds:
      - is_cluster: icd11_code contains '&' or '/'
      - is_residual: mms_uri ends in /unspecified or /other
      - foundation_is_mms: the Foundation entity is itself the MMS entity
    """
    path = path or settings.who_mapping_table
    df = pd.read_excel(path, dtype=str).rename(columns=COLUMNS)
    df = df[list(COLUMNS.values())]
    if class_kinds:
        df = df[df.icd10_class_kind.isin(class_kinds)]
    return add_flags(df.fillna("")).reset_index(drop=True)


def add_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns to a table with foundation_uri, mms_uri and icd11_code.

    - is_cluster, is_residual, foundation_is_mms (see `load_10to11`)
    - silver_target_type: what the WHO table itself did with the row
        foundation_is_mms           Foundation entity is the MMS category
        aggregated_postcoordinated  aggregated, and the table gives a cluster
        aggregated_bare             aggregated, bare stem or residual: needs review
                                    (-> aggregated_postcoordinated or aggregated_detail_lost)
        none                        no ICD-11 code in the table
    """
    df = df.copy()
    df["is_cluster"] = df.icd11_code.str.contains(r"[&/]", regex=True)
    df["is_residual"] = df.mms_uri.str.endswith(("/unspecified", "/other"))
    foundation_id = df.foundation_uri.str.rsplit("/", n=1).str[-1]
    mms_id = df.mms_uri.str.split("/mms/", n=1).str[-1]
    df["foundation_is_mms"] = foundation_id == mms_id
    df["silver_target_type"] = "aggregated_bare"
    df.loc[df.is_cluster, "silver_target_type"] = "aggregated_postcoordinated"
    df.loc[df.foundation_is_mms, "silver_target_type"] = "foundation_is_mms"
    df.loc[df.icd11_code == "", "silver_target_type"] = "none"
    return df


def who_ancestor_for_cm(cm_code: str, who_codes: set[str]) -> tuple[str | None, str]:
    """Return (nearest WHO ICD-10 code, match level) for an ICD-10-CM code.

    match level is 'exact' when the CM code itself is in the WHO table,
    'ancestor' when a truncation is, and 'none' otherwise.
    Accepts dotted ('S72.001A') or undotted ('S72001A') input.
    """
    code = cm_code.strip().upper().replace(".", "")
    if len(code) < 3:
        return None, "none"
    for end in range(len(code), 2, -1):
        stem = code[:end]
        dotted = stem if len(stem) == 3 else f"{stem[:3]}.{stem[3:]}"
        if dotted in who_codes:
            return dotted, "exact" if end == len(code) else "ancestor"
    return None, "none"
