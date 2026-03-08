"""llamaindex-kya — KYA (Know Your Agent) identity verification for LlamaIndex agents.

Provides tools, decorators, and helpers to bring cryptographic agent identity
to LlamaIndex workflows. No blockchain, no cloud dependency — just Ed25519 signatures.

Usage:
    from llamaindex_kya import KYAIdentityTool, TrustGateTool, create_agent_card, attach_card
"""

__version__ = "0.1.0"

from llamaindex_kya.card import create_agent_card, attach_card, get_card
from llamaindex_kya.identity import KYAIdentityTool
from llamaindex_kya.trust_gate import TrustGateTool
from llamaindex_kya.middleware import kya_verified

__all__ = [
    "KYAIdentityTool",
    "TrustGateTool",
    "kya_verified",
    "create_agent_card",
    "attach_card",
    "get_card",
]
