from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID


@dataclass(frozen=True)
class Settings:
    mode: str = "local"
    tenant_id: str = ""
    audience: str = ""
    client_ids: tuple[str, ...] = ()
    runtime_client_id: str = ""
    sql_server: str = ""
    sql_database: str = ""
    search_endpoint: str = ""
    search_index: str = ""
    ui_client_id: str = ""
    storage_account: str = ""
    vision_endpoint: str = ""
    vision_deployment: str = ""
    vision_model_version: str = ""
    foundry_endpoint: str = ""
    assessor_version: str = ""
    communication_version: str = ""

    @classmethod
    def from_environment(cls, values: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if values is None else values
        mode = values.get("CLAIMS_MODE", "local")
        if mode not in ("local", "azure"):
            raise ValueError("CLAIMS_MODE must be local or azure.")
        if mode == "local":
            if values.get("CONTAINER_APP_NAME"):
                raise ValueError("Azure Container Apps must explicitly use CLAIMS_MODE=azure.")
            return cls()
        required = (
            "AZURE_TENANT_ID",
            "CLAIMS_API_AUDIENCE",
            "CLAIMS_API_CLIENT_IDS",
            "AZURE_RUNTIME_CLIENT_ID",
            "AZURE_SQL_SERVER",
            "AZURE_SQL_DATABASE",
            "AZURE_SEARCH_ENDPOINT",
            "AZURE_SEARCH_INDEX",
            "CLAIMS_UI_CLIENT_ID",
        )
        missing = [key for key in required if not values.get(key, "").strip()]
        if missing:
            raise ValueError(f"Azure mode requires explicit configuration: {', '.join(missing)}.")
        clients = tuple(
            str(UUID(item.strip())) for item in values["CLAIMS_API_CLIENT_IDS"].split(",")
        )
        tenant = str(UUID(values["AZURE_TENANT_ID"]))
        runtime = str(UUID(values["AZURE_RUNTIME_CLIENT_ID"]))
        audience = str(UUID(values["CLAIMS_API_AUDIENCE"]))
        ui_client = str(UUID(values["CLAIMS_UI_CLIENT_ID"]))
        if ui_client not in clients:
            raise ValueError("The UI client must be explicitly allowed in CLAIMS_API_CLIENT_IDS.")
        endpoint = values["AZURE_SEARCH_ENDPOINT"].rstrip("/")
        if not re.fullmatch(r"https://[a-z0-9-]+\.search\.windows\.net", endpoint):
            raise ValueError("Search endpoint must be an Azure AI Search HTTPS endpoint.")
        index = values["AZURE_SEARCH_INDEX"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,126}[a-z0-9]", index):
            raise ValueError("Invalid Azure AI Search index name.")
        storage = values.get("AZURE_STORAGE_ACCOUNT_NAME", "")
        if storage and not re.fullmatch(r"[a-z0-9]{3,24}", storage):
            raise ValueError("Invalid evidence storage account name.")
        vision = tuple(values.get(key, "") for key in (
            "CLAIMS_VISION_ENDPOINT", "CLAIMS_VISION_DEPLOYMENT", "CLAIMS_VISION_MODEL_VERSION",
        ))
        if any(vision) and not all(vision):
            raise ValueError("Vision endpoint, deployment and model version must be set together.")
        if any(vision) and not storage:
            raise ValueError("Live vision requires the private evidence storage account.")
        if vision[1] and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", vision[1]):
            raise ValueError("Invalid vision deployment identifier.")
        if vision[2] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", vision[2]):
            raise ValueError("Vision requires an explicit dated model version.")
        if vision[0]:
            parsed = urlparse(vision[0])
            if (
                parsed.scheme != "https" or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.port
                or not (parsed.hostname or "").endswith((
                    ".openai.azure.com", ".services.ai.azure.com", ".azure-api.net",
                ))
                or not parsed.path.rstrip("/").endswith("/openai/v1")
            ):
                raise ValueError("Vision requires an approved Azure HTTPS /openai/v1 endpoint.")
        foundry = values.get("FOUNDRY_PROJECT_ENDPOINT", "")
        version = values.get("CLAIM_ASSESSOR_AGENT_VERSION", "")
        communication_version = values.get("CLAIM_COMMUNICATION_AGENT_VERSION", "")
        if bool(foundry) != bool(version):
            raise ValueError("Foundry project endpoint and explicit agent version are required.")
        if foundry and not re.fullmatch(
            r"https://[a-z0-9-]+\.services\.ai\.azure\.com/api/projects/[a-z0-9-]+", foundry,
        ):
            raise ValueError("Invalid Foundry project endpoint.")
        if version and not re.fullmatch(r"[1-9][0-9]*", version):
            raise ValueError("The Claim Assessor version must be an explicit positive integer.")
        if communication_version and (
            not foundry or not re.fullmatch(r"[1-9][0-9]*", communication_version)
        ):
            raise ValueError(
                "The Communication Agent requires a Foundry endpoint and explicit positive version."
            )
        return cls(
            mode=mode,
            tenant_id=tenant,
            audience=audience,
            client_ids=clients,
            runtime_client_id=runtime,
            sql_server=values["AZURE_SQL_SERVER"],
            sql_database=values["AZURE_SQL_DATABASE"],
            search_endpoint=endpoint,
            search_index=index,
            ui_client_id=ui_client,
            storage_account=storage,
            vision_endpoint=vision[0],
            vision_deployment=vision[1],
            vision_model_version=vision[2],
            foundry_endpoint=foundry,
            assessor_version=version,
            communication_version=communication_version,
        )
