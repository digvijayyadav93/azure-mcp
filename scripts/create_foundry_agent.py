"""Create and verify a Microsoft Foundry prompt agent backed by this MCP server.

Authentication comes from DefaultAzureCredential. Run az login before this
script. The MCP API key is stored in the Foundry project connection created by
configure_foundry.ps1 and is never written to this script or its output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential


ALLOWED_TOOLS = [
    "get_customer",
    "search_customers",
    "list_orders",
    "get_sales_summary",
]


def build_agent_definition(
    model: str,
    instructions: str,
    mcp_server_url: str,
    connection_name: str,
) -> PromptAgentDefinition:
    tool = MCPTool(
        server_label="customer_data",
        server_url=mcp_server_url,
        server_description="Read-only customer and order data from Azure SQL.",
        require_approval="never",
        project_connection_id=connection_name,
        allowed_tools=ALLOWED_TOOLS,
    )
    return PromptAgentDefinition(
        model=model,
        instructions=instructions,
        tools=[tool],
    )


def run_agent_smoke_test(project: AIProjectClient, agent_name: str) -> dict[str, Any]:
    """Require a completed MCP call and a result grounded in customer 1."""

    openai = project.get_openai_client()
    conversation = openai.conversations.create()
    try:
        response = openai.responses.create(
            conversation=conversation.id,
            input=(
                "Use the get_customer MCP tool with customer_id 1. "
                "Return the customer's name, country, and tier."
            ),
            extra_body={
                "agent_reference": {
                    "name": agent_name,
                    "type": "agent_reference",
                }
            },
        )

        response_status = getattr(response, "status", None)
        if response_status != "completed":
            raise RuntimeError(f"Agent response did not complete: {response_status!r}")

        mcp_calls = [
            item for item in response.output
            if getattr(item, "type", "") == "mcp_call"
            and getattr(item, "name", "") == "get_customer"
        ]
        if not mcp_calls:
            observed = [
                {
                    "type": getattr(item, "type", "unknown"),
                    "name": getattr(item, "name", None),
                    "status": getattr(item, "status", None),
                }
                for item in response.output
            ]
            raise RuntimeError(
                "Agent did not record a get_customer MCP call. "
                f"Observed output: {observed}"
            )

        mcp_call = mcp_calls[-1]
        call_status = getattr(mcp_call, "status", None)
        call_error = getattr(mcp_call, "error", None)
        if call_status != "completed" or call_error is not None:
            raise RuntimeError(
                "get_customer MCP call failed. "
                f"status={call_status!r}, error={call_error!r}"
            )

        call_output = getattr(mcp_call, "output", None)
        serialized_output = json.dumps(call_output, default=str)
        if "Aarav Sharma" not in serialized_output:
            raise RuntimeError(
                "Completed MCP call did not return the expected Azure SQL record. "
                f"Output: {serialized_output}"
            )

        output_text = response.output_text or ""
        if "Aarav Sharma" not in output_text:
            raise RuntimeError(
                "Agent final response omitted the customer returned by MCP. "
                f"Response: {output_text!r}"
            )

        return {
            "response_id": response.id,
            "response_status": response_status,
            "mcp_call_name": getattr(mcp_call, "name", None),
            "mcp_call_status": call_status,
            "mcp_call_output": call_output,
            "output_text": output_text,
        }
    finally:
        openai.conversations.delete(conversation.id)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Create and verify the Foundry MCP agent")
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--model", required=True, help="Foundry model deployment name")
    parser.add_argument("--mcp-server-url", required=True)
    parser.add_argument("--connection-name", required=True)
    parser.add_argument("--agent-name", default="customer-data-agent")
    parser.add_argument(
        "--instructions-file",
        type=Path,
        default=repo_root / "agent" / "instructions.md",
    )
    parser.add_argument("--skip-smoke-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    instructions = args.instructions_file.read_text(encoding="utf-8")
    definition = build_agent_definition(
        model=args.model,
        instructions=instructions,
        mcp_server_url=args.mcp_server_url,
        connection_name=args.connection_name,
    )

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=args.project_endpoint.rstrip("/"), credential=credential) as project,
    ):
        agent = project.agents.create_version(
            agent_name=args.agent_name,
            description="Read-only customer-data agent using an authenticated MCP server.",
            definition=definition,
        )
        result: dict[str, Any] = {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "agent_version": agent.version,
            "project_endpoint": args.project_endpoint.rstrip("/"),
            "mcp_server_url": args.mcp_server_url,
            "allowed_tools": ALLOWED_TOOLS,
        }
        if not args.skip_smoke_test:
            result["smoke_test"] = run_agent_smoke_test(project, agent.name)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
