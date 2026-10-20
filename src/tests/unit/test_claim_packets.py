from __future__ import annotations

from unittest.mock import Mock

import pytest
from app.search_rest import KnowledgeError
from initialize_claim_packets import (
    BASE,
    CLAIM_IDS,
    INDEX,
    SOURCE,
    definitions,
    packet_documents,
    publish,
    verify,
)


def test_packet_content_preserves_actual_outputs_and_separates_live_history() -> None:
    documents = packet_documents()
    assert [item["claim_id"] for item in documents] == list(CLAIM_IDS)
    for document in documents:
        assert document["packet_id"] == document["claim_id"]
        assert document["source_document"].endswith(".docx")
        assert len(document["snapshot_sha256"]) == 64
        assert "human_review" in document["content"]
        assert "get_claim_risk_facts" in document["content"]
        assert "not a live Foundry invocation" in document["content"]
    assert "glass wording" in documents[0]["content"]
    assert "USD 7,200" in documents[1]["content"]
    assert "No separate estimate attachment" in documents[1]["content"]
    assert "differs from policy insured" in documents[2]["content"]
    assert "No part-level damage observations" in documents[2]["content"]


def test_knowledge_base_has_only_packet_source_and_no_policy_source() -> None:
    schema = definitions()
    assert schema[f"/knowledgebases/{BASE}"]["knowledgeSources"] == [{"name": SOURCE}]
    source = schema[f"/knowledgesources/{SOURCE}"]
    assert source["searchIndexParameters"]["searchIndexName"] == INDEX
    assert source["kind"] == "searchIndex"
    assert {"name": "content"} in source["searchIndexParameters"]["sourceDataFields"]
    fields = schema[f"/indexes/{INDEX}"]["fields"]
    assert next(field for field in fields if field["name"] == "claim_id")["filterable"]


def test_existing_packet_drift_is_not_overwritten() -> None:
    client = Mock()
    client.request.return_value = {}
    with pytest.raises(ValueError, match="schema drift"):
        publish(client, packet_documents())
    assert all(call.args[0] == "GET" for call in client.request.call_args_list)


def test_verify_rejects_extra_sources_in_knowledge_base() -> None:
    client = Mock()
    schema = definitions()

    def request(method, path):
        value = schema[path]
        if path == f"/knowledgebases/{BASE}":
            return {**value, "knowledgeSources": [{"name": SOURCE}, {"name": "unrelated"}]}
        return value

    client.request.side_effect = request
    with pytest.raises(KnowledgeError, match="Definition mismatch"):
        verify(client, packet_documents())
