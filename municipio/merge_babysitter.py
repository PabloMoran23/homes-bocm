from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from municipio.manifest import MUNICIPIOS_DIR, POC_ROOT

AUTOMATION_BRANCH_RE = re.compile(r"^automation/municipio-(.+)$")
CURSOR_BRANCH_PREFIXES = ("cursor/", "automation/municipio-")
MANIFEST_IN_PR = re.compile(r"^data/municipios/([^/]+)/manifest\.yaml$")


@dataclass
class MunicipioPrCandidate:
    number: int
    title: str
    url: str
    head_ref: str
    slug: str | None
    mergeable: str | None
    review_decision: str | None
    status_check_rollup: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "headRef": self.head_ref,
            "slug": self.slug,
            "mergeable": self.mergeable,
            "reviewDecision": self.review_decision,
            "checks": self.status_check_rollup,
        }


def _gh_json(args: list[str]) -> Any:
    proc = subprocess.run(
        ["gh", *args, "--repo", _gh_repo()],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "gh error").strip())
    return json.loads(proc.stdout or "null")


def _gh_repo() -> str:
    import os

    env = os.environ.get("GITHUB_REPOSITORY")
    if env:
        return env
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=POC_ROOT,
        capture_output=True,
        text=True,
    )
    url = (proc.stdout or "").strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
    if not m:
        raise RuntimeError("No se pudo resolver repo GitHub")
    return m.group(1)


def slug_from_branch(head_ref: str) -> str | None:
    m = AUTOMATION_BRANCH_RE.match(head_ref or "")
    if m:
        from municipio.queue import normalize_open_pr_slug

        return normalize_open_pr_slug(m.group(1))
    return None


def slug_from_pr_files(pr_number: int) -> str | None:
    try:
        data = _gh_json(["pr", "view", str(pr_number), "--json", "files"])
    except RuntimeError:
        return None
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, list):
        return None
    for item in files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        m = MANIFEST_IN_PR.match(path)
        if m and m.group(1) != "_template":
            return m.group(1)
    return None


def resolve_slug(head_ref: str, pr_number: int) -> str | None:
    slug = slug_from_branch(head_ref)
    if slug:
        return slug
    return slug_from_pr_files(pr_number)


def is_municipio_pr(head_ref: str, title: str) -> bool:
    if slug_from_branch(head_ref):
        return True
    if head_ref.startswith(CURSOR_BRANCH_PREFIXES):
        return True
    t = (title or "").lower()
    return "portal ayuntamiento" in t or "municipio" in t and "portal" in t


def list_open_municipio_prs() -> list[MunicipioPrCandidate]:
    prs = _gh_json(
        [
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "500",
            "--json",
            "number,title,url,headRefName,mergeable,reviewDecision,statusCheckRollup",
        ]
    )
    if not isinstance(prs, list):
        return []

    out: list[MunicipioPrCandidate] = []
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        head = str(pr.get("headRefName") or "")
        title = str(pr.get("title") or "")
        if not is_municipio_pr(head, title):
            continue
        number = int(pr["number"])
        slug = resolve_slug(head, number)
        rollup = pr.get("statusCheckRollup") or []
        out.append(
            MunicipioPrCandidate(
                number=number,
                title=title,
                url=str(pr.get("url") or ""),
                head_ref=head,
                slug=slug,
                mergeable=str(pr.get("mergeable") or ""),
                review_decision=str(pr.get("reviewDecision") or ""),
                status_check_rollup=rollup if isinstance(rollup, list) else [],
            )
        )
    out.sort(key=lambda x: x.number)
    return out


def checks_summary(candidate: MunicipioPrCandidate) -> dict[str, Any]:
    checks = candidate.status_check_rollup
    conclusions = []
    pending = 0
    failed = 0
    for c in checks:
        if not isinstance(c, dict):
            continue
        state = str(c.get("state") or c.get("status") or "")
        conclusion = str(c.get("conclusion") or "")
        name = str(c.get("name") or c.get("context") or "?")
        if state.upper() in {"PENDING", "IN_PROGRESS", "QUEUED"} or conclusion == "":
            pending += 1
        elif conclusion.upper() not in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
            failed += 1
        conclusions.append({"name": name, "state": state, "conclusion": conclusion})
    return {
        "total": len(conclusions),
        "pending": pending,
        "failed": failed,
        "allGreen": failed == 0 and pending == 0 and len(conclusions) > 0,
        "items": conclusions,
    }


def build_merge_review_payload() -> dict[str, Any]:
    candidates = list_open_municipio_prs()
    enriched = []
    for c in candidates:
        item = c.to_dict()
        item["checksSummary"] = checks_summary(c)
        item["staticCheckReady"] = bool(c.slug)
        enriched.append(item)

    return {
        "repo": _gh_repo(),
        "openMunicipioPrs": len(enriched),
        "candidates": enriched,
        "scripts": {
            "static": "scripts/check-municipio-pr-static.sh",
            "fullValidate": "scripts/validate-municipio-onboard.sh",
            "postMerge": "scripts/post-merge-municipio.sh",
        },
    }


def main() -> int:
    print(json.dumps(build_merge_review_payload(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
