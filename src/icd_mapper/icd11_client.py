"""Async client for the WHO ICD-11 API.

- OAuth 2.0 client-credentials flow against icdaccessmanagement.who.int.
- Caches the bearer token in memory until expiry.
- Caches entity responses on disk via `diskcache` so repeated runs don't
  hammer the API.

Reference: https://icd.who.int/icdapi/docs2/

Usage:
    async with ICD11Client() as client:
        entity = await client.get_entity("1435254666")
        children = await client.get_children("1435254666")
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from diskcache import Cache

from icd_mapper.config import settings
from icd_mapper.types import ICD11Entity

log = logging.getLogger(__name__)

ENTITY_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
TOKEN_LEEWAY_SECONDS = 30  # refresh slightly before expiry


def _entity_id_from_iri(iri: str) -> str:
    """Extract the trailing integer from an ICD-11 IRI."""
    return iri.rstrip("/").rsplit("/", 1)[-1]


class ICD11Client:
    """Thin async wrapper over the WHO ICD-11 REST API."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        language: str | None = None,
        api_version: str | None = None,
        base_url: str | None = None,
        token_url: str | None = None,
        cache_dir: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.client_id = client_id or settings.icd11_client_id
        secret = client_secret or (
            settings.icd11_client_secret.get_secret_value()
            if settings.icd11_client_secret
            else None
        )
        if not self.client_id or not secret:
            raise RuntimeError(
                "ICD-11 credentials missing. Set ICD11_CLIENT_ID and "
                "ICD11_CLIENT_SECRET in .env. Register at "
                "https://icd.who.int/icdapi."
            )
        self._client_secret = secret
        self.language = language or settings.icd11_language
        self.api_version = api_version or settings.icd11_api_version
        self.base_url = (base_url or settings.icd11_base_url).rstrip("/")
        self.token_url = token_url or settings.icd11_token_url

        cache_path = cache_dir or str(settings.icd_cache_dir / "icd11")
        self._cache = Cache(cache_path)

        self._http = httpx.AsyncClient(timeout=timeout)
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def __aenter__(self) -> ICD11Client:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        self._cache.close()

    # ---- token ----

    async def _fetch_token(self) -> str:
        log.debug("Fetching new ICD-11 access token")
        resp = await self._http.post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self._client_secret,
                "scope": "icdapi_access",
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        # `expires_in` is seconds; subtract leeway to refresh early.
        self._token_expires_at = (
            time.monotonic() + float(payload["expires_in"]) - TOKEN_LEEWAY_SECONDS
        )
        return self._token

    async def _ensure_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        return await self._fetch_token()

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Accept-Language": self.language,
            "API-Version": self.api_version,
        }

    # ---- core requests ----

    async def _get(self, path: str) -> dict[str, Any]:
        token = await self._ensure_token()
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        cache_key = f"GET::{self.language}::{self.api_version}::{url}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        resp = await self._http.get(url, headers=self._headers(token))
        resp.raise_for_status()
        data = resp.json()
        self._cache.set(cache_key, data, expire=ENTITY_TTL_SECONDS)
        return data

    # ---- public API ----

    async def get_entity_raw(self, entity_id: str) -> dict[str, Any]:
        """Return the raw JSON for a Foundation entity."""
        return await self._get(f"/entity/{entity_id}")

    async def get_entity(self, entity_id: str) -> ICD11Entity:
        """Return a normalized ICD11Entity for the given Foundation entity."""
        raw = await self.get_entity_raw(entity_id)
        return _entity_from_raw(raw)

    async def get_children(self, entity_id: str) -> list[str]:
        """Return list of child entity IDs (IRIs extracted)."""
        raw = await self.get_entity_raw(entity_id)
        return [_entity_id_from_iri(c) for c in raw.get("child", [])]

    async def get_parents(self, entity_id: str) -> list[str]:
        raw = await self.get_entity_raw(entity_id)
        return [_entity_id_from_iri(p) for p in raw.get("parent", [])]

    async def search(
        self,
        query: str,
        *,
        chapter_filter: str | None = None,
        flat_results: bool = True,
        use_flexisearch: bool = True,
    ) -> dict[str, Any]:
        """Search Foundation. Returns the raw search response (no caching).

        Useful for week-3 onwards; the search endpoint is mutable so we don't cache.
        """
        token = await self._ensure_token()
        params: dict[str, Any] = {
            "q": query,
            "useFlexisearch": str(use_flexisearch).lower(),
            "flatResults": str(flat_results).lower(),
        }
        if chapter_filter:
            params["chapterFilter"] = chapter_filter
        resp = await self._http.get(
            f"{self.base_url}/entity/search",
            headers=self._headers(token),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def walk_descendants(self, entity_id: str, *, max_nodes: int = 5000) -> list[ICD11Entity]:
        """BFS over the Foundation tree starting at `entity_id`.

        Returns each visited entity once. Use for caching a whole chapter.
        """
        seen: set[str] = set()
        out: list[ICD11Entity] = []
        queue: list[str] = [entity_id]
        while queue and len(out) < max_nodes:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            entity = await self.get_entity(current)
            out.append(entity)
            queue.extend(c for c in entity.children if c not in seen)
        if len(out) >= max_nodes:
            log.warning("walk_descendants hit max_nodes=%d for %s", max_nodes, entity_id)
        return out


# ---- helpers ----


def _entity_from_raw(raw: dict[str, Any]) -> ICD11Entity:
    """Normalize the WHO API JSON into our ICD11Entity model.

    WHO returns titles and definitions as `{ "@language": "en", "@value": "..." }`
    objects; synonyms and inclusions are lists of such objects.
    """
    iri = raw["@id"]
    entity_id = _entity_id_from_iri(iri)

    title = _localized(raw.get("title"))
    definition = _localized(raw.get("definition"))
    synonyms = [_localized(s) for s in raw.get("synonym", []) if _localized(s)]
    inclusions = [_localized(s) for s in raw.get("inclusion", []) if _localized(s)]
    exclusions = [_localized(s) for s in raw.get("exclusion", []) if _localized(s)]
    parents = [_entity_id_from_iri(p) for p in raw.get("parent", [])]
    children = [_entity_id_from_iri(c) for c in raw.get("child", [])]
    code = raw.get("code")

    return ICD11Entity(
        entity_id=entity_id,
        iri=iri,
        title=title or "(untitled)",
        definition=definition,
        synonyms=synonyms,
        inclusions=inclusions,
        exclusions=exclusions,
        parents=parents,
        children=children,
        code=code,
    )


def _localized(value: Any) -> str | None:
    """Pull `@value` out of a WHO localized object, or return the value as-is."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("@value") or value.get("label", {}).get("@value")
    return None
