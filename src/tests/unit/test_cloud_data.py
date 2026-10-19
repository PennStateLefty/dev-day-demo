from __future__ import annotations

from unittest.mock import Mock, patch

import httpx
import pytest
from app.database import (
    InMemoryCommunicationStore,
    SqlClaimsStore,
    connection_string,
    connector,
    payload,
)
from app.knowledge import SearchPolicyKnowledge
from app.models import CommunicationRecord
from app.search_rest import KnowledgeError, SearchRestClient
from app.service import DemoService, ResourceNotFound
from app.settings import Settings


def test_runtime_sql_auth_is_explicit_and_encrypted() -> None:
    client_id = "00000000-0000-0000-0000-000000000001"
    value = connection_string("demo.database.windows.net", "claims", client_id=client_id)
    assert "Authentication=ActiveDirectoryMSI" in value
    assert f"UID={client_id}" in value
    assert "Encrypt=yes;TrustServerCertificate=no" in value
    assert "Connection Timeout" not in value
    assert "ActiveDirectoryDefault" in connection_string(
        "demo.database.windows.net", "claims", local_admin=True
    )
    for server, database in (
        ("attacker.example", "claims"),
        ("demo.database.windows.net;TrustServerCertificate=yes", "claims"),
        ("demo.database.windows.net", "claims;UID=another"),
    ):
        with pytest.raises(ValueError):
            connection_string(server, database, client_id=client_id)
    with pytest.raises(ValueError):
        connection_string("demo.database.windows.net", "claims")
    with pytest.raises(ValueError):
        connection_string("demo.database.windows.net", "claims", client_id="invalid")


def test_sql_login_and_query_timeouts_are_bounded() -> None:
    with patch("mssql_python.connect") as connect:
        connection = connector("validated-connection-string")()
    connect.assert_called_once_with("validated-connection-string", timeout=30)
    assert connection.timeout == 30


@pytest.mark.parametrize("content", [b"not JSON", b"\xff", b"[]"])
def test_malformed_search_responses_do_not_escape_as_success(content) -> None:
    rest = SearchRestClient("https://demo.search.windows.net", Mock())
    rest.http.close()
    rest.http = httpx.Client(
        base_url="https://demo.search.windows.net",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content)),
    )
    try:
        with pytest.raises(KnowledgeError):
            rest.request("POST", "/knowledgebases/synthetic-policy-knowledge/retrieve")
        with pytest.raises(ValueError):
            rest.request("GET", "//attacker.example")
    finally:
        rest.close()


def test_fixed_sql_queries_bind_input_and_close_connections() -> None:
    connection = Mock()
    cursor = connection.cursor.return_value
    claim = DemoService().get_claim("clm-demo-001")
    cursor.fetchall.return_value = [(payload(claim),)]
    store = SqlClaimsStore(lambda: connection)
    malicious = "'; DROP TABLE claims.Claim;--"
    assert store.find_claim(malicious) == claim
    sql, params = cursor.execute.call_args.args
    assert malicious not in sql
    assert params == (malicious,)
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_sql_review_write_is_bounded_and_committed() -> None:
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = [("note-id",)]
    store = SqlClaimsStore(lambda: connection)
    assert store.add_review_note("clm-demo-001", "Synthetic review only.") == "note-id"
    assert cursor.execute.call_args.args == (
        "EXEC claims.AddReviewNote @claim_id = ?, @note = ?",
        ("clm-demo-001", "Synthetic review only."),
    )
    connection.commit.assert_called_once()
    for note in (" ", "", "a" * 2001):
        with pytest.raises(ValueError):
            store.add_review_note("clm-demo-001", note)


def test_sql_communication_writes_use_fixed_procedures_and_commit() -> None:
    connection = Mock()
    cursor = connection.cursor.return_value
    record = CommunicationRecord(
        communication_id="com-00000000-0000-0000-0000-000000000001",
        claim_id="clm-demo-001",
        assessment_id="asm-demo-001",
        citation_ids=["cit-demo-001"],
        artifact_ids=["art-demo-photo-001"],
        body="A handler will review the information.",
        created_at="2026-10-18T15:00:00Z",
        human_review_required=True,
    )
    record_json = record.model_dump_json(by_alias=True)
    cursor.fetchall.return_value = [(record_json,)]
    store = SqlClaimsStore(lambda: connection)

    assert store.create_communication(record) == record
    assert cursor.execute.call_args.args == (
        "EXEC claims.CreateCommunication @payload = ?",
        (record_json,),
    )
    connection.commit.assert_called_once()

    connection.reset_mock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = [("updated", record_json)]
    reviewed = store.mark_communication_reviewed(record.communication_id, "Demo Handler")
    assert reviewed == record
    assert cursor.execute.call_args.args == (
        "EXEC claims.MarkCommunicationReviewed @communication_id = ?, @reviewer = ?",
        (record.communication_id, "Demo Handler"),
    )
    connection.commit.assert_called_once()

    connection.reset_mock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = [("missing", None)]
    with pytest.raises(LookupError, match="not found"):
        store.mark_communication_sent(record.communication_id)
    connection.commit.assert_not_called()


