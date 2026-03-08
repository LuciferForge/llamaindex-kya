"""Card helpers — create and manage KYA identity cards for LlamaIndex agents.

Works with or without llama-index installed. When llama-index is available,
cards are stored on agent objects via a _kya_card attribute.

LlamaIndex agents expose: tools, llm, memory, chat_history.
AgentRunner wraps AgentWorker and provides the high-level interface.
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional


def _resolve_agent_fields(agent: Any) -> Dict[str, str]:
    """Extract identity-relevant fields from a LlamaIndex Agent object.

    LlamaIndex AgentRunner has: tools (via agent_worker), llm, memory,
    chat_history. We derive identity from the agent's class name and tools.
    """
    # Try to get a meaningful name
    agent_name = getattr(agent, "name", None)
    if not agent_name:
        agent_name = type(agent).__name__

    # Build a slug from the name
    slug = agent_name.lower().replace(" ", "-").replace("_", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    slug = slug.strip("-") or "agent"

    # Try to get LLM model name for context
    llm = getattr(agent, "llm", None)
    llm_model = ""
    if llm is not None:
        llm_model = getattr(llm, "model", "") or getattr(llm, "model_name", "") or type(llm).__name__

    return {
        "name": agent_name,
        "slug": slug,
        "llm_model": llm_model,
    }


def _extract_tool_capabilities(agent: Any) -> List[Dict[str, str]]:
    """Extract capabilities from a LlamaIndex agent's tools list.

    LlamaIndex tools have a .metadata attribute with .name and .description.
    """
    tools = getattr(agent, "tools", []) or []
    capabilities = []
    for tool in tools:
        # LlamaIndex FunctionTool stores info in .metadata
        metadata = getattr(tool, "metadata", None)
        if metadata:
            name = getattr(metadata, "name", None) or type(tool).__name__
            description = getattr(metadata, "description", "") or ""
        else:
            name = getattr(tool, "name", None) or type(tool).__name__
            description = getattr(tool, "description", "") or ""

        capabilities.append({
            "name": name,
            "description": description[:200],
            "risk_level": "medium",
            "scope": "as-configured",
        })
    return capabilities


def create_agent_card(
    agent: Any,
    *,
    owner_name: str = "unspecified",
    owner_contact: str = "unspecified",
    agent_id_prefix: str = "llamaindex",
    capabilities: Optional[List[Dict[str, str]]] = None,
    version: str = "0.1.0",
    risk_classification: str = "minimal",
    human_oversight: str = "human-on-the-loop",
) -> Dict[str, Any]:
    """Create a KYA identity card from a LlamaIndex Agent.

    Args:
        agent: A LlamaIndex AgentRunner/AgentWorker or any object with tools/llm.
        owner_name: Organization or person responsible for this agent.
        owner_contact: Contact email for security/compliance inquiries.
        agent_id_prefix: Prefix for the agent_id (default: "llamaindex").
        capabilities: Override auto-detected capabilities. If None, extracted from agent.tools.
        version: Semantic version for the agent.
        risk_classification: EU AI Act risk level (minimal/limited/high/unacceptable).
        human_oversight: Oversight level (none/human-on-the-loop/human-in-the-loop/human-above-the-loop).

    Returns:
        A KYA card dict conforming to the v0.1 schema.
    """
    fields = _resolve_agent_fields(agent)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if capabilities is None:
        capabilities = _extract_tool_capabilities(agent)

    # Build purpose from agent info
    purpose_parts = [f"LlamaIndex agent: {fields['name']}"]
    if fields["llm_model"]:
        purpose_parts.append(f"powered by {fields['llm_model']}")
    tool_names = [c["name"] for c in capabilities]
    if tool_names:
        purpose_parts.append(f"with tools: {', '.join(tool_names)}")

    purpose = " ".join(purpose_parts)
    # Ensure purpose meets KYA minLength of 10
    if len(purpose) < 10:
        purpose = f"LlamaIndex agent performing the role of {fields['name']}"
    # Cap at schema maxLength
    purpose = purpose[:500]

    card: Dict[str, Any] = {
        "kya_version": "0.1",
        "agent_id": f"{agent_id_prefix}/{fields['slug']}",
        "name": fields["name"],
        "version": version,
        "purpose": purpose,
        "agent_type": "autonomous",
        "owner": {
            "name": owner_name,
            "contact": owner_contact,
        },
        "capabilities": {
            "declared": capabilities,
            "denied": [],
        },
        "data_access": {
            "sources": [],
            "destinations": [],
            "pii_handling": "none",
            "retention_policy": "session-only",
        },
        "security": {
            "last_audit": None,
            "known_vulnerabilities": [],
            "injection_tested": False,
        },
        "compliance": {
            "frameworks": [],
            "risk_classification": risk_classification,
            "human_oversight": human_oversight,
        },
        "behavior": {
            "logging_enabled": False,
            "log_format": "none",
            "max_actions_per_minute": 0,
            "kill_switch": True,
            "escalation_policy": "halt-and-notify",
        },
        "metadata": {
            "created_at": now,
            "updated_at": now,
            "tags": ["llamaindex"],
        },
    }

    return card


def attach_card(agent: Any, card: Dict[str, Any]) -> None:
    """Attach a KYA identity card to a LlamaIndex Agent instance.

    Stores the card as agent._kya_card for retrieval by tools and middleware.
    """
    agent._kya_card = card


def get_card(agent: Any) -> Optional[Dict[str, Any]]:
    """Retrieve the KYA card attached to a LlamaIndex Agent, if any."""
    return getattr(agent, "_kya_card", None)
