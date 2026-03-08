"""Tests for llamaindex-kya integration.

Tests work without llama-index installed by using mock Agent/Tool classes.
"""

import json
import pytest
from typing import Any

from llamaindex_kya.card import create_agent_card, attach_card, get_card
from llamaindex_kya.identity import verify_identity, _verify_card_data
from llamaindex_kya.trust_gate import evaluate_trust
from llamaindex_kya.middleware import kya_verified, KYAVerificationError


# ── Mock LlamaIndex classes ──


class FunctionTool:
    """Mimics llama_index.core.tools.FunctionTool."""

    def __init__(self, fn=None, name="", description=""):
        self.metadata = type("M", (), {"name": name, "description": description})()


class AgentRunner:
    """Mimics llama_index.core.agent.AgentRunner."""

    def __init__(self, tools=None, llm=None, name=None):
        self.tools = tools or []
        self.llm = llm
        self.name = name


class MockLLM:
    """Mimics a LlamaIndex LLM object."""

    def __init__(self, model="gpt-4"):
        self.model = model


# ── Card creation ──


class TestCreateAgentCard:
    def test_basic_card(self):
        agent = AgentRunner(name="ResearchAgent")
        card = create_agent_card(agent, owner_name="TestOrg", owner_contact="test@test.com")

        assert card["kya_version"] == "0.1"
        assert card["agent_id"] == "llamaindex/researchagent"
        assert card["name"] == "ResearchAgent"
        assert "ResearchAgent" in card["purpose"]
        assert card["owner"]["name"] == "TestOrg"
        assert card["owner"]["contact"] == "test@test.com"

    def test_card_with_tools(self):
        tools = [
            FunctionTool(name="web_search", description="Search the web"),
            FunctionTool(name="file_read", description="Read files"),
        ]
        agent = AgentRunner(tools=tools, name="Analyst")
        card = create_agent_card(agent, owner_name="Org")

        declared = card["capabilities"]["declared"]
        assert len(declared) == 2
        assert declared[0]["name"] == "web_search"
        assert declared[1]["name"] == "file_read"

    def test_card_with_llm(self):
        llm = MockLLM(model="gpt-4-turbo")
        agent = AgentRunner(llm=llm, name="SmartAgent")
        card = create_agent_card(agent)

        assert "gpt-4-turbo" in card["purpose"]

    def test_card_custom_prefix(self):
        agent = AgentRunner(name="Writer")
        card = create_agent_card(agent, agent_id_prefix="myorg")
        assert card["agent_id"] == "myorg/writer"

    def test_card_slug_from_class_name(self):
        """When no name is set, falls back to class name."""
        agent = AgentRunner()
        card = create_agent_card(agent)
        assert card["agent_id"] == "llamaindex/agentrunner"

    def test_purpose_minimum_length(self):
        agent = AgentRunner(name="X")
        card = create_agent_card(agent)
        assert len(card["purpose"]) >= 10

    def test_card_has_metadata_timestamps(self):
        agent = AgentRunner(name="Bot")
        card = create_agent_card(agent)
        assert card["metadata"]["created_at"] != ""
        assert card["metadata"]["updated_at"] != ""

    def test_card_tags_include_llamaindex(self):
        agent = AgentRunner(name="Tagged")
        card = create_agent_card(agent)
        assert "llamaindex" in card["metadata"]["tags"]


# ── Card attachment ──


class TestAttachCard:
    def test_attach_and_get(self):
        agent = AgentRunner(name="Test")
        card = {"kya_version": "0.1", "agent_id": "test/test"}
        attach_card(agent, card)
        assert get_card(agent) == card

    def test_get_card_none_when_not_attached(self):
        agent = AgentRunner(name="Test")
        assert get_card(agent) is None


# ── Identity verification ──


VALID_CARD = {
    "kya_version": "0.1",
    "agent_id": "llamaindex/researcher",
    "name": "Researcher",
    "version": "0.1.0",
    "purpose": "A LlamaIndex agent that researches topics and summarizes findings.",
    "agent_type": "autonomous",
    "owner": {"name": "TestOrg", "contact": "test@test.com"},
    "capabilities": {
        "declared": [
            {"name": "web_search", "risk_level": "medium"},
            {"name": "summarize", "risk_level": "low"},
        ],
        "denied": [],
    },
}

MINIMAL_CARD = {
    "kya_version": "0.1",
    "agent_id": "llamaindex/minimal",
    "name": "Minimal",
    "version": "0.1.0",
    "purpose": "A minimal test agent for validation.",
    "owner": {"name": "Test", "contact": "test@test.com"},
    "capabilities": {"declared": [{"name": "test", "risk_level": "low"}]},
}

INVALID_CARD = {
    "kya_version": "0.1",
    "name": "Broken",
    # Missing agent_id, purpose, capabilities, owner
}