def test_local_communication_store_requires_review_before_marking_sent() -> None:
    store = InMemoryCommunicationStore()
    record = CommunicationRecord(
        communication_id="com-00000000-0000-0000-0000-000000000002",
        claim_id="clm-demo-001",
        assessment_id="asm-demo-001",
        citation_ids=[],
        artifact_ids=[],
        body="A handler will review the information.",
        created_at="2026-10-18T15:00:00Z",
        human_review_required=True,
    )
    store.create_communication(record)
    with pytest.raises(ValueError, match="reviewed"):
        store.mark_communication_sent(record.communication_id)
    reviewed = store.mark_communication_reviewed(record.communication_id, "Demo Handler")
    sent = store.mark_communication_sent(record.communication_id)
    assert reviewed.reviewed_by == "Demo Handler"
    assert sent.reviewed_at is not None and sent.sent_at is not None
    assert store.list_communications(record.claim_id) == [sent]
    with pytest.raises(ValueError, match="already been marked sent"):
        store.mark_communication_sent(record.communication_id)


def test_cloud_service_does_not_load_or_fall_back_to_fixtures() -> None:
    store = Mock()
    knowledge = Mock()
    service = DemoService(store=store, knowledge=knowledge)
    assert not hasattr(service, "claims")
    store.find_claim.return_value = None
    with pytest.raises(ResourceNotFound):
        service.get_claim("clm-demo-001")
    store.find_claim.side_effect = ConnectionError("unreachable")
    with pytest.raises(ConnectionError):
        service.get_claim("clm-demo-001")
    store.find_policy.return_value = DemoService().get_policy("pol-demo-auto")
    knowledge.lookup.side_effect = ConnectionError("unreachable")
    with pytest.raises(ConnectionError):
        service.lookup_policy("pol-demo-auto", "deer")
    with pytest.raises(ValueError):
        DemoService(store=store)


def test_cloud_assessment_uses_live_data_and_citations() -> None:
    fixtures = DemoService()
    store = Mock()
    knowledge = Mock()
    store.find_claim.return_value = fixtures.get_claim("clm-demo-002")
    store.find_policy.return_value = fixtures.get_policy("pol-demo-auto")
    store.find_artifact.side_effect = fixtures.artifacts.get
    knowledge.lookup.return_value = fixtures.lookup_policy("pol-demo-auto", "collision")
    assessment = DemoService(store=store, knowledge=knowledge).assess_claim("clm-demo-002")
    assert assessment.human_review_required
    assert assessment.policy_basis == "grounded"
    assert [call.args[0] for call in store.find_artifact.call_args_list] == [
        "art-demo-estimate-002", "art-demo-photo-002",
    ]
    knowledge.lookup.assert_called_once()


def test_search_policy_filter_is_not_caller_controlled() -> None:
    client = Mock()
    client.get_document.return_value = {
        "citation_id": "cit-demo-001",
        "policy_id": "pol-demo-auto",
        "source_document": "data/policies/demo-auto-policy.md",
        "section": "Section 1",
        "quoted_text": "Synthetic evidence.",
    }
    rest = Mock()
    rest.request.return_value = {"references": [{"type": "searchIndex", "docKey": "cit-demo-001"}]}
    knowledge = SearchPolicyKnowledge(client, rest)
    assert knowledge.lookup("pol-demo-auto", "deer")[0].policy_id == "pol-demo-auto"
    body = rest.request.call_args.args[2]
    assert body["knowledgeSourceParams"][0]["filterAddOn"] == "policy_id eq 'pol-demo-auto'"
    assert body["intents"] == [{"type": "semantic", "search": "deer"}]
    client.get_document.assert_called_once_with(key="cit-demo-001")
    for policy_id, query in (("pol-a' or true", "query"), ("pol-demo-auto", " ")):
        with pytest.raises(ValueError):
            knowledge.lookup(policy_id, query)


@pytest.mark.parametrize(
    "references",
    [None, {}, ["not-an-object"], [{"type": "blob", "docKey": "cit-demo-001"}]],
)
def test_malformed_iq_references_are_explicit_dependency_errors(references) -> None:
    client, rest = Mock(), Mock()
    rest.request.return_value = {"references": references}
    with pytest.raises(KnowledgeError):
        SearchPolicyKnowledge(client, rest).lookup("pol-demo-auto", "animal")
    client.get_document.assert_not_called()


