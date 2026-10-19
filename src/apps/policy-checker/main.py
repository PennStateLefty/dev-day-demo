from __future__ import annotations

import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.sdk.resources import Resource
from policy_checker import (
    TOOLBOX_NAME,
    load_instructions,
    validate_versioned_toolbox_endpoint,
)

credential = DefaultAzureCredential()


def create_agent() -> Agent:
    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    toolbox_version = os.environ["POLICY_CHECKER_TOOLBOX_VERSION"]
    toolbox_endpoint = validate_versioned_toolbox_endpoint(
        os.environ["POLICY_CHECKER_TOOLBOX_ENDPOINT"],
        project_endpoint,
        toolbox_version,
    )
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )
    toolbox = FoundryToolbox(
        credential,
        url=toolbox_endpoint,
        name=TOOLBOX_NAME,
    )
    return Agent(
        client=client,
        name="policy-checker",
        instructions=load_instructions(),
        tools=toolbox,
        default_options={"store": False},
    )


async def main() -> None:
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if connection_string:
        configure_azure_monitor(
            connection_string=connection_string,
            resource=Resource.create({"service.name": "policy-checker"}),
            logger_name="policy_checker",
            enable_live_metrics=False,
        )
    server = ResponsesHostServer(agent=create_agent, history_source="agent_server")
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
