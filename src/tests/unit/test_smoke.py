from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from app.service import DemoService
from mssql_python import Error as SqlError
from mssql_python import ProgrammingError
from validation import runtime_smoke
from validation.http_smoke import check_http, validate_url


def runtime_fixture() -> Mock:
    service = DemoService()
    runtime = Mock()
    runtime.store.customer_history.return_value = [
        service.get_claim("clm-demo-001"),
        service.get_claim("clm-demo-002"),
    ]
    runtime.store.add_review_note.return_value = "synthetic-note"
    cursor = runtime.store.connect.return_value.cursor.return_value
    cursor.execute.side_effect = ProgrammingError(
        "Syntax error or access violation",
        "[Microsoft][SQL Server]The UPDATE permission was denied on the object 'Claim', "
        "database 'claims', schema 'claims'.",
    )
    runtime.service.lookup_policy.return_value = service.lookup_policy("pol-demo-auto", "animal")
    return runtime


def blob_fixture() -> Mock:
    blobs = Mock()
    blobs.__enter__ = Mock(return_value=blobs)
    blobs.__exit__ = Mock(return_value=None)
    blobs.get_blob_client.return_value.download_blob.return_value.readall.return_value = Path(
        "data/policies/demo-auto-policy.md"
    ).read_bytes()
    return blobs


def test_runtime_smoke_checks_actual_denial_and_citation_content() -> None:
    with patch.object(runtime_smoke, "BlobServiceClient", return_value=blob_fixture()):
        checks = runtime_smoke.check_data_plane(runtime_fixture(), "demostorage")
    assert len(checks) == 5
    assert all(check["passed"] for check in checks)


@pytest.mark.parametrize(
    "error",
    [
        None,
        SqlError("28000", "Login failed (18456)"),
        ProgrammingError("Syntax error or access violation", "Invalid object name 'claims.Claim'."),
        ProgrammingError("Syntax error or access violation", "Unrelated SQL failure (229)"),
        ProgrammingError(
            "Syntax error or access violation",
            "[Microsoft][SQL Server]The UPDATE permission was denied on the object 'Policy', "
            "database 'claims', schema 'claims'.",
        ),
    ],
)
def test_sql_smoke_never_calls_success_or_login_failure_a_permission_denial(error) -> None:
    runtime = runtime_fixture()
    runtime.store.connect.return_value.cursor.return_value.execute.side_effect = error
    with patch.object(runtime_smoke, "BlobServiceClient", return_value=blob_fixture()):
        checks = runtime_smoke.check_data_plane(runtime, "demostorage")
    denied = next(check for check in checks if check["name"] == "denied-claim-update")
    assert denied["passed"] is False


def test_smoke_cannot_use_fixtures_or_call_unrelated_hosts(monkeypatch, capsys) -> None:
    monkeypatch.setenv("CLAIMS_MODE", "local")
    assert runtime_smoke.main() == 1
    assert json.loads(capsys.readouterr().out)["passed"] is False
    for url in (
        "http://demo.azure-api.net",
        "https://attacker.example",
        "https://demo.azure-api.net.attacker.example",
        "https://demo.azure-api.net?token=secret",
        "https://user:password@demo.azure-api.net",
        "https://demo.azure-api.net:444",
    ):
        with pytest.raises(ValueError):
            validate_url(url)
    assert validate_url("https://demo.azure-api.net/claims/") == "https://demo.azure-api.net/claims/"


def test_runtime_smoke_rejects_missing_or_unresolvable_evidence() -> None:
    for citations in ([], [Mock(quoted_text="Invented policy content.")]):
        runtime = runtime_fixture()
        runtime.service.lookup_policy.return_value = citations
        with patch.object(runtime_smoke, "BlobServiceClient", return_value=blob_fixture()):
            checks = runtime_smoke.check_data_plane(runtime, "demostorage")
        assert checks[-1]["passed"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("mode, expected", [("azure", True), ("local", False)])
@pytest.mark.parametrize(
    "mcp_url",
    [None, "https://demo.azure-api.net/claims-tools/mcp", "https://demo.azure-api.net/claims-tools/mcp/"],
)
@pytest.mark.parametrize("valid_evidence", [True, False])
async def test_http_smoke_requires_an_authenticated_azure_runtime(
    mode, expected, mcp_url, valid_evidence
) -> None:
    http = AsyncMock()
    http.__aenter__.return_value = http

    async def get(url, **kwargs):
        request = httpx.Request("GET", url)
        if url.endswith("/ready"):
            assert "Authorization" in kwargs["headers"]
            return httpx.Response(200, json={"status": "ready", "mode": mode}, request=request)
        assert "headers" not in kwargs
        return httpx.Response(401, request=request)

    http.get.side_effect = get
    http.post.return_value = httpx.Response(401)
    mcp = AsyncMock()
    mcp.__aenter__.return_value = mcp
    mcp.list_tools.return_value = [
        SimpleNamespace(name=name)
        for name in (
            "lookup_policy",
            "assess_synthetic_claim",
            "synthetic_customer_history",
            "add_synthetic_review_note",
        )
    ]
    service = DemoService()
    citations = [
        citation.model_dump(mode="json", by_alias=True)
        for citation in service.lookup_policy("pol-demo-auto", "animal")
    ]
    mcp.call_tool.side_effect = [
        SimpleNamespace(data=citations if valid_evidence else [{"citationId": "cit-demo-001"}]),
        SimpleNamespace(
            data=service.assess_claim("clm-demo-001").model_dump(mode="json", by_alias=True)
        ),
    ]
    with (
        patch("validation.http_smoke.httpx.AsyncClient", return_value=http),
        patch("validation.http_smoke.Client", return_value=mcp),
        patch("validation.http_smoke.StreamableHttpTransport") as transport,
    ):
        checks = await check_http(
            "https://demo.azure-api.net/claims", "synthetic-test-token", mcp_url
        )
    expected_mcp_url = mcp_url or "https://demo.azure-api.net/claims/mcp/"
    http.post.assert_awaited_once_with(expected_mcp_url)
    assert transport.call_args.args == (expected_mcp_url,)
    assert all(check["passed"] for check in checks) is (expected and valid_evidence)
    assert len(checks) == 3
    assert mcp.list_tools.await_count == 1
    assert mcp.call_tool.await_count == (2 if valid_evidence else 1)


@pytest.mark.asyncio
async def test_http_smoke_rejects_mismatched_gateway_hosts_before_network_calls() -> None:
    with (
        patch("validation.http_smoke.httpx.AsyncClient") as http,
        pytest.raises(ValueError, match="same HTTPS gateway host"),
    ):
        await check_http(
            "https://demo.azure-api.net/claims",
            "synthetic-test-token",
            "https://another.azure-api.net/mcp",
        )
    http.assert_not_called()
