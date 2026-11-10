"""Tests for the ICD-11 client — no network calls, no real credentials.

We mock the WHO endpoints with `respx` and verify that:
- the OAuth token request is made correctly,
- a Foundation entity response is normalized into ICD11Entity,
- responses are cached on disk so a second call doesn't hit the network.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx

from icd_mapper.icd11_client import ICD11Client

TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
BASE_URL = "https://id.who.int/icd"

SAMPLE_ENTITY = {
    "@id": "http://id.who.int/icd/entity/1435254666",
    "title": {"@language": "en", "@value": "Certain infectious or parasitic diseases"},
    "definition": {
        "@language": "en",
        "@value": "A group of diseases caused by pathogenic organisms.",
    },
    "synonym": [{"@language": "en", "@value": "Infections"}],
    "child": [
        "http://id.who.int/icd/entity/123",
        "http://id.who.int/icd/entity/456",
    ],
    "parent": [],
}


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "icd11_cache"


@pytest.fixture
def client(temp_cache_dir: Path) -> Iterator[ICD11Client]:
    c = ICD11Client(
        client_id="fake-id",
        client_secret="fake-secret",
        cache_dir=str(temp_cache_dir),
    )
    try:
        yield c
    finally:
        # Synchronous close of the disk cache; the http client is closed by the
        # async context manager in real usage, but it has no on-disk side effects.
        c._cache.close()


async def test_get_entity_normalizes_and_caches(client: ICD11Client) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        )
        route = router.get(f"{BASE_URL}/entity/1435254666").mock(
            return_value=httpx.Response(200, json=SAMPLE_ENTITY)
        )

        e1 = await client.get_entity("1435254666")
        assert e1.entity_id == "1435254666"
        assert e1.title == "Certain infectious or parasitic diseases"
        assert "Infections" in e1.synonyms
        assert e1.children == ["123", "456"]
        assert route.call_count == 1

        # Second call should be served from disk cache → no extra network hit.
        e2 = await client.get_entity("1435254666")
        assert e2.entity_id == e1.entity_id
        assert route.call_count == 1

    await client._http.aclose()


async def test_token_is_fetched_only_once(client: ICD11Client) -> None:
    with respx.mock(assert_all_called=False) as router:
        token_route = router.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        )
        router.get(f"{BASE_URL}/entity/123").mock(
            return_value=httpx.Response(
                200, json={**SAMPLE_ENTITY, "@id": "http://id.who.int/icd/entity/123"}
            )
        )
        router.get(f"{BASE_URL}/entity/456").mock(
            return_value=httpx.Response(
                200, json={**SAMPLE_ENTITY, "@id": "http://id.who.int/icd/entity/456"}
            )
        )

        await client.get_entity("123")
        await client.get_entity("456")
        assert token_route.call_count == 1

    await client._http.aclose()


SAMPLE_LOOKUP = {
    "@id": "http://id.who.int/icd/release/11/2026-01/mms/257068234",
    "code": "1A00",
    "title": {"@language": "en", "@value": "Cholera"},
    "postcoordinationScale": [
        {
            "axisName": "http://id.who.int/icd/schema/infectiousAgent",
            "requiredPostcoordination": "false",
            "allowMultipleValues": "AllowAlways",
            "scaleEntity": ["http://id.who.int/icd/release/11/2026-01/mms/1205958647"],
        }
    ],
}


async def test_mms_lookup_derives_code_and_axes(temp_cache_dir: Path) -> None:
    c = ICD11Client(
        client_id="fake-id",
        client_secret="fake-secret",
        release_id="2026-01",
        cache_dir=str(temp_cache_dir),
    )
    with respx.mock(assert_all_called=False) as router:
        router.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        )
        route = router.get(
            f"{BASE_URL}/release/11/2026-01/mms/lookup",
            params={"foundationUri": "http://id.who.int/icd/entity/1205958647"},
        ).mock(return_value=httpx.Response(200, json=SAMPLE_LOOKUP))

        d = await c.mms_lookup("1205958647")
        assert route.call_count == 1
        assert d.foundation_uri == "http://id.who.int/icd/entity/1205958647"
        assert d.code == "1A00"
        assert d.title == "Cholera"
        assert not d.is_residual
        assert d.axes[0].axis_name.endswith("infectiousAgent")
        assert not d.requires_postcoordination

    await c.aclose()


async def test_mms_lookup_flags_residual(temp_cache_dir: Path) -> None:
    c = ICD11Client(
        client_id="fake-id",
        client_secret="fake-secret",
        release_id="2026-01",
        cache_dir=str(temp_cache_dir),
    )
    residual = {
        "@id": "http://id.who.int/icd/release/11/2026-01/mms/1435254666/unspecified",
        "code": "1H0Z",
        "title": {"@language": "en", "@value": "Infection, unspecified"},
    }
    with respx.mock(assert_all_called=False) as router:
        router.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        )
        router.get(f"{BASE_URL}/release/11/2026-01/mms/lookup").mock(
            return_value=httpx.Response(200, json=residual)
        )
        d = await c.mms_lookup("http://id.who.int/icd/entity/1435254666")
        assert d.is_residual
        assert d.code == "1H0Z"
        assert d.axes == []

    await c.aclose()


async def test_codeinfo_encodes_cluster(temp_cache_dir: Path) -> None:
    c = ICD11Client(
        client_id="fake-id",
        client_secret="fake-secret",
        release_id="2026-01",
        cache_dir=str(temp_cache_dir),
    )
    with respx.mock(assert_all_called=False) as router:
        router.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        )
        route = router.get(f"{BASE_URL}/release/11/2026-01/mms/codeinfo/1A00%26XN8P1").mock(
            return_value=httpx.Response(200, json={"code": "1A00&XN8P1"})
        )
        info = await c.codeinfo("1A00&XN8P1")
        assert info["code"] == "1A00&XN8P1"
        assert route.call_count == 1

    await c.aclose()
