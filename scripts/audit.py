"""System audit — what's actually wired up vs dead code.

Static analysis only. Idempotent. No DB writes.
Run: python3 scripts/audit.py > /tmp/audit_static.md
"""
import ast
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOT = REPO / "bot"


def find_imports() -> dict[str, set[str]]:
    """Map: file → set of bot.* modules it imports."""
    graph: dict[str, set[str]] = defaultdict(set)
    for py in BOT.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("bot."):
                graph[str(py.relative_to(REPO))].add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("bot."):
                        graph[str(py.relative_to(REPO))].add(alias.name)
    return graph


def count_defs(path: Path) -> tuple[int, int]:
    """Return (loc, function_count) for a python file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return 0, 0
    loc = sum(1 for _ in text.splitlines())
    funcs = 0
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs += 1
    except SyntaxError:
        pass
    return loc, funcs


def text_references(target: str, search_dirs: list[Path]) -> list[str]:
    """Files that mention `target` as a substring."""
    hits = []
    for d in search_dirs:
        for py in d.rglob("*.py"):
            try:
                if target in py.read_text(encoding="utf-8"):
                    hits.append(str(py.relative_to(REPO)))
            except (UnicodeDecodeError, FileNotFoundError):
                continue
    return hits


def main() -> None:
    graph = find_imports()
    # Reverse map: module → set of files that import it
    importers: dict[str, set[str]] = defaultdict(set)
    for file, imports in graph.items():
        for imp in imports:
            importers[imp].add(file)

    print("# AUDIT REPORT — Static Analysis\n")
    print(f"_Generated: {datetime.now(timezone.utc).isoformat()}_\n")
    print(f"_Repo: {REPO.name}_\n")

    # ─── Core modules ─────────────────────────────────────────────────────
    print("## Core Modules (`bot/core/`)\n")
    print("| Module | LOC | Funcs | Importers | Status |")
    print("|---|---:|---:|---:|---|")
    core_dead: list[tuple[str, int]] = []
    core_stub: list[tuple[str, int]] = []
    for f in sorted((BOT / "core").glob("*.py")):
        if f.name == "__init__.py":
            continue
        modname = f"bot.core.{f.stem}"
        imps = importers.get(modname, set())
        loc, funcs = count_defs(f)
        if not imps:
            status = "DEAD"
            core_dead.append((f.name, loc))
        elif funcs < 2:
            status = "STUB"
            core_stub.append((f.name, loc))
        else:
            status = "WIRED"
        print(f"| {f.name} | {loc} | {funcs} | {len(imps)} | **{status}** |")

    print("\n### Importer detail (WIRED only)\n")
    for f in sorted((BOT / "core").glob("*.py")):
        if f.name == "__init__.py":
            continue
        modname = f"bot.core.{f.stem}"
        imps = importers.get(modname, set())
        if not imps:
            continue
        print(f"- **{f.name}**: {len(imps)} importer(s)")
        for imp in sorted(imps):
            print(f"  - `{imp}`")

    # ─── Scheduler jobs ───────────────────────────────────────────────────
    print("\n## Scheduler Jobs (`bot/jobs/`)\n")
    print("| Job File | LOC | Funcs | Registered in scheduler.py? |")
    print("|---|---:|---:|---|")
    scheduler_path = BOT / "jobs" / "scheduler.py"
    try:
        scheduler_text = scheduler_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        scheduler_text = ""
    job_orphans: list[str] = []
    for f in sorted((BOT / "jobs").glob("*.py")):
        if f.name in ("__init__.py", "scheduler.py"):
            continue
        # Check if any function in this file is referenced in scheduler.py
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        public_funcs = [
            n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_")
        ]
        registered = any(fn in scheduler_text for fn in public_funcs) or f.stem in scheduler_text
        loc, funcs = count_defs(f)
        flag = "✓" if registered else "✗ ORPHAN"
        if not registered:
            job_orphans.append(f.name)
        print(f"| {f.name} | {loc} | {funcs} | {flag} |")

    # ─── Summary recommendations ──────────────────────────────────────────
    print("\n## Top Findings (recommendations)\n")

    print("### Dead modules (no importers)\n")
    if not core_dead:
        print("_None — all core modules have at least one importer._")
    else:
        for name, loc in sorted(core_dead, key=lambda x: -x[1])[:10]:
            print(f"- `bot/core/{name}` ({loc} LOC) — no importers, candidate for deletion")

    print("\n### Stub modules (1 or 0 functions)\n")
    if not core_stub:
        print("_None._")
    else:
        for name, loc in sorted(core_stub, key=lambda x: -x[1])[:10]:
            print(f"- `bot/core/{name}` ({loc} LOC) — stub/thin")

    print("\n### Orphan scheduler jobs (not in scheduler.py)\n")
    if not job_orphans:
        print("_None — all jobs are registered._")
    else:
        for name in job_orphans:
            print(f"- `bot/jobs/{name}` — not referenced in scheduler.py")

    # Aggregate stats
    print("\n## Stats\n")
    total_files = sum(1 for _ in BOT.rglob("*.py"))
    total_loc = sum(count_defs(p)[0] for p in BOT.rglob("*.py"))
    print(f"- Total Python files in `bot/`: {total_files}")
    print(f"- Total LOC: {total_loc}")
    print(f"- Core modules: {sum(1 for _ in (BOT / 'core').glob('*.py')) - 1}")
    print(f"- Scheduler job files: {sum(1 for f in (BOT / 'jobs').glob('*.py') if f.name not in ('__init__.py', 'scheduler.py'))}")
    print(f"- Dead modules: {len(core_dead)}")
    print(f"- Stub modules: {len(core_stub)}")
    print(f"- Orphan jobs: {len(job_orphans)}")


if __name__ == "__main__":
    main()
