"""Publish frozen synthetic escalation packets to an isolated Foundry IQ knowledge base."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import httpx
from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential
from initialize_knowledge import ensure_definition, matches_definition

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/apps/claims-api"))

from app.models import HandlerResult  # noqa: E402
from app.search_rest import KnowledgeError, SearchRestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PACKETS = ROOT / "data/claim-packets"
CLAIM_IDS = ("clm-demo-001", "clm-demo-002", "clm-demo-004")
INDEX = "claim-escalation-packets"
SOURCE = "claim-escalation-packets-source"
BASE = "supervisor-claim-packets"


def definitions() -> dict[str, dict]:
    return {
        f"/indexes/{INDEX}": json.loads((PACKETS / "iq/index.json").read_text()),
        f"/knowledgesources/{SOURCE}": json.loads(
            (PACKETS / "iq/knowledge-source.json").read_text()
        ),
        f"/knowledgebases/{BASE}": json.loads((PACKETS / "iq/knowledge-base.json").read_text()),
    }


def packet_documents() -> list[dict[str, str]]:
    documents = []
    for claim_id in CLAIM_IDS:
        source = PACKETS / "source" / f"{claim_id}.json"
        snapshot = json.loads(source.read_text())
        workflow = HandlerResult.model_validate(snapshot["workflow"])
        if (
            snapshot["synthetic"] is not True
            or snapshot["humanReviewRequired"] is not True
            or snapshot["claim"]["claimId"] != claim_id
            or workflow.assessment.claim_id != claim_id
            or workflow.recommendation.claim_id != claim_id
        ):
            raise ValueError(f"Snapshot identity or safety mismatch: {claim_id}")
        packet = PACKETS / "upload" / f"{claim_id}-escalation-packet.docx"
        with ZipFile(packet) as document:
            xml = ET.fromstring(document.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            content = "\n".join(
                "".join(node.text or "" for node in paragraph.findall(".//w:t", ns))
                for paragraph in xml.findall(".//w:p", ns)
            )
        required = [
            claim_id,
            snapshot["claim"]["claimantStatement"],
            workflow.recommendation.summary,
            workflow.response_id,
            "human_review",
            "get_claim_risk_facts",
        ]
        required.extend(workflow.recommendation.recommended_actions)
        for photo in snapshot["photos"]:
            photo_bytes = (ROOT / photo["path"]).read_bytes()
            digest = hashlib.sha256(photo_bytes).hexdigest()
            if (
                digest != photo["sha256"]
                or digest != workflow.assessment.image_analysis.input_sha256
            ):
                raise ValueError(f"Evidence hash mismatch: {claim_id}")
            with ZipFile(packet) as archive:
                embedded = [
                    hashlib.sha256(archive.read(name)).hexdigest()
                    for name in archive.namelist()
                    if name.startswith("word/media/")
                ]
            if digest not in embedded:
                raise ValueError(f"Original photo missing from packet: {claim_id}")
            required.append(digest)
        if not all(item in content for item in required):
            raise ValueError(f"Packet omitted captured evidence: {claim_id}")
        documents.append(
            {
                "packet_id": claim_id,
                "claim_id": claim_id,
                "title": f"{claim_id} synthetic supervisor escalation packet",
                "content": content,
                "source_document": str(packet.relative_to(ROOT)),
                "captured_at_utc": snapshot["capturedAtUtc"],
                "snapshot_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "packet_sha256": hashlib.sha256(packet.read_bytes()).hexdigest(),
            }
        )
    return documents


def publish(client: SearchRestClient, documents: list[dict[str, str]]) -> None:
    for path, definition in definitions().items():
        if path.startswith("/indexes/"):
            ensure_definition(client, path, definition)
    pending = []
    for document in documents:
        try:
            existing = client.request("GET", f"/indexes/{INDEX}/docs/{document['packet_id']}")
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 404:
                raise
            pending.append({"@search.action": "upload", **document})
        else:
            if not matches_definition(existing, document):
                raise ValueError(f"Packet drift; no overwrite performed: {document['packet_id']}")
    if pending:
        outcomes = client.request("POST", f"/indexes/{INDEX}/docs/index", {"value": pending})
        results = outcomes.get("value", [])
        if len(results) != len(pending) or any(item.get("status") is not True for item in results):
            raise KnowledgeError("At least one packet failed indexing.")
    for path, definition in definitions().items():
        if not path.startswith("/indexes/"):
            ensure_definition(client, path, definition)


def verify(client: SearchRestClient, documents: list[dict[str, str]]) -> dict:
    for path, definition in definitions().items():
        if not matches_definition(client.request("GET", path), definition):
            raise KnowledgeError(f"Definition mismatch: {path}")
    indexed = client.request(
        "POST",
        f"/indexes/{INDEX}/docs/search",
        {"search": "*", "select": "packet_id", "count": True, "top": 100},
    )
    if indexed.get("@odata.count") != 3 or {
        item["packet_id"] for item in indexed.get("value", [])
    } != set(CLAIM_IDS):
        raise KnowledgeError("Packet index must contain exactly the three approved claims.")
    for document in documents:
        existing = client.request("GET", f"/indexes/{INDEX}/docs/{document['packet_id']}")
        if not matches_definition(existing, document):
            raise KnowledgeError(f"Indexed content mismatch: {document['packet_id']}")
    return {
        "passed": True,
        "index": INDEX,
        "knowledge_source": SOURCE,
        "knowledge_base": BASE,
        "packet_count": len(documents),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument(
        "--apply", action="store_true", help="Create missing objects; never overwrite."
    )
    parser.add_argument("--verify", action="store_true", help="Verify deployed objects, read-only.")
    args = parser.parse_args()
    try:
        documents = packet_documents()
        if not args.apply and not args.verify:
            print(json.dumps({"planned": list(definitions()), "packet_count": len(documents)}))
            return 0
        with AzureCliCredential() as credential:
            client = SearchRestClient(args.endpoint, credential)
            try:
                policy_before = {
                    path: client.request("GET", path)
                    for path in (
                        "/indexes/synthetic-policies",
                        "/knowledgesources/synthetic-policy-source",
                        "/knowledgebases/synthetic-policy-knowledge",
                    )
                }
                if args.apply:
                    publish(client, documents)
                result = verify(client, documents)
                for path, before in policy_before.items():
                    if client.request("GET", path) != before:
                        raise KnowledgeError(f"Existing policy definition changed: {path}")
                result["existing_policy_definitions_unchanged"] = True
                print(json.dumps(result))
            finally:
                client.close()
    except (ValueError, KeyError, OSError, AzureError, httpx.HTTPError, KnowledgeError) as error:
        logging.exception("Claim packet initialization failed; no substitute data was used.")
        print(json.dumps({"passed": False, "error": type(error).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
