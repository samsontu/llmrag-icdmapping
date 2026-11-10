"""Run WHO CodeFusion in batch and read its matches, including postcoordination clusters.

CodeFusion (https://icd.who.int/docs/codefusion/en/user-guide/) matches phrases in an
input file against an ICD classification and writes a `-checked` output file. With a
linearization source (MMS) it reports postcoordination combinations:

- MatchType `PostCoordinationCombination`: the match "can be represented as a
  postcoordination combination" (Code holds the code or cluster string).
- MatchLevel `GoodMatchWithFreePostcoordination`: free matching found "multiple
  entities jointly matching the text" (only with free matching on).

`useFreePostcoordinationMatching`:
- False (CodeFusion's default): only the postcoordination axes the classification
  *suggests* for an entity are tried.
- True: CodeFusion "tries to find any postcoordination combination" without that
  constraint. Useful for precoordinated source concepts that ICD-11 can only express
  as a cluster, at the cost of more (and noisier) combinations.

Clusters are not reported with `source="foundation"`, so this wrapper uses MMS.
CodeFusion proposes; the pipeline still validates every cluster with ICD-API
`codeinfo` and records where it came from (`MappingProposal.cluster_source`).

CodeFusion is a desktop binary (macOS/Windows/Linux builds), so `run()` works on the
machine where it is installed; set CODEFUSION_PATH in .env. Run it once per chapter
and per mode, and cache the parsed results (`data/codefusion/chNN_{default,free}.parquet`).

The command-line flags below follow the user guide's "--name value" form; run
`CodeFusion --help` once to confirm them for your build.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from icd_mapper.config import settings

OUTPUT_COLUMNS = {
    "MatchLevel": "match_level",
    "Score": "score",
    "MatchType": "match_type",
    "BestMatchPhrase": "best_match_phrase",
    "LinearizationURI": "linearization_uri",
    "Code": "code",
    "FoundationURI": "foundation_uri",
}

POSTCOORD_MATCH_TYPE = "PostCoordinationCombination"
FREE_POSTCOORD_LEVEL = "GoodMatchWithFreePostcoordination"


@dataclass
class CodeFusionConfig:
    executable: Path | None = None
    version: str | None = None  # default: CODEFUSION_VERSION (2026)
    source: str = "MMS"  # clusters are only reported for a linearization source
    language: str = "en"
    use_free_postcoordination: bool | None = None  # default: CODEFUSION_FREE_POSTCOORDINATION
    match_threshold: float | None = None  # CodeFusion default 0.43
    subtree_filter: list[str] = field(default_factory=list)  # Foundation URIs
    timeout_s: int = 3600

    def resolved_executable(self) -> Path:
        exe = self.executable or settings.codefusion_path
        if not exe:
            raise RuntimeError(
                "CodeFusion executable not set. Put CODEFUSION_PATH in .env, e.g. "
                "/Users/tu/Downloads/codefusion_osx-x64/CodeFusion"
            )
        return Path(exe)

    @property
    def resolved_version(self) -> str:
        return self.version or settings.codefusion_version

    @property
    def free(self) -> bool:
        if self.use_free_postcoordination is None:
            return settings.codefusion_free_postcoordination
        return self.use_free_postcoordination

    @property
    def mode(self) -> str:
        """'free' or 'default': use in cache file names and `cluster_source`."""
        return "free" if self.free else "default"


def write_input(rows: pd.DataFrame, path: Path, *, text_column: str = "title") -> Path:
    """Write an input file for CodeFusion: tab-separated, header row, id first.

    `rows` needs an `id` column (e.g. the ICD-10-CM code) and a text column. The id
    column lets you join results back; CodeFusion matches column `text_column`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rows[["id", text_column]].to_csv(path, sep="\t", index=False)
    return path


def build_command(input_path: Path, config: CodeFusionConfig, *, column_no: int = 2) -> list[str]:
    """CodeFusion command line for one batch (input written by `write_input`)."""
    args = [
        str(config.resolved_executable()),
        "--inputFile", input_path.as_posix(),
        "--columnNo", str(column_no),
        "--fileContainsHeader", "true",
        "--version", config.resolved_version,
        "--source", config.source,
        "--language", config.language,
        "--useFreePostcoordinationMatching", str(config.free).lower(),
        "--includeScoreInOutput", "true",
        "--exitWhenFinished", "true",
    ]
    if config.match_threshold is not None:
        args += ["--matchThreshold", str(config.match_threshold)]
    if config.subtree_filter:
        args += ["--subtreeFilter", ",".join(config.subtree_filter)]
    return args


def find_output(input_path: Path) -> Path:
    """Locate the `-checked` (or `_checked`) Excel output next to the input file."""
    for sep in ("-", "_"):
        candidate = input_path.with_name(f"{input_path.stem}{sep}checked.xlsx")
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No CodeFusion output found for {input_path}")


def run(input_path: Path, config: CodeFusionConfig) -> Path:
    """Run CodeFusion on `input_path` and return the path of its checked output."""
    exe = config.resolved_executable()
    subprocess.run(
        build_command(input_path, config),
        cwd=exe.parent,  # CodeFusion reads its own folder (parameters.json, caches)
        check=True,
        timeout=config.timeout_s,
    )
    return find_output(input_path)


def read_output(path: Path) -> pd.DataFrame:
    """Read a CodeFusion `-checked` file into snake_case columns plus flags.

    Input columns are kept as they were written (e.g. `id`, `title`). Adds:
      - is_cluster: Code contains '&' or '/'
      - is_postcoordination: MatchType is PostCoordinationCombination
      - is_free_postcoordination: MatchLevel is GoodMatchWithFreePostcoordination
    """
    df = pd.read_excel(path, dtype=str).rename(columns=OUTPUT_COLUMNS).fillna("")
    for col in OUTPUT_COLUMNS.values():
        if col not in df.columns:
            df[col] = ""
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["is_cluster"] = df["code"].str.contains(r"[&/]", regex=True)
    df["is_postcoordination"] = df["match_type"] == POSTCOORD_MATCH_TYPE
    df["is_free_postcoordination"] = df["match_level"] == FREE_POSTCOORD_LEVEL
    return df


def cluster_candidates(df: pd.DataFrame, source_id: str, *, id_column: str = "id") -> list[dict]:
    """Postcoordination candidates CodeFusion found for one source code, best first."""
    rows = df[(df[id_column] == source_id) & (df.is_cluster | df.is_postcoordination)]
    rows = rows.sort_values("score", ascending=False, na_position="last")
    return rows[
        ["code", "foundation_uri", "linearization_uri", "match_level", "match_type", "score"]
    ].to_dict("records")
