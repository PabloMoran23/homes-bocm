#!/usr/bin/env python3
"""Cierra PRs duplicadas de municipios y mergea las canónicas a main."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_ROOT))

from municipio.manifest import slugify  # noqa: E402

AUTOMATION_BRANCH_RE = re.compile(r"^automation/municipio-(.+)$")
MANIFEST_PATH_RE = re.compile(r"^data/municipios/([^/]+)/manifest\.yaml$")
BRANCH_SLUG_SUFFIX_RE = re.compile(r"-v\d+$")
MUNICIPIO_TITLE_RE = re.compile(r"portal ayuntamiento\s+(.+)$", re.I)


def run(cmd: list[str], *, check: bool = True, cwd: Path = POC_ROOT) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def gh_json(args: list[str]) -> Any:
    proc = run(["gh", *args], check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "gh error")
    return json.loads(proc.stdout or "null")


def normalize_slug(slug: str) -> str:
    return BRANCH_SLUG_SUFFIX_RE.sub("", slug.strip())


def main_slugs() -> set[str]:
    base = POC_ROOT / "data" / "municipios"
    return {p.name for p in base.iterdir() if p.is_dir() and (p / "manifest.yaml").is_file()}


@dataclass
class PrInfo:
    number: int
    title: str
    url: str
    head_ref: str
    slug: str | None
    mergeable: str
    created_at: str

    @property
    def rank(self) -> tuple:
        exact = 1 if self.slug and self.head_ref == f"automation/municipio-{self.slug}" else 0
        auto = 1 if self.head_ref.startswith("automation/municipio-") else 0
        return (exact, auto, self.number)


def resolve_slug(pr: dict) -> str | None:
    head = str(pr.get("headRefName") or "")
    m = AUTOMATION_BRANCH_RE.match(head)
    if m:
        return normalize_slug(m.group(1))
    number = pr.get("number")
    if number is None:
        return None
    data = gh_json(["pr", "view", str(number), "--json", "files"])
    for item in data.get("files") or []:
        path = str(item.get("path") or "")
        m2 = MANIFEST_PATH_RE.match(path)
        if m2 and m2.group(1) != "_template":
            return m2.group(1)
    title = str(pr.get("title") or "")
    m3 = MUNICIPIO_TITLE_RE.search(title)
    if m3:
        return slugify(m3.group(1).strip())
    return None


def list_open_prs() -> list[PrInfo]:
    raw = gh_json(
        [
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "500",
            "--json",
            "number,title,url,headRefName,mergeable,createdAt",
        ]
    )
    out: list[PrInfo] = []
    for pr in raw:
        slug = resolve_slug(pr)
        out.append(
            PrInfo(
                number=int(pr["number"]),
                title=str(pr.get("title") or ""),
                url=str(pr.get("url") or ""),
                head_ref=str(pr.get("headRefName") or ""),
                slug=slug,
                mergeable=str(pr.get("mergeable") or "UNKNOWN"),
                created_at=str(pr.get("createdAt") or ""),
            )
        )
    return out


def close_pr(number: int, comment: str) -> None:
    run(["gh", "pr", "close", str(number), "--comment", comment], check=False)


def adapter_paths_for_slug(slug: str) -> list[str]:
    paths = []
    manifest = POC_ROOT / "data" / "municipios" / slug / "manifest.yaml"
    if manifest.is_file():
        import yaml

        raw = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        adapter = (raw.get("portal") or {}).get("adapter") or ""
        if adapter:
            mod = adapter.split(":", 1)[0].strip()
            rel = mod.replace(".", "/") + ".py"
            paths.append(rel)
    # fallback glob
    for p in (POC_ROOT / "municipio" / "adapters").glob("*.py"):
        if slug.replace("-", "_") in p.stem or slug in p.stem:
            paths.append(str(p.relative_to(POC_ROOT)))
    return paths


def resolve_merge_conflicts(slug: str) -> None:
    """En rama PR tras merge conflictivo: main gana queue; PR gana municipio."""
    status = run(["git", "diff", "--name-only", "--diff-filter=U"], check=False)
    conflicted = [ln.strip() for ln in (status.stdout or "").splitlines() if ln.strip()]
    if not conflicted:
        return
    municipio_prefix = f"data/municipios/{slug}/"
    adapter_paths = set(adapter_paths_for_slug(slug))
    for path in conflicted:
        if path == "data/municipios/queue.yaml":
            run(["git", "checkout", "--theirs", path], check=False)
        elif path.startswith(municipio_prefix) or path in adapter_paths:
            run(["git", "checkout", "--ours", path], check=False)
        else:
            run(["git", "checkout", "--ours", path], check=False)
        run(["git", "add", path], check=False)


def rebase_and_push(number: int, slug: str) -> bool:
    run(["git", "fetch", "origin", "main"], check=True)
    run(["git", "checkout", "main"], check=True)
    run(["git", "reset", "--hard", "origin/main"], check=True)
    proc = run(["gh", "pr", "checkout", str(number)], check=False)
    if proc.returncode != 0:
        print(f"WARN: checkout PR #{number} failed:\n{proc.stderr}", flush=True)
        return False

    merge = run(["git", "merge", "origin/main", "-m", f"merge main into PR #{number}"], check=False)
    if merge.returncode != 0:
        resolve_merge_conflicts(slug)
        commit = run(["git", "commit", "-m", f"resolve merge conflicts with main (PR #{number})"], check=False)
        if commit.returncode != 0:
            print(f"WARN: could not commit conflict resolution for #{number}", flush=True)
            run(["git", "merge", "--abort"], check=False)
            return False

    run(
        ["git", "restore", "--source=origin/main", "--staged", "--worktree", "data/municipios/queue.yaml"],
        check=False,
    )

    static = run(["./scripts/check-municipio-pr-static.sh", slug], check=False)
    if static.returncode != 0:
        print(f"WARN: static check failed for {slug} PR #{number}:\n{static.stdout}\n{static.stderr}", flush=True)
        return False

    push = run(["git", "push", "origin", "HEAD"], check=False)
    if push.returncode != 0:
        print(f"WARN: push failed for #{number}:\n{push.stderr}", flush=True)
        return False
    return True


def merge_pr(number: int, title: str) -> bool:
    for _ in range(12):
        view = gh_json(["pr", "view", str(number), "--json", "mergeable,mergeStateStatus"])
        mergeable = view.get("mergeable")
        state = view.get("mergeStateStatus")
        if mergeable == "MERGEABLE" and state == "CLEAN":
            break
        if mergeable == "CONFLICTING":
            return False
        time.sleep(5)
    proc = run(
        ["gh", "pr", "merge", str(number), "--squash", "--delete-branch", "--subject", title],
        check=False,
    )
    if proc.returncode != 0:
        print(f"WARN: merge failed #{number}:\n{proc.stderr}", flush=True)
        return False
    return True


def main() -> int:
    merged_slugs = main_slugs()
    prs = list_open_prs()
    municipio_prs = [p for p in prs if p.slug and "portal ayuntamiento" in p.title.lower()]

    by_slug: dict[str, list[PrInfo]] = defaultdict(list)
    for p in municipio_prs:
        by_slug[p.slug].append(p)

    closed = 0
    merged = 0
    failed: list[str] = []

    for slug in sorted(merged_slugs):
        for pr in by_slug.get(slug, []):
            close_pr(pr.number, f"Cerrada por cleanup: `{slug}` ya está en `main`.")
            closed += 1
        by_slug.pop(slug, None)

    pending = sorted(by_slug.keys(), key=lambda s: max(p.number for p in by_slug[s]))
    for slug in pending:
        group = sorted(by_slug[slug], key=lambda p: p.rank, reverse=True)
        canonical = group[0]
        for dup in group[1:]:
            close_pr(dup.number, f"Duplicada de #{canonical.number} (`{slug}`). Cleanup automático.")
            closed += 1

        print(f"\n=== {slug}: PR #{canonical.number} ===", flush=True)
        if not rebase_and_push(canonical.number, slug):
            failed.append(f"{slug} (#{canonical.number}) rebase")
            continue
        if merge_pr(canonical.number, canonical.title):
            merged += 1
            merged_slugs.add(slug)
            run(["git", "checkout", "main"], check=False)
            run(["git", "pull", "origin", "main"], check=False)
        else:
            failed.append(f"{slug} (#{canonical.number}) merge")

    summary = {
        "closed": closed,
        "merged": merged,
        "failed": failed,
        "open_after": len(list_open_prs()),
    }
    print(json.dumps(summary, indent=2), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
