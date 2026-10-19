import json
import logging
from unittest.mock import patch

from app.telemetry import configure_telemetry, log_demo_content
from fastapi.testclient import TestClient


def test_local_telemetry_does_not_export_without_configuration(monkeypatch) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    with patch("app.telemetry.configure_azure_monitor") as configure:
        assert configure_telemetry() is False
    configure.assert_not_called()


def test_telemetry_uses_configured_resource_and_app_logger(monkeypatch) -> None:
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "configured-for-test")
    with (
        patch("app.telemetry.configure_azure_monitor") as configure,
        patch("app.telemetry.HTTPXClientInstrumentor") as httpx,
    ):
        assert configure_telemetry() is True
    httpx.return_value.instrument.assert_called_once()
    options = configure.call_args.kwargs
    assert options["connection_string"] == "configured-for-test"
    assert options["resource"].attributes["service.name"] == "claims-api"
    assert options["logger_name"] == "app"
    assert options["enable_live_metrics"] is False
    assert options["instrumentation_options"]["fastapi"]["enabled"] is False


def test_browser_configuration_is_public_nonsecret_and_disabled_locally(monkeypatch) -> None:
    from app import main

    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "configured-for-test")
    with TestClient(main.app) as client:
        response = client.get("/telemetry-config")
    assert response.status_code == 200
    assert response.json() == {"connectionString": ""}
    assert response.headers["cache-control"] == "no-store"


def test_demo_content_capture_requires_explicit_opt_in(monkeypatch, caplog) -> None:
    monkeypatch.delenv("CLAIMS_LOG_DEMO_CONTENT", raising=False)
    with caplog.at_level(logging.WARNING, logger="app.genai"):
        log_demo_content("agent.request", {"input": "synthetic demo"})
    assert not caplog.records


def test_demo_content_chunks_preserve_full_response_and_metadata(monkeypatch, caplog) -> None:
    monkeypatch.setenv("CLAIMS_LOG_DEMO_CONTENT", "true")
    content = {"output": [{"type": "tool_call", "result": "x" * 40000}]}
    with caplog.at_level(logging.WARNING, logger="app.genai"):
        log_demo_content("agent.response", content, response_id="resp-demo")
    assert len(caplog.records) == 11
    assert len({record.content_id for record in caplog.records}) == 1
    assert json.loads("".join(record.content_chunk for record in caplog.records)) == content
    assert all(record.response_id == "resp-demo" for record in caplog.records)
    assert all(len(record.content_chunk) <= 4000 for record in caplog.records)
    assert [record.chunk_index for record in caplog.records] == list(range(11))