class TestIdentityVerification:
    def test_valid_card(self):
        result = verify_identity(json.dumps(VALID_CARD))
        assert "VERIFIED" in result
        assert "Researcher" in result

    def test_invalid_card(self):
        result = verify_identity(json.dumps(INVALID_CARD))
        assert "FAILED" in result

    def test_invalid_json(self):
        result = verify_identity("not json")
        assert "FAILED" in result
        assert "Invalid JSON" in result

    def test_verify_data_returns_capabilities(self):
        result = _verify_card_data(VALID_CARD)
        assert "web_search" in result["capabilities"]
        assert "summarize" in result["capabilities"]

    def test_verify_data_score(self):
        result = _verify_card_data(VALID_CARD)
        assert result["completeness_score"] > 0


# ── Trust gate ──


class TestTrustGate:
    def test_passes_valid_card(self):
        result = evaluate_trust(json.dumps(VALID_CARD), min_score=0)
        assert "PASSED" in result

    def test_blocks_low_score(self):
        result = evaluate_trust(json.dumps(MINIMAL_CARD), min_score=100)
        assert "BLOCKED" in result
        assert "below threshold" in result

    def test_blocks_missing_capabilities(self):
        result = evaluate_trust(
            json.dumps(VALID_CARD),
            min_score=0,
            required_capabilities="web_search,secret_power",
        )
        assert "BLOCKED" in result
        assert "secret_power" in result

    def test_blocks_unsigned_when_signature_required(self):
        result = evaluate_trust(
            json.dumps(VALID_CARD),
            min_score=0,
            require_signature=True,
        )
        assert "BLOCKED" in result
        assert "unsigned" in result.lower()

    def test_invalid_json(self):
        result = evaluate_trust("bad json")
        assert "BLOCKED" in result


# ── Middleware decorator ──


class TestKYAVerified:
    def test_passes_with_valid_card(self):
        agent = AgentRunner(name="GoodAgent")
        card = create_agent_card(agent, owner_name="Test", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=0)
        def task(agent):
            return "executed"

        assert task(agent) == "executed"

    def test_raises_without_card(self):
        agent = AgentRunner(name="NakedAgent")

        @kya_verified()
        def task(agent):
            return "executed"

        with pytest.raises(KYAVerificationError, match="No KYA card"):
            task(agent)

    def test_raises_on_low_score(self):
        agent = AgentRunner(name="WeakAgent")
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=100)
        def task(agent):
            return "executed"

        with pytest.raises(KYAVerificationError, match="below required"):
            task(agent)

    def test_skip_on_fail(self):
        agent = AgentRunner(name="Skippable")

        @kya_verified(on_fail="skip")
        def task(agent):
            return "executed"

        assert task(agent) is None

    def test_log_on_fail(self, capsys):
        agent = AgentRunner(name="LoggedAgent")

        @kya_verified(on_fail="log")
        def task(agent):
            return "executed"

        result = task(agent)
        assert result == "executed"
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_agent_as_kwarg(self):
        agent = AgentRunner(name="KwargAgent")
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=0)
        def task(data, agent=None):
            return f"processed {data}"

        assert task("stuff", agent=agent) == "processed stuff"

    def test_required_capabilities(self):
        tools = [FunctionTool(name="reading", description="Read data")]
        agent = AgentRunner(tools=tools, name="LimitedAgent")
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(required_capabilities=["reading"])
        def task(agent):
            return "executed"

        assert task(agent) == "executed"

    def test_missing_required_capabilities(self):
        agent = AgentRunner(name="NoToolsAgent")
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(required_capabilities=["admin_access"])
        def task(agent):
            return "executed"

        with pytest.raises(KYAVerificationError, match="Missing capabilities"):
            task(agent)

    def test_no_agent_found(self):
        """When no agent-like object is passed, should fail."""

        @kya_verified()
        def task(data):
            return "executed"

        with pytest.raises(KYAVerificationError, match="No agent found"):
            task("just a string")


# ── Tool classes ──


class TestToolClasses:
    def test_identity_tool_run(self):
        from llamaindex_kya.identity import KYAIdentityTool

        tool = KYAIdentityTool()
        result = tool.run(json.dumps(VALID_CARD))
        assert "VERIFIED" in result

    def test_trust_gate_tool_run(self):
        from llamaindex_kya.trust_gate import TrustGateTool

        tool = TrustGateTool()
        result = tool.run(json.dumps(VALID_CARD), min_score=0)
        assert "PASSED" in result

    def test_identity_tool_as_tool_without_llamaindex(self):
        from llamaindex_kya.identity import KYAIdentityTool

        # Without llama-index installed, as_tool() returns None
        result = KYAIdentityTool.as_tool()
        assert result is None

    def test_trust_gate_as_tool_without_llamaindex(self):
        from llamaindex_kya.trust_gate import TrustGateTool

        result = TrustGateTool.as_tool()
        assert result is None
