from __future__ import annotations

from pathlib import Path

from cmgl import __version__

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]


def test_v1_version_and_classifier_are_stable() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)["project"]
    assert project["version"] == "1.1.0"
    assert __version__ == "1.1.0"
    assert "Development Status :: 5 - Production/Stable" in project["classifiers"]
    assert all("Beta" not in classifier for classifier in project["classifiers"])


def test_public_docs_do_not_contain_stale_adapter_language() -> None:
    public_paths = [
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        ROOT / "DEPENDENCIES.md",
        *list((ROOT / "docs").glob("*.md")),
    ]
    forbidden = ("1.0.0", "0.8.0", "pre-1.0", "placeholder", "stub")
    for path in public_paths:
        text = path.read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in text, f"{path} contains stale public wording {term!r}"


def test_readme_names_supported_v1_adapter_shims() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Current public API status: `1.1.0`" in readme
    assert "| Mem0 | Supported shim |" in readme
    assert "| Graphiti | Supported async shim |" in readme
    assert "| LangMem | Supported shim |" in readme
    assert "| LangGraph | Supported helper |" in readme
