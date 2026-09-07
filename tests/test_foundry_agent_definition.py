from azure.ai.projects.models import PromptAgentDefinition
import pytest

from scripts.create_foundry_agent import ALLOWED_TOOLS, build_agent_definition, run_agent_smoke_test


def test_foundry_definition_wires_authenticated_mcp_and_allowlist() -> None:
    definition = build_agent_definition(
        model="gpt-test",
        instructions="Use tools.",
        mcp_server_url="https://example.azurewebsites.net/mcp",
        connection_name="customer-data-mcp-connection",
    )

    assert isinstance(definition, PromptAgentDefinition)
    data = definition.as_dict()
    assert data["model"] == "gpt-test"
    assert data["kind"] == "prompt"
    assert data["tools"] == [
        {
            "type": "mcp",
            "server_label": "customer_data",
            "server_url": "https://example.azurewebsites.net/mcp",
            "require_approval": "never",
            "project_connection_id": "customer-data-mcp-connection",
            "allowed_tools": ALLOWED_TOOLS,
        }
    ]


class _Item:
    def __init__(self, item_type: str):
        self.type = item_type


class _Conversations:
    def __init__(self):
        self.deleted: list[str] = []

    def create(self):
        return type("Conversation", (), {"id": "conversation-1"})()

    def delete(self, conversation_id: str) -> None:
        self.deleted.append(conversation_id)


class _Responses:
    def __init__(self, output_types: list[str], output_text: str):
        self.output_types = output_types
        self.output_text = output_text

    def create(self, **_kwargs):
        return type(
            "Response",
            (),
            {
                "id": "response-1",
                "output": [_Item(item_type) for item_type in self.output_types],
                "output_text": self.output_text,
            },
        )()


class _OpenAI:
    def __init__(self, output_types: list[str], output_text: str):
        self.conversations = _Conversations()
        self.responses = _Responses(output_types, output_text)


class _Project:
    def __init__(self, output_types: list[str], output_text: str):
        self.openai = _OpenAI(output_types, output_text)

    def get_openai_client(self):
        return self.openai


def test_agent_smoke_test_requires_tool_trace_and_expected_record() -> None:
    project = _Project(["mcp_call", "message"], "Aarav Sharma is a Gold customer in India.")
    result = run_agent_smoke_test(project, "customer-data-agent")
    assert result["response_id"] == "response-1"
    assert "mcp_call" in result["output_types"]
    assert project.openai.conversations.deleted == ["conversation-1"]


def test_agent_smoke_test_rejects_untraced_answer_and_cleans_conversation() -> None:
    project = _Project(["message"], "Aarav Sharma is a Gold customer in India.")
    with pytest.raises(RuntimeError, match="without a recorded MCP call"):
        run_agent_smoke_test(project, "customer-data-agent")
    assert project.openai.conversations.deleted == ["conversation-1"]
