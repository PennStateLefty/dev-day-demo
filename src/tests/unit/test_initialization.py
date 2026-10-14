from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from app.search_rest import KnowledgeError, SearchRestClient
from app.service import DemoService
from initialize_knowledge import (
    ensure_definition,
    index_definition,
    knowledge_definition,
    policy_documents,
    seed_search,
    source_definition,
)
from initialize_sql import initialize, runtime_grants

ROOT = Path(__file__).resolve().parents[3]


def test_contained_identity_is_uuid_validated_and_least_privileged() -> None:
    grant = runtime_grants("00112233-4455-6677-8899-aabbccddeeff")
    assert "0x33221100554477668899aabbccddeeff" in grant
    assert "TYPE = E" in grant
    assert "FROM EXTERNAL PROVIDER" not in grant
    assert "db_datawriter" not in grant
    assert "db_owner" not in grant
    assert "GRANT SELECT ON OBJECT::claims.Claim" in grant
    assert "GRANT EXECUTE ON OBJECT::claims.AddReviewNote" in grant
    with pytest.raises(ValueError):
        runtime_grants("'; DROP TABLE claims.Claim;--")
    assert "DROP USER" not in grant


def test_legacy_runtime_user_repair_requires_exact_explicit_old_sid() -> None:
    client = "00112233-4455-6677-8899-aabbccddeeff"
    principal = "11223344-5566-7788-99aa-bbccddeeff00"
    grants = runtime_grants(client, principal)
    assert "sid = 0x443322116655887799aabbccddeeff00 AND type = 'E'" in grants
    assert "DROP USER claims_runtime_identity" in grants
    assert "WITH SID = 0x33221100554477668899aabbccddeeff, TYPE = E" in grants
    with pytest.raises(ValueError):
        runtime_grants(client, client)


def test_initial_sql_seed_commits_in_relational_dependency_order() -> None:
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = []
    result = initialize(lambda: connection, "00000000-0000-0000-0000-000000000001", DemoService())
    assert result == {"passed": True, "migrations_applied": 2, "records_inserted": 6}
    calls = [call.args[0] for call in cursor.execute.call_args_list]
    policy = next(i for i, sql in enumerate(calls) if sql.startswith("INSERT claims.Policy"))
    claim = next(i for i, sql in enumerate(calls) if sql.startswith("INSERT claims.Claim"))
    artifact = next(i for i, sql in enumerate(calls) if sql.startswith("INSERT claims.Artifact"))
    assert policy < claim < artifact
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once()


def test_sql_redeployment_does_not_reinsert_or_reapply() -> None:
    connection = Mock()
    cursor = connection.cursor.return_value
    fixtures = DemoService()

    def execute(sql, params=()):
        if sql.startswith("SELECT sha256"):
            content = (ROOT / "infrastructure/sql" / params[0]).read_bytes()
            cursor.fetchall.return_value = [(hashlib.sha256(content).hexdigest(),)]
        elif sql.startswith("SELECT payload"):
            model = {**fixtures.policies, **fixtures.claims, **fixtures.artifacts}[params[0]]
            cursor.fetchall.return_value = [(model.model_dump_json(by_alias=True),)]
        else:
            cursor.fetchall.return_value = []

    cursor.execute.side_effect = execute
    result = initialize(lambda: connection, "00000000-0000-0000-0000-000000000001", fixtures)
    assert result["migrations_applied"] == 0
    assert result["records_inserted"] == 0
    connection.commit.assert_called_once()


def test_changed_applied_sql_is_not_silently_overwritten() -> None:
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = [("different-hash",)]
    with pytest.raises(ValueError, match="Applied migration changed"):
        initialize(lambda: connection, "00000000-0000-0000-0000-000000000001", DemoService())
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()


def test_policy_chunks_preserve_exact_source_text_and_bounded_citations() -> None:
    fixtures = DemoService()
    documents = policy_documents(fixtures)
    assert documents
    assert len({document["citation_id"] for document in documents}) == len(documents)
    for document in documents:
        assert document["quoted_text"] in fixtures.policy_text[document["policy_id"]]
        assert 1 <= len(document["quoted_text"]) <= 4000
        assert document["source_document"] == "data/policies/demo-auto-policy.md"
    assert (
        index_definition("synthetic-policies")["semantic"]["defaultConfiguration"]
        == "policy-semantic"
    )


def test_schema_drift_does_not_trigger_unsafe_upsert() -> None:
    client = Mock()
    client.request.return_value = {"name": "different"}
    with pytest.raises(ValueError, match="schema drift"):
        ensure_definition(
            client, "/indexes/synthetic-policies", index_definition("synthetic-policies")
        )
    assert client.request.call_count == 1


def test_knowledge_redeployment_uses_existing_identical_objects() -> None:
    fixtures = DemoService()
    documents = policy_documents(fixtures)
    definitions = {
        "/indexes/synthetic-policies": index_definition("synthetic-policies"),
        "/knowledgesources/synthetic-policy-source": source_definition("synthetic-policies"),
        "/knowledgebases/synthetic-policy-knowledge": knowledge_definition(),
        **{
            f"/indexes/synthetic-policies/docs/{document['citation_id']}": document
            for document in documents
        },
    }
    client = Mock()
    client.request.side_effect = lambda method, path: definitions[path]
    assert seed_search(client, "synthetic-policies", fixtures) == len(documents)
    assert all(call.args[0] == "GET" for call in client.request.call_args_list)


def test_partial_or_bad_knowledge_response_is_not_success() -> None:
    credential = Mock()
    credential.get_token.return_value.token = "test-token"
    client = SearchRestClient("https://demo.search.windows.net", credential)
    client.http.close()
    client.http = httpx.Client(
        base_url="https://demo.search.windows.net",
        transport=httpx.MockTransport(lambda request: httpx.Response(206, json={"references": []})),
    )
    with pytest.raises(KnowledgeError, match="Partial"):
        client.request("POST", "/knowledgebases/synthetic-policy-knowledge/retrieve", {})
    client.close()


def test_search_authorization_is_scoped_and_not_redirected() -> None:
    credential = Mock()
    credential.get_token.return_value.token = "test-token"
    client = SearchRestClient("https://demo.search.windows.net", credential)
    client.http.close()
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"value": []})

    client.http = httpx.Client(
        base_url="https://demo.search.windows.net", transport=httpx.MockTransport(handle)
    )
    assert client.request("GET", "/indexes") == {"value": []}
    assert requests[0].headers["Authorization"] == "Bearer test-token"
    assert requests[0].url.params["api-version"] == "2026-04-01"
    credential.get_token.assert_called_once_with("https://search.azure.com/.default")
    with pytest.raises(ValueError):
        client.request("GET", "https://attacker.example")
    client.close()
