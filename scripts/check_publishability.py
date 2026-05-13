from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any

try:  # pragma: no cover - Python 3.10 fallback
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]
DELETED_ROOT_FILES = {
    f"{stem}{suffix}"
    for stem, suffix in [
        ("AGENTS", ".md"),
        ("CONTRIBUTING", ".md"),
        ("NOT" + "ICE", ""),
        ("PLAN", ".md"),
    ]
}
EXCLUDED_SCAN_PARTS = {
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
    "docs",
    "__pycache__",
}
SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token)\b"
    r"\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{32,}[\"']?"
    r"|-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"
)
DELETED_REFERENCE_PATTERNS = {
    name: re.compile(rf"(^|[\s`'\"/\\]){re.escape(name)}($|[\s`'\"/\\,.;:])")
    for name in DELETED_ROOT_FILES
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret-scan-only", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    errors.extend(secret_scan())
    if args.secret_scan_only:
        return report(errors)

    errors.extend(check_deleted_files_absent())
    errors.extend(check_deleted_references())
    errors.extend(check_versions())
    errors.extend(check_env_files())
    errors.extend(check_workflows())
    errors.extend(check_archives())
    errors.extend(smoke_wheel())
    return report(errors)


def report(errors: list[str]) -> int:
    if errors:
        for error in errors:
            print(f"publishability error: {error}", file=sys.stderr)
        return 1
    print("publishability checks passed")
    return 0


def secret_scan() -> list[str]:
    findings: list[str] = []
    for path in iter_repo_files():
        if any(part in EXCLUDED_SCAN_PARTS for part in path.relative_to(ROOT).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in SECRET_PATTERN.finditer(text):
            rel = path.relative_to(ROOT)
            findings.append(f"high-confidence secret-shaped value in {rel}: {match.group(0)[:40]}")
    return findings


def check_deleted_files_absent() -> list[str]:
    return [f"{name} must be absent" for name in DELETED_ROOT_FILES if (ROOT / name).exists()]


def check_deleted_references() -> list[str]:
    targets = [
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        ROOT / "CODE_OF_CONDUCT.md",
        ROOT / "DEPENDENCIES.md",
        ROOT / "THIRD_PARTY_NOTICES.md",
        ROOT / "pyproject.toml",
    ]
    targets.extend((ROOT / "docs").glob("*.md"))
    errors: list[str] = []
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for deleted, pattern in DELETED_REFERENCE_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{path.relative_to(ROOT)} references deleted file {deleted}")
    return errors


def check_versions() -> list[str]:
    errors: list[str] = []
    project = read_project_metadata()
    version = str(project.get("version", ""))
    if version != "1.1.0":
        errors.append(f"project version must be 1.1.0 for this release, got {version!r}")
    classifiers = set(project.get("classifiers", []))
    if "Development Status :: 5 - Production/Stable" not in classifiers:
        errors.append("project classifier must be Production/Stable for v1")
    if any("Beta" in classifier or "Alpha" in classifier for classifier in classifiers):
        errors.append("project classifiers must not contain alpha/beta status for v1")

    init_text = (ROOT / "src" / "cmgl" / "__init__.py").read_text(encoding="utf-8")
    if f'__version__ = "{version}"' not in init_text:
        errors.append("src/cmgl/__init__.py version does not match pyproject")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "1.1.0" not in readme:
        errors.append("README must state the v1.1.0 public API status")

    public_paths = [
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        ROOT / "DEPENDENCIES.md",
        *list((ROOT / "docs").glob("*.md")),
    ]
    stale_patterns = ("1.0.0", "0.8.0", "0.7.0", "pre-1.0", "placeholder", "stub")
    for path in public_paths:
        text = path.read_text(encoding="utf-8")
        for pattern in stale_patterns:
            if pattern in text:
                errors.append(f"{path.relative_to(ROOT)} contains stale public wording: {pattern}")
    return errors


def check_env_files() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob(".env*"):
        rel_parts = path.relative_to(ROOT).parts
        if any(part in {".git", ".venv"} for part in rel_parts):
            continue
        if path.name != ".env.example":
            errors.append(f"real env file is not publishable: {path.relative_to(ROOT)}")
    return errors


def check_workflows() -> list[str]:
    workflow_dir = ROOT / ".github" / "workflows"
    required = ["ci.yml", "security.yml", "publish.yml", "live-adapters.yml"]
    errors = [f"missing workflow {name}" for name in required if not (workflow_dir / name).exists()]
    publish = workflow_dir / "publish.yml"
    if publish.exists():
        text = publish.read_text(encoding="utf-8")
        if "id-token: write" not in text:
            errors.append("publish workflow must use OIDC id-token permission")
        if "password:" in text or "PYPI_API_TOKEN" in text:
            errors.append("publish workflow must not use stored PyPI tokens")
    return errors


def check_archives() -> list[str]:
    dist = ROOT / "dist"
    wheels = sorted(dist.glob("cmgl-*.whl"))
    sdists = sorted(dist.glob("cmgl-*.tar.gz"))
    errors: list[str] = []
    version = str(read_project_metadata().get("version", ""))
    if not wheels:
        errors.append("missing built wheel in dist")
    if not sdists:
        errors.append("missing built sdist in dist")
    for archive in [*wheels, *sdists]:
        if f"cmgl-{version}" not in archive.name:
            errors.append(f"stale or mismatched build artifact: {archive.name}")
    for archive in wheels:
        with zipfile.ZipFile(archive) as zip_file:
            errors.extend(check_archive_names(archive, zip_file.namelist()))
    for archive in sdists:
        with tarfile.open(archive) as tar_file:
            errors.extend(check_archive_names(archive, tar_file.getnames()))
    return errors


def check_archive_names(archive: Path, names: list[str]) -> list[str]:
    errors: list[str] = []
    for name in names:
        parts = set(Path(name).parts)
        if parts & DELETED_ROOT_FILES:
            errors.append(f"{archive.name} contains deleted internal file {name}")
        if parts & {".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}:
            errors.append(f"{archive.name} contains generated local artifact {name}")
    return errors


def smoke_wheel() -> list[str]:
    wheels = sorted((ROOT / "dist").glob("cmgl-*.whl"))
    if not wheels:
        return []
    wheel = wheels[-1]
    expected_version = str(read_project_metadata().get("version", ""))
    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp) / "wheel"
        with zipfile.ZipFile(wheel) as zip_file:
            zip_file.extractall(extract_dir)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(extract_dir)
        commands = [
            [sys.executable, "-c", "import cmgl; print(cmgl.__version__)"],
            [sys.executable, "-m", "cmgl", "version"],
            [sys.executable, "-m", "cmgl", "doctor", "--skip-ledger"],
            [sys.executable, "-m", "cmgl", "schema", "export", str(Path(tmp) / "schemas")],
        ]
        errors: list[str] = []
        for command in commands:
            completed = subprocess.run(
                command,
                cwd=tmp,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                errors.append(
                    "wheel smoke command failed: "
                    f"{' '.join(command)} stderr={completed.stderr.strip()}"
                )
            if command[:2] == [sys.executable, "-c"] and expected_version not in completed.stdout:
                errors.append(
                    f"wheel import reported {completed.stdout.strip()!r}, expected {expected_version}"
                )
        return errors


def iter_repo_files() -> list[Path]:
    return [path for path in ROOT.rglob("*") if path.is_file()]


def read_project_metadata() -> dict[str, Any]:
    with (ROOT / "pyproject.toml").open("rb") as file:
        return dict(tomllib.load(file)["project"])


if __name__ == "__main__":
    raise SystemExit(main())
