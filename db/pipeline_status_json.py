#!/usr/bin/env python3
"""
Emite un JSON con el estado del pipeline SIGMA/NTI (SQLite, log, visor JSON).
Uso: python3 db/pipeline_status_json.py /ruta/poc-bocm
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _tail_text(path: Path, max_bytes: int = 120_000) -> str:
    if not path.is_file():
        return ""
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="replace")


def _parse_log_progress(tail: str) -> dict:
    out: dict = {
        "phase": "desconocido",
        "fetchCurrent": None,
        "fetchTotal": None,
        "lastLines": [],
    }
    lines = [ln.rstrip() for ln in tail.splitlines() if ln.strip()]
    out["lastLines"] = lines[-24:]

    low = tail.lower()

    def rfind(subs: tuple[str, ...]) -> int:
        best = -1
        for s in subs:
            j = low.rfind(s)
            if j > best:
                best = j
        return best

    p_done = rfind(("pipeline done",))
    p_dl = rfind(("download nti pendientes", "download_nti_sqlite"))
    p_in = rfind(("ingest_visor_sqlite", "ingest sqlite"))
    p_vf = rfind(("madrid_viso_fetch", "visor fetch (todos"))

    cand = [(p_done, "completado"), (p_dl, "descarga_nti"), (p_in, "ingest_sqlite"), (p_vf, "visor_fetch")]
    cand_ok = [(p, ph) for p, ph in cand if p >= 0]

    out["phase"] = "desconocido"
    if cand_ok:
        out["phase"] = max(cand_ok, key=lambda x: x[0])[1]
    else:
        blob = "".join(lines[-30:]).lower()
        if "madrid_viso_fetch" in blob or "[" in blob and "]" in blob and " ok " in blob:
            out["phase"] = "visor_fetch"

    for ln in reversed(lines):
        m = re.search(r"\[\s*(\d+)\s*/\s*(\d+)\s*\]\s*OK", ln)
        if m:
            out["fetchCurrent"] = int(m.group(1))
            out["fetchTotal"] = int(m.group(2))
            break

    err_hits = [ln for ln in lines if re.search(r"\berror\b|\btraceback\b|http\s*50", ln, re.I)]
    out["errorLineCount"] = len(err_hits)
    out["errorSample"] = err_hits[-8:]

    return out


def _visor_stats(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"exists": True, "parseError": str(e)}
    by_g = raw.get("byGrupoExpediente") or {}
    con_ficha = sum(
        1
        for v in by_g.values()
        if isinstance(v, dict) and (v.get("tramitacion") or v.get("documentacionUrls"))
    )
    con_nti = sum(
        1
        for v in by_g.values()
        if isinstance(v, dict)
        and v.get("ntiArbol")
        and isinstance(v["ntiArbol"], dict)
        and (v["ntiArbol"].get("documentos") or v["ntiArbol"].get("documentosMuestra"))
    )
    con_ficha_html = sum(
        1 for v in by_g.values() if isinstance(v, dict) and v.get("visorFicha")
    )
    return {
        "exists": True,
        "generatedAt": raw.get("generatedAt"),
        "expedientesEnJson": len(by_g),
        "conVisorFicha": con_ficha_html,
        "conFichaTramitacionOUrls": con_ficha,
        "conArbolNti": con_nti,
    }


def _sqlite_stats(db: Path) -> dict:
    if not db.is_file():
        return {"exists": False}
    con = sqlite3.connect(str(db))
    try:
        def one(q: str) -> int:
            r = con.execute(q).fetchone()
            return int(r[0]) if r and r[0] is not None else 0

        nti_total = one("SELECT COUNT(*) FROM sigma_nti_document")
        nti_ok = one(
            "SELECT COUNT(*) FROM sigma_nti_document WHERE local_path IS NOT NULL AND TRIM(local_path) != ''"
        )
        nti_err = one(
            "SELECT COUNT(*) FROM sigma_nti_document WHERE download_error IS NOT NULL AND TRIM(download_error) != ''"
        )
        nti_pend = nti_total - nti_ok
        tram = one("SELECT COUNT(*) FROM sigma_vis_tramite")
        exp_cat = one("SELECT COUNT(*) FROM sigma_catalog_expediente")
        exp_link = one("SELECT COUNT(*) FROM link_project_sigma")
        return {
            "exists": True,
            "sigmaCatalogExpedientes": exp_cat,
            "linkProjectSigma": exp_link,
            "tramiteRows": tram,
            "ntiDocumentRows": nti_total,
            "ntiDescargados": nti_ok,
            "ntiPendientes": max(0, nti_pend),
            "ntiConError": nti_err,
            "ntiPct": round(100.0 * nti_ok / nti_total, 1) if nti_total else None,
        }
    finally:
        con.close()


def _process_grep() -> dict:
    out = {"visorFetchRunning": False, "downloadRunning": False, "pipelineScriptRunning": False}
    try:
        r = subprocess.run(
            ["pgrep", "-af", "madrid_viso_fetch"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        out["visorFetchRunning"] = bool(r.stdout.strip())
        out["visorFetchSample"] = r.stdout.strip().split("\n")[0][:200] if r.stdout.strip() else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    try:
        r = subprocess.run(
            ["pgrep", "-af", "download_nti_sqlite"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        out["downloadRunning"] = bool(r.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    try:
        r = subprocess.run(
            ["pgrep", "-af", "run_full_pipeline_bg"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        out["pipelineScriptRunning"] = bool(r.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return out


def build_status(poc_root: Path) -> dict:
    poc_root = poc_root.resolve()
    log_path = poc_root / "output" / "poc_sigma_full_pipeline.log"
    visor_path = poc_root / "output" / "madrid_viso_expedientes.json"
    db_path = poc_root / "db" / "poc_local.sqlite"

    tail = _tail_text(log_path)
    log_meta = _parse_log_progress(tail)
    if log_path.is_file():
        log_meta["logPath"] = str(log_path.relative_to(poc_root))
        log_meta["logBytes"] = log_path.stat().st_size
        log_meta["logMtime"] = datetime.fromtimestamp(
            log_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "pocRoot": str(poc_root),
        "sqlite": _sqlite_stats(db_path),
        "visorJson": _visor_stats(visor_path),
        "log": log_meta,
        "processes": _process_grep(),
    }


def main() -> None:
    poc = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    print(json.dumps(build_status(poc), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
