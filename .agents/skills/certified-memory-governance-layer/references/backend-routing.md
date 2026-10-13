# Backend routing

Use the shortest stable boundary; application setup remains application-owned.

| Backend | Preferred surface | Governing operation |
| --- | --- | --- |
| Custom persistence callable | `GuardedMemoryBackend` | wrap write/update/delete and retain receipt |
| Typed local integration | `GovernanceLayer` | govern events and verify ledger |
| Mem0 | `cmgl.adapters.mem0.Mem0Adapter` | guard add/update/delete; normalize/filter search |
| Graphiti | `cmgl.adapters.graphiti.GraphitiAdapter` | guard episodes; normalize/filter search |
| LangMem | `cmgl.adapters.langmem.LangMemAdapter` | guard memory tools; filter search results |
| LangGraph | supported helper | filter retrieved events before model context |

Do not claim an adapter validates a provider account, every SDK version, or a record's truth.
