from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from .models import Citation
from .search_rest import KNOWLEDGE_BASE_NAME, SOURCE_NAME, KnowledgeError, SearchRestClient

if TYPE_CHECKING:
    from azure.search.documents import SearchClient


class SearchPolicyKnowledge:
    def __init__(self, client: SearchClient, rest: SearchRestClient) -> None:
        self.client = client
        self.rest = rest

    def lookup(self, policy_id: str, query: str) -> list[Citation]:
        if not re.fullmatch(r"pol-[a-z0-9-]+", policy_id):
            raise ValueError("Invalid policy ID.")
        if not 1 <= len(query.strip()) <= 10000:
            raise ValueError("Policy lookup requires 1-10000 non-whitespace characters.")
        result = self.rest.request(
            "POST",
            f"/knowledgebases/{KNOWLEDGE_BASE_NAME}/retrieve",
            {
                "intents": [{"type": "semantic", "search": query}],
                "knowledgeSourceParams": [
                    {
                        "knowledgeSourceName": SOURCE_NAME,
                        "kind": "searchIndex",
                        "filterAddOn": f"policy_id eq '{policy_id}'",
                        "includeReferences": True,
                    }
                ],
            },
        )
        references = result.get("references")
        if not isinstance(references, list):
            raise KnowledgeError("Knowledge retrieval omitted its reference array.")
        citations = []
        seen = set()
        for reference in references[:3]:
            if (
                not isinstance(reference, dict)
                or reference.get("type") != "searchIndex"
                or not re.fullmatch(r"cit-[a-z0-9-]+", str(reference.get("docKey", "")))
            ):
                raise KnowledgeError("Knowledge retrieval returned an invalid citation reference.")
            key = reference["docKey"]
            if key in seen:
                continue
            seen.add(key)
            document = self.client.get_document(key=key)
            fields = ("citation_id", "policy_id", "source_document", "section", "quoted_text")
            if not isinstance(document, dict) or not all(name in document for name in fields):
                raise KnowledgeError("Knowledge citation document omitted required evidence.")
            try:
                citation = Citation.model_validate({name: document[name] for name in fields})
            except ValidationError as error:
                raise KnowledgeError("Knowledge citation document failed validation.") from error
            if citation.policy_id != policy_id or citation.citation_id != key:
                raise KnowledgeError("Knowledge citation does not match the requested policy/key.")
            citations.append(citation)
        return citations
