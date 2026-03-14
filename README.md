# llamaindex-kya

KYA (Know Your Agent) identity verification for LlamaIndex agents.

## Install

```bash
pip install llamaindex-kya
```

## Quick Start

```python
from llamaindex_kya import KYAQueryEngine

engine = KYAQueryEngine(
    name="my-engine",
    version="1.0.0",
    capabilities=["retrieval", "qa"]
)

card = engine.identity_card()
print(card)
```

## What is KYA?

Know Your Agent (KYA) is an identity standard for AI agents. It provides unique agent identity with Ed25519 signing, framework-native integration, and verifiable credentials.

See [kya-agent](https://github.com/LuciferForge/KYA) for the core library.

## Related

- [kya-agent](https://github.com/LuciferForge/KYA) — Core library
- [crewai-kya](https://github.com/LuciferForge/crewai-kya) — CrewAI
- [autogen-kya](https://github.com/LuciferForge/autogen-kya) — AutoGen
- [langchain-kya](https://github.com/LuciferForge/langchain-kya) — LangChain
- [smolagents-kya](https://github.com/LuciferForge/smolagents-kya) — smolagents
- [dspy-kya](https://github.com/LuciferForge/dspy-kya) — DSPy

## License

MIT
