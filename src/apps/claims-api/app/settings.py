from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
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
        )
