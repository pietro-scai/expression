---
name: harness-adapter
description: Contract and template for plugging a new LLM harness into model agent.
---

`expression agent` is harness-agnostic. The default `anthropic-api` harness
talks to the Anthropic API directly. The bundled `claude-code` harness
shells out to a local `claude` CLI. Adding a third (OpenAI, a local
gateway, an internal router) is a small, focused change.

## The contract

Implement the protocol in `src/model/agent/harness.py`:

```python
class Harness(Protocol):
    name: str
    def chat(self, messages: list[Message], system: str,
             tools: list[ToolSpec]) -> HarnessResponse: ...
    def supports_tools(self) -> bool: ...
```

- `messages` — full conversation so far. Roles are `"user"` and
  `"assistant"`. `content` is either a string or a list of structured
  blocks (`text`, `tool_use`, `tool_result`).
- `system` — the system prompt. Includes the agent rules, the loaded
  skill bodies, and a snapshot of the workspace.
- `tools` — JSON-schema tool specs. Pass through to your provider's
  tool-use API. If your harness owns its own tool loop (like the
  `claude-code` CLI), return `False` from `supports_tools()` and ignore
  this argument — the loop won't pass tools through.

`HarnessResponse` has:
- `text` — the assistant's prose for this turn (may be empty if it only
  emitted tool calls).
- `tool_calls: list[ToolCall]` — populated when the model wants to call
  tools the harness exposed.
- `stop_reason` — opaque string from the provider.
- `usage` — billing metadata; logged to the trace, not used by the loop.

## Template

```python
# src/model/agent/harnesses/openai_compatible.py
from ..harness import (
    Harness, HarnessResponse, Message, ToolCall, ToolSpec, register_harness,
)
import os

class OpenAICompatibleHarness:
    name = "openai-compat"

    def __init__(self):
        from openai import OpenAI  # lazy import — keep deps optional
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("Set OPENAI_API_KEY (https://platform.openai.com/api-keys)")
        self._client = OpenAI(api_key=key)

    def supports_tools(self) -> bool:
        return True

    def chat(self, messages, system, tools) -> HarnessResponse:
        # Translate `messages` and `tools` into your provider's schema,
        # call its chat-completions endpoint, then translate the response
        # blocks back into HarnessResponse / ToolCall.
        ...

register_harness("openai-compat", OpenAICompatibleHarness)
```

Then import the module in `src/model/agent/__init__.py` so it's auto-
registered when `expression agent` starts. That's it — no other surface area
to plug into.

## Guidelines

- **Lazy-import provider SDKs** so installing `model` doesn't pull every
  vendor's library.
- **Validate config in `__init__`**, not on the first call. Fail fast
  with a clear error that tells the user how to set the missing
  variable.
- **Cache the system prompt** if your provider supports it. The skills
  block is long and stable across turns within a session.
- **Don't hide tool-use round-trips inside the harness.** The loop
  expects to see tool calls, dispatch them, and feed results back. If
  your harness owns its own tool loop (like `claude-code`), return
  `False` from `supports_tools()` and document that limitation.
- **Keep the harness pure.** All side effects (file writes, expression runs)
  go through the loop's tool dispatcher, which gates on user
  confirmation and writes to the trace. Bypassing that breaks the
  audit trail.
