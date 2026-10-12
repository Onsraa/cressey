"""Imports point one way. The types know nothing of ours, the model clients know the types,
the core and the guides know both but never each other, and only the app wires them. The
demo, the evals and the tests sit on top and may use the test doubles; nothing else may."""

import ast
from pathlib import Path

SRC = Path(__file__).parents[1] / "src" / "cressey"
# What each part may import from cressey, besides itself.
BASE = {"domain", "settings", "tasks"}
ALLOWED: dict[str, set[str]] = {
    "domain": set(),
    "settings": set(),
    "tasks": set(),
    "scan": {"domain"},
    "store": {"domain", "scan"},
    "llm": {"domain", "settings"},
    "judge": {"domain", "llm", "settings"},
    "engine": BASE | {"scan", "store", "llm", "judge"},
    "adapters": BASE | {"scan", "store", "llm", "judge", "engine"},
    "incidents": BASE | {"scan", "store", "engine"},
    "replay": {"domain", "settings", "store", "incidents", "demo"},
    "core": BASE | {"scan", "store", "llm", "judge", "engine", "adapters", "incidents"},
    "guide": {"domain", "llm", "settings"},
    "export_openapi": {"app", "settings"},
    "__init__": set(),
}
EVERYTHING = set(ALLOWED) | {"app", "demo", "testing"}
ALLOWED |= {"app": EVERYTHING - {"testing"}, "demo": EVERYTHING, "testing": EVERYTHING}


def _part(module: str) -> str:
    """cressey.core.api -> core; cressey.app -> app; cressey -> __init__."""
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else "__init__"


def _imported(path: Path) -> set[str]:
    """Every cressey module the file imports, those inside functions too."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
    return {m for m in found if m == "cressey" or m.startswith("cressey.")}


def test_imports_point_one_way():
    wrong = []
    for path in sorted(SRC.rglob("*.py")):
        module = ".".join(path.relative_to(SRC.parent).with_suffix("").parts)
        own = _part(module.removesuffix(".__init__"))
        for target in sorted(map(_part, _imported(path))):
            if target != own and target not in ALLOWED[own]:
                wrong.append(f"{module} -> {target}")
    assert wrong == []
