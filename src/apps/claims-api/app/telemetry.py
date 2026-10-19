from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import uuid4

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource


def log_demo_content(event: str, content: Any, **metadata: str) -> None:
    if os.getenv("CLAIMS_LOG_DEMO_CONTENT", "false").lower() != "true":
        return
    serialized = json.dumps(content, ensure_ascii=True)
    content_id = str(uuid4())
    # Custom-dimension values have an 8 KiB limit, smaller than trace messages.
    chunks = [serialized[index:index + 4000] for index in range(0, len(serialized), 4000)]
    for index, chunk in enumerate(chunks):
        logging.getLogger("app.genai").warning(
            "Demo AI content: %s", event,
            extra={
                "event_name": event,
                "content_id": content_id,
                "content_chunk": chunk,
                "chunk_index": index,
                "chunk_count": len(chunks),
                **metadata,
            },
        )


def configure_telemetry() -> bool:
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not connection_string:
        return False
    configure_azure_monitor(
        connection_string=connection_string,
        resource=Resource.create({"service.name": "claims-api"}),
        logger_name="app",
        enable_live_metrics=False,
        instrumentation_options={"fastapi": {"enabled": False}},
    )
    HTTPXClientInstrumentor().instrument()
    return True
