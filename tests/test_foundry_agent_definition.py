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
            "server_description": "Read-only customer and order data from Azure SQL.",
            "require_approval": "never",
            "project_connection_id": "customer-data-mcp-connection",
            "allowed_tools": ALLOWED_TOOLS,
        }
    ]


class _Item:
    def __init__(
        self,
        item_type: str,
        name: str | None = None,
        status: str | None = None,
        error: object | None = None,
        output: object | None = None,
    ):
        self.type = item_type
        self.name = name
        self.status = status
        self.error = error
        self.output = output


class _Conversations:
    def __init__(self):
        self.deleted: list[str] = []

    def create(self):
        return type("Conversation", (), {"id": "conversation-1"})()

    def delete(self, conversation_id: str) -> None:
        self.deleted.append(conversation_id)


class _Responses:
    def __init__(self, items: list[_Item], output_text: str, status: str = "completed"):
        self.items = items
        self.output_text = output_text
        self.status = status

    def create(self, **_kwargs):
        return type(
            "Response",
            (),
            {
                "id": "response-1",
                "status": self.status,
                "output": self.items,
                "output_text": self.output_text,
            },
        )()


class _OpenAI:
    def __init__(self, items: list[_Item], output_text: str, status: str = "completed"):
        self.conversations = _Conversations()
        self.responses = _Responses(items, output_text, status)


class _Project:
    def __init__(self, items: list[_Item], output_text: str, status: str = "completed"):
        self.openai = _OpenAI(items, output_text, status)

    def get_openai_client(self):
        return self.openai


def test_agent_smoke_test_requires_completed_mcp_call_and_expected_record() -> None:
    mcp_call = _Item(
        "mcp_call",
        name="get_customer",
        status="completed",
        output={"id": 1, "name": "Aarav Sharma", "country": "India", "tier": "Gold"},
    )
    project = _Project(
        [mcp_call, _Item("message")],
        "Aarav Sharma is a Gold customer in India.",
    )
    result = run_agent_smoke_test(project, "customer-data-agent")
    assert result["response_id"] == "response-1"
    assert result["response_status"] == "completed"
    assert result["mcp_call_name"] == "get_customer"
    assert result["mcp_call_status"] == "completed"
    assert project.openai.conversations.deleted == ["conversation-1"]


def test_agent_smoke_test_rejects_untraced_answer_and_cleans_conversation() -> None:
    project = _Project([_Item("message")], "Aarav Sharma is a Gold customer in India.")
    with pytest.raises(RuntimeError, match="did not record a get_customer MCP call"):
        run_agent_smoke_test(project, "customer-data-agent")
    assert project.openai.conversations.deleted == ["conversation-1"]


def test_agent_smoke_test_rejects_failed_mcp_call() -> None:
    failed_call = _Item(
        "mcp_call",
        name="get_customer",
        status="failed",
        error={"message": "connection failed"},
    )
    project = _Project([failed_call], "Aarav Sharma")
    with pytest.raises(RuntimeError, match="get_customer MCP call failed"):
        run_agent_smoke_test(project, "customer-data-agent")