def test_iq_no_results_is_not_fabricated_and_cross_policy_evidence_is_rejected() -> None:
    client, rest = Mock(), Mock()
    knowledge = SearchPolicyKnowledge(client, rest)
    rest.request.return_value = {"references": []}
    assert knowledge.lookup("pol-demo-auto", "unrelated") == []
    client.get_document.assert_not_called()
    rest.request.return_value = {"references": [{"type": "searchIndex", "docKey": "cit-demo-001"}]}
    for document in (
        {},
        {
            "citation_id": "cit-demo-001",
            "policy_id": "pol-unrelated",
            "source_document": "other.md",
            "section": "Section 1",
            "quoted_text": "Other policy.",
        },
        {
            "citation_id": "cit-demo-wrong",
            "policy_id": "pol-demo-auto",
            "source_document": "other.md",
            "section": "Section 1",
            "quoted_text": "Other evidence.",
        },
    ):
        client.get_document.return_value = document
        with pytest.raises(KnowledgeError):
            knowledge.lookup("pol-demo-auto", "animal")


def cloud_values() -> dict[str, str]:
    return {
        "CLAIMS_MODE": "azure",
        "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
        "CLAIMS_API_AUDIENCE": "00000000-0000-0000-0000-000000000002",
        "CLAIMS_API_CLIENT_IDS": "00000000-0000-0000-0000-000000000003",
        "AZURE_RUNTIME_CLIENT_ID": "00000000-0000-0000-0000-000000000004",
        "AZURE_SQL_SERVER": "demo.database.windows.net",
        "AZURE_SQL_DATABASE": "claims",
        "AZURE_SEARCH_ENDPOINT": "https://demo.search.windows.net",
        "AZURE_SEARCH_INDEX": "synthetic-policies",
        "CLAIMS_UI_CLIENT_ID": "00000000-0000-0000-0000-000000000003",
    }


def test_azure_mode_requires_complete_identity_and_dependency_configuration() -> None:
    values = cloud_values()
    assert Settings.from_environment(values).mode == "azure"
    for key in values:
        if key == "CLAIMS_MODE":
            continue
        with pytest.raises(ValueError):
            Settings.from_environment(
                {name: value for name, value in values.items() if name != key}
            )
    for invalid in (
        {"CLAIMS_MODE": "unexpected"},
        {"CONTAINER_APP_NAME": "deployed"},
        values | {"AZURE_SEARCH_ENDPOINT": "http://attacker.example"},
        values | {"CLAIMS_API_CLIENT_IDS": "not-a-uuid"},
        values | {"CLAIMS_UI_CLIENT_ID": "00000000-0000-0000-0000-000000000099"},
    ):
        with pytest.raises(ValueError):
            Settings.from_environment(invalid)


def test_live_vision_and_pinned_handler_configuration_cannot_be_partial_or_arbitrary() -> None:
    configured = cloud_values() | {
        "AZURE_STORAGE_ACCOUNT_NAME": "stsyntheticdemo",
        "CLAIMS_VISION_ENDPOINT": "https://demo.openai.azure.com/openai/v1",
        "CLAIMS_VISION_DEPLOYMENT": "claims-vision",
        "CLAIMS_VISION_MODEL_VERSION": "2026-09-22",
        "FOUNDRY_PROJECT_ENDPOINT": "https://demo.services.ai.azure.com/api/projects/claims",
        "CLAIM_ASSESSOR_AGENT_VERSION": "3",
    }
    assert Settings.from_environment(configured).vision_deployment == "claims-vision"
    for key in configured.keys() - cloud_values().keys():
        with pytest.raises(ValueError):
            Settings.from_environment(
                {name: value for name, value in configured.items() if name != key}
            )
    for override in (
        {"CLAIMS_VISION_ENDPOINT": "https://attacker.example/openai/v1"},
        {"CLAIMS_VISION_ENDPOINT": "https://demo.openai.azure.com/openai/v1?secret=value"},
        {"CLAIMS_VISION_MODEL_VERSION": "latest"},
        {"CLAIM_ASSESSOR_AGENT_VERSION": "latest"},
    ):
        with pytest.raises(ValueError):
            Settings.from_environment(configured | override)


def test_communication_agent_version_is_optional_but_pinned_when_configured() -> None:
    configured = cloud_values() | {
        "FOUNDRY_PROJECT_ENDPOINT": "https://demo.services.ai.azure.com/api/projects/claims",
        "CLAIM_ASSESSOR_AGENT_VERSION": "3",
        "CLAIM_COMMUNICATION_AGENT_VERSION": "1",
    }
    assert Settings.from_environment(configured).communication_version == "1"
    with pytest.raises(ValueError, match="explicit positive version"):
        Settings.from_environment(configured | {"CLAIM_COMMUNICATION_AGENT_VERSION": "latest"})
    with pytest.raises(ValueError, match="requires a Foundry endpoint"):
        Settings.from_environment({
            **cloud_values(),
            "CLAIM_COMMUNICATION_AGENT_VERSION": "1",
        })
