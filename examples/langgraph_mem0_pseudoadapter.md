# LangGraph + Mem0 integration pattern

CMGL can sit between a LangGraph context-building step and a Mem0 retrieval/write path.

```text
LangGraph node
  -> retrieve raw memories from Mem0
  -> normalize raw hits with Mem0Adapter
  -> run CMGL retrieval filter
  -> pass only admitted memories into LangGraph state/context
```

For persistent writes:

```text
agent observation
  -> structured AuthorityBundle
  -> CMGL strict promotion path
  -> Mem0Adapter calls Mem0 only when admitted
  -> AdapterOperationReceipt binds CMGL memory_id/update_id to Mem0 id
```

Minimal shape:

```python
from cmgl.adapters.langgraph import LangGraphAdapter
from cmgl.adapters.mem0 import Mem0Adapter

mem0_adapter = Mem0Adapter(mem0_client, authority_scope="user:demo")
langgraph_adapter = LangGraphAdapter(authority_scope="user:demo")

write_bundle = mem0_adapter.add(
    "User prefers morning meetings.",
    authority_bundle=authority_bundle,
)

raw = mem0_adapter.search("meeting preference")
filtered = langgraph_adapter.filter_events("meeting preference", raw)
context = [event.content for event in filtered.admitted_events]
```

Core tests use fake clients. Live Mem0 credentials and LangGraph graph topology remain application-owned.
