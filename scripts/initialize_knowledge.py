"""Initialize only the reviewed synthetic policy corpus, index and extractive IQ knowledge base."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/apps/claims-api"))

from app.search_rest import (  # noqa: E402
    KNOWLEDGE_BASE_NAME,
    SOURCE_NAME,
    KnowledgeError,
    SearchRestClient,
)
from app.service import DemoService  # noqa: E402


def index_definition(name: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,126}[a-z0-9]", name):
        raise ValueError("Invalid index name.")
    return {
        "name": name,
        "fields": [
            {
                "name": field,
                "type": "Edm.String",
                "key": field == "citation_id",
                "searchable": field in ("section", "quoted_text"),
                "filterable": field == "policy_id",
                "retrievable": True,
            }
            for field in ("citation_id", "policy_id", "source_document", "section", "quoted_text")
        ],
        "semantic": {
            "defaultConfiguration": "policy-semantic",
            "configurations": [
                {
                    "name": "policy-semantic",
                    "prioritizedFields": {
                        "titleField": {"fieldName": "section"},
                        "prioritizedContentFields": [{"fieldName": "quoted_text"}],
                    },
                }
            ],
        },
    }


def source_definition(index: str) -> dict[str, Any]:
    return {
        "name": SOURCE_NAME,
        "kind": "searchIndex",
        "description": "Synthetic training policy only; evidence for mandatory human review.",
        "searchIndexParameters": {
            "searchIndexName": index,
            "semanticConfigurationName": "policy-semantic",
            "searchFields": [{"name": "section"}, {"name": "quoted_text"}],
            "sourceDataFields": [
                {"name": name}
                for name in (
                    "citation_id",
                    "policy_id",
                    "source_document",
                    "section",
                    "quoted_text",
                )
            ],
        },
    }


def knowledge_definition() -> dict[str, Any]:
    return {
        "name": KNOWLEDGE_BASE_NAME,
        "description": "Extractive synthetic policy evidence; no autonomous coverage decisions.",
        "knowledgeSources": [{"name": SOURCE_NAME}],
    }


def matches_definition(actual: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and matches_definition(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                matches_definition(item, wanted)
                for item, wanted in zip(actual, expected, strict=True)
            )
        )
    return actual == expected


def ensure_definition(client: SearchRestClient, path: str, definition: dict[str, Any]) -> None:
    try:
        existing = client.request("GET", path)
    except httpx.HTTPStatusError as error:
        if error.response.status_code != 404:
            raise
        client.request("PUT", path, definition, create_only=True)
        return
    if not matches_definition(existing, definition):
        raise ValueError(f"Knowledge schema drift at {path}; no overwrite performed.")


def policy_documents(fixtures: DemoService) -> list[dict[str, str]]:
    documents = []
    for policy_id, text in fixtures.policy_text.items():
        sections = re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
        for index, (title, body) in enumerate(sections):
            body = body.strip()
            for chunk, offset in enumerate(range(0, len(body), 4000)):
                documents.append(
                    {
                        "citation_id": f"cit-{policy_id.removeprefix('pol-')}-{index}-{chunk}",
                        "policy_id": policy_id,
                        "source_document": fixtures.policies[policy_id].source_document_refs[0],
                        "section": title,
                        "quoted_text": body[offset : offset + 4000],
                    }
                )
    if not documents:
        raise ValueError("Synthetic policy corpus contains no sections.")
    return documents


def seed_search(client: SearchRestClient, index: str, fixtures: DemoService) -> int:
    ensure_definition(client, f"/indexes/{index}", index_definition(index))
    documents = policy_documents(fixtures)
    pending = []
    for document in documents:
        try:
            existing = client.request("GET", f"/indexes/{index}/docs/{document['citation_id']}")
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 404:
                raise
            pending.append({"@search.action": "upload", **document})
            continue
        if not matches_definition(existing, document):
            raise ValueError("Synthetic indexed policy drift; no overwrite performed.")
    if pending:
        response = client.request("POST", f"/indexes/{index}/docs/index", {"value": pending})
        outcomes = response.get("value", [])
        if len(outcomes) != len(pending) or any(
            item.get("status") is not True for item in outcomes
        ):
            raise KnowledgeError("At least one synthetic policy document failed indexing.")
    ensure_definition(client, f"/knowledgesources/{SOURCE_NAME}", source_definition(index))
    ensure_definition(client, f"/knowledgebases/{KNOWLEDGE_BASE_NAME}", knowledge_definition())
    return len(documents)


def seed_blobs(client: BlobServiceClient, fixtures: DemoService) -> None:
    for policy_id, text in fixtures.policy_text.items():
        blob = client.get_blob_client("policies", f"{policy_id}.md")
        content = text.encode("utf-8")
        try:
            existing = blob.download_blob().readall()
        except ResourceNotFoundError:
            blob.upload_blob(
                content,
                overwrite=False,
                content_settings=ContentSettings(content_type="text/markdown; charset=utf-8"),
            )
            continue
        if existing != content:
            raise ValueError("Synthetic policy Blob drift; no overwrite performed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--managed-identity", action="store_true")
    arguments = parser.parse_args()
    try:
        endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
        index = os.environ["AZURE_SEARCH_INDEX"]
        account = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
        if not re.fullmatch(r"[a-z0-9]{3,24}", account):
            raise ValueError("Invalid storage account.")
        credential = (
            ManagedIdentityCredential(client_id=os.environ["AZURE_BOOTSTRAP_CLIENT_ID"])
            if arguments.managed_identity
            else AzureCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"])
        )
        with credential:
            with BlobServiceClient(
                f"https://{account}.blob.core.windows.net",
                credential=credential,
                connection_timeout=10,
                read_timeout=30,
            ) as blobs:
                fixtures = DemoService()
                seed_blobs(blobs, fixtures)
            search = SearchRestClient(endpoint, credential)
            try:
                count = seed_search(search, index, fixtures)
            finally:
                search.close()
    except (KeyError, ValueError, OSError, AzureError, httpx.HTTPError, KnowledgeError) as error:
        logging.error(
            "Knowledge initialization failed (%s); no fixture fallback.", type(error).__name__
        )
        print(json.dumps({"passed": False, "error": type(error).__name__}))
        return 1
    print(
        json.dumps(
            {"passed": True, "indexed_sections": count, "knowledge_base": KNOWLEDGE_BASE_NAME}
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
