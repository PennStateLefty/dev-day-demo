from __future__ import annotations

import json
import re
from typing import Any

import httpx
from azure.core.credentials import TokenCredential

API_VERSION = "2026-04-01"
SOURCE_NAME = "synthetic-policy-source"
KNOWLEDGE_BASE_NAME = "synthetic-policy-knowledge"


class KnowledgeError(Exception):
    """Knowledge dependency returned an incomplete or invalid response."""


class SearchRestClient:
    def __init__(self, endpoint: str, credential: TokenCredential) -> None:
        if not re.fullmatch(r"https://[a-z0-9-]+\.search\.windows\.net", endpoint):
            raise ValueError("Invalid Azure AI Search endpoint.")
        self.credential = credential
        self.http = httpx.Client(base_url=endpoint, timeout=60, follow_redirects=False)

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        create_only: bool = False,
    ) -> dict[str, Any]:
        if path.startswith("//") or not re.fullmatch(r"/[a-zA-Z0-9/_-]+", path):
            raise ValueError("Search path must be an internal resource path.")
        token = self.credential.get_token("https://search.azure.com/.default")
        headers = {"Authorization": f"Bearer {token.token}"}
        if create_only:
            headers["If-None-Match"] = "*"
        response = self.http.request(
            method, path, params={"api-version": API_VERSION}, json=body, headers=headers
        )
        response.raise_for_status()
        if response.status_code == 206:
            raise KnowledgeError("Partial knowledge results must not be used as complete evidence.")
        try:
            result = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise KnowledgeError("Knowledge service returned invalid JSON.") from error
        if not isinstance(result, dict):
            raise KnowledgeError("Knowledge service returned an invalid object.")
        return result

    def close(self) -> None:
        self.http.close()
