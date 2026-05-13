from __future__ import annotations

import asyncio
import os
from importlib import import_module
from importlib.util import find_spec
from typing import Any, Literal
from uuid import uuid4

from cmgl.time import now_utc

ADAPTER_TARGETS = ("mem0", "graphiti", "langmem", "langgraph")

_DEPENDENCIES = {
    "mem0": "mem0",
    "graphiti": "graphiti_core",
    "langmem": "langmem",
    "langgraph": "langgraph",
}
_REQUIRED_ENV = {
    "mem0": ("OPENAI_API_KEY",),
    "graphiti": ("OPENAI_API_KEY", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"),
    "langmem": (),
    "langgraph": (),
}


def adapter_doctor() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for target in ADAPTER_TARGETS:
        module_name = f"cmgl.adapters.{target}"
        dependency = _DEPENDENCIES[target]
        checks.append(_import_check(f"adapter:{target}", module_name))
        checks.append(_import_check(f"optional_dependency:{target}", dependency))
    return {
        "schema_version": "cmgl.adapters_doctor_report.v1",
        "ok": all(bool(item["ok"]) for item in checks if item["required"]),
        "checks": checks,
        "network": "not_used",
    }


def run_live_smoke(
    *,
    target: Literal["mem0", "graphiti", "langmem", "langgraph", "all"] = "all",
    dry_run: bool = False,
    require_live_env: bool = False,
) -> dict[str, Any]:
    targets = list(ADAPTER_TARGETS) if target == "all" else [target]
    checks: list[dict[str, Any]] = []
    for item in targets:
        dependency = _DEPENDENCIES[item]
        checks.append(_import_check(f"optional_dependency:{item}", dependency))
        missing = [name for name in _REQUIRED_ENV[item] if not os.environ.get(name)]
        env_ok = not missing or dry_run or not require_live_env
        checks.append(
            {
                "name": f"env:{item}",
                "ok": env_ok,
                "required": require_live_env and not dry_run,
                "detail": _env_detail(missing=missing, dry_run=dry_run),
            }
        )
        if dry_run:
            checks.append(
                {
                    "name": f"live_call:{item}",
                    "ok": True,
                    "required": False,
                    "detail": "not called in dry-run",
                }
            )
        elif missing:
            checks.append(
                {
                    "name": f"live_call:{item}",
                    "ok": not require_live_env,
                    "required": require_live_env,
                    "detail": f"skipped because required environment is missing: {', '.join(missing)}",
                }
            )
        else:
            checks.append(_run_live_target(item))
    return {
        "schema_version": "cmgl.live_adapter_smoke_report.v1",
        "target": target,
        "dry_run": dry_run,
        "require_live_env": require_live_env,
        "ok": all(bool(item["ok"]) for item in checks if item["required"]),
        "checks": checks,
    }


def _env_detail(*, missing: list[str], dry_run: bool) -> str:
    if dry_run:
        return "dry-run"
    if missing:
        return f"missing but skipped: {', '.join(missing)}"
    return "configured"


def _import_check(name: str, module_name: str) -> dict[str, Any]:
    if name.startswith("optional_dependency:"):
        found = find_spec(module_name) is not None
        return {
            "name": name,
            "ok": found,
            "required": False,
            "detail": "installed" if found else "not installed",
        }
    try:
        import_module(module_name)
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "required": False,
            "detail": f"not importable: {type(exc).__name__}: {exc}",
        }
    return {"name": name, "ok": True, "required": False, "detail": "importable"}


def _run_live_target(target: str) -> dict[str, Any]:
    try:
        if target == "mem0":
            detail = _run_mem0_smoke()
        elif target == "graphiti":
            detail = asyncio.run(_run_graphiti_smoke())
        elif target == "langmem":
            detail = _run_langmem_smoke()
        elif target == "langgraph":
            detail = _run_langgraph_smoke()
        else:  # pragma: no cover - guarded by CLI/parser choices
            raise ValueError(f"unsupported live target: {target}")
    except Exception as exc:
        return {
            "name": f"live_call:{target}",
            "ok": False,
            "required": True,
            "detail": f"{type(exc).__name__}: {exc}",
        }
    return {"name": f"live_call:{target}", "ok": True, "required": True, "detail": detail}


def _run_mem0_smoke() -> str:
    from mem0 import Memory

    user_prefix = os.environ.get("MEM0_TEST_USER_PREFIX", "cmgl-live")
    user_id = f"{user_prefix}-{uuid4()}"
    memory = Memory()
    memory.add(
        [
            {
                "role": "user",
                "content": "CMGL live smoke: user prefers deterministic local evidence.",
            }
        ],
        user_id=user_id,
    )
    memory.search("deterministic local evidence", filters={"user_id": user_id})
    return "Mem0 add/search completed for isolated test user"


async def _run_graphiti_smoke() -> str:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EpisodeType

    graphiti = Graphiti(
        os.environ["NEO4J_URI"],
        os.environ["NEO4J_USER"],
        os.environ["NEO4J_PASSWORD"],
    )
    try:
        await graphiti.build_indices_and_constraints()
        await graphiti.add_episode(
            name=f"cmgl-live-{uuid4()}",
            episode_body="CMGL live smoke episode with no secret material.",
            source=EpisodeType.text,
            source_description="CMGL live adapter smoke",
            reference_time=now_utc(),
        )
        await graphiti.search("CMGL live smoke episode")
    finally:
        await _close_graphiti(graphiti)
    return "Graphiti add_episode/search completed against configured Neo4j"


def _run_langmem_smoke() -> str:
    from langgraph.store.memory import InMemoryStore
    from langmem import create_manage_memory_tool, create_search_memory_tool

    namespace = ("cmgl-live", str(uuid4()))
    store = InMemoryStore()
    manage_tool = create_manage_memory_tool(namespace=namespace, store=store)
    search_tool = create_search_memory_tool(namespace=namespace, store=store)
    manage_tool.invoke({"content": "CMGL live smoke LangMem memory", "action": "create"})
    search_tool.invoke({"query": "CMGL live smoke", "limit": 1})
    return "LangMem manage/search tools completed with local InMemoryStore"


def _run_langgraph_smoke() -> str:
    from langgraph.store.memory import InMemoryStore

    namespace = ("cmgl-live", str(uuid4()))
    store = InMemoryStore()
    store.put(namespace, "1", {"data": "CMGL live smoke LangGraph store memory"})
    store.search(namespace, query="CMGL live smoke", limit=1)
    return "LangGraph InMemoryStore put/search completed locally"


async def _close_graphiti(client: Any) -> None:
    await client.close()
