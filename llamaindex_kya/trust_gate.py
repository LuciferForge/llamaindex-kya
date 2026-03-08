"""TrustGateTool — Gate agent actions on trust score thresholds.

A LlamaIndex tool that checks whether an agent's KYA identity card meets
a minimum completeness/trust score before allowing an action to proceed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

try:
    from llama_index.core.tools import FunctionTool as _LlamaIndexFunctionTool

    _HAS_LLAMAINDEX = True
except ImportError:
    _HAS_LLAMAINDEX = False


def evaluate_trust(
    card_json: str,
    min_score: int = 50,
    require_signature: bool = False,
    required_capabilities: Optional[str] = None,
) -> str:
    """Evaluate whether a KYA card meets trust requirements.

    Returns a human-readable PASS/FAIL result with reasons.
    """
    try:
        card = json.loads(card_json)
    except json.JSONDecodeError as e:
        return f"BLOCKED: Invalid JSON — {e}"

    from kya.validator import compute_completeness_score

    score = compute_completeness_score(card)
    reasons: list[str] = []
    passed = True

    # Score check
    if score < min_score:
        passed = False
        reasons.append(f"Score {score}/100 below threshold {min_score}")

    # Signature check
    if require_signature:
        sig = card.get("_signature")
        if not sig:
            passed = False
            reasons.append("No signature — card is unsigned")
        else:
            try:
                from kya.signer import verify_card

                result = verify_card(card)
                if not result.get("valid"):
                    passed = False
                    reasons.append(f"Invalid signature: {result.get('error', 'unknown')}")
            except ImportError:
                passed = False
                reasons.append("Cannot verify signature — install kya-agent[signing]")

    # Capabilities check
    if required_capabilities:
        required = {c.strip().lower() for c in required_capabilities.split(",")}
        declared = {
            c.get("name", "").lower()
            for c in card.get("capabilities", {}).get("declared", [])
        }
        missing = required - declared
        if missing:
            passed = False
            reasons.append(f"Missing capabilities: {', '.join(sorted(missing))}")

    # Build result
    agent_name = card.get("name", "unknown")
    agent_id = card.get("agent_id", "unknown")

    lines = []
    if passed:
        lines.append(f"PASSED: {agent_name} ({agent_id})")
        lines.append(f"Score: {score}/100")
        lines.append("Action permitted.")
    else:
        lines.append(f"BLOCKED: {agent_name} ({agent_id})")
        lines.append(f"Score: {score}/100")
        for r in reasons:
            lines.append(f"Reason: {r}")
        lines.append("Action denied.")

    return "\n".join(lines)


def _make_trust_gate_tool():
    """Create a LlamaIndex FunctionTool wrapping evaluate_trust."""
    if _HAS_LLAMAINDEX:
        return _LlamaIndexFunctionTool.from_defaults(
            fn=evaluate_trust,
            name="kya_trust_gate",
            description=(
                "Check if an AI agent meets trust requirements before performing an action. "
                "Input is a KYA card JSON, minimum score threshold, and optional requirements "
                "(signature, capabilities). Returns PASSED or BLOCKED with reasons."
            ),
        )
    return None


if _HAS_LLAMAINDEX:

    class TrustGateTool:
        """Trust gate as a LlamaIndex FunctionTool.

        Use .as_tool() to get a FunctionTool instance for agent tool belts.
        """

        name = "kya_trust_gate"
        description = "Check if an AI agent meets trust requirements before performing an action."

        @staticmethod
        def as_tool():
            """Return a LlamaIndex FunctionTool for use with AgentRunner."""
            return _make_trust_gate_tool()

        @staticmethod
        def run(
            card_json: str,
            min_score: int = 50,
            require_signature: bool = False,
            required_capabilities: Optional[str] = None,
        ) -> str:
            return evaluate_trust(card_json, min_score, require_signature, required_capabilities)

        _run = run

else:

    class TrustGateTool:  # type: ignore[no-redef]
        """Trust gate tool (llama-index not installed — standalone mode)."""

        name = "kya_trust_gate"
        description = "Check if an AI agent meets trust requirements before performing an action."

        @staticmethod
        def as_tool():
            """LlamaIndex not installed — returns None."""
            return None

        @staticmethod
        def run(
            card_json: str,
            min_score: int = 50,
            require_signature: bool = False,
            required_capabilities: Optional[str] = None,
        ) -> str:
            return evaluate_trust(card_json, min_score, require_signature, required_capabilities)

        _run = run
