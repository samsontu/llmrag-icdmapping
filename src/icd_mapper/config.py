"""Centralized settings, loaded from .env via pydantic-settings.

Usage:
    from icd_mapper.config import settings
    settings.anthropic_api_key  # SecretStr — call .get_secret_value()
"""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All runtime configuration. Read once at process start; pass around explicitly."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLMs ---
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    # --- WHO ICD-11 API ---
    icd11_client_id: str | None = None
    icd11_client_secret: SecretStr | None = None
    icd11_api_version: str = "v2"
    icd11_language: str = "en"
    icd11_release_id: str = "2026-01"  # matches the 2026 WHO mapping tables
    icd11_token_url: str = "https://icdaccessmanagement.who.int/connect/token"
    icd11_base_url: str = "https://id.who.int/icd"

    # --- WHO CodeFusion (desktop binary; proposes postcoordination clusters) ---
    codefusion_path: Path | None = None  # e.g. .../codefusion_osx-x64/CodeFusion
    codefusion_version: str = "2026"
    codefusion_free_postcoordination: bool = False  # useFreePostcoordinationMatching

    # --- Paths ---
    icd_data_dir: Path = REPO_ROOT / "data"
    icd_cache_dir: Path = REPO_ROOT / "data" / ".cache"
    # WHO 2026 release mapping table (ICD-10 -> ICD-11), the gold/silver source.
    who_mapping_table: Path = REPO_ROOT / "data" / "raw" / "10To11MapToOneCategory.xlsx"

    # --- Budget ---
    daily_llm_budget_usd: float = 5.00

    def ensure_dirs(self) -> None:
        """Create data + cache directories if missing. Safe to call repeatedly."""
        self.icd_data_dir.mkdir(parents=True, exist_ok=True)
        self.icd_cache_dir.mkdir(parents=True, exist_ok=True)
        (self.icd_data_dir / "raw").mkdir(parents=True, exist_ok=True)


settings = Settings()
