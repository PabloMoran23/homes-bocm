#!/usr/bin/env python3
"""
Descarga ficheros enlazados en el árbol NTI (output de madrid_viso_fetch.py).

Lee metadatos de output/madrid_viso_expedientes.json y baja sólo URLs de hosts
considerados públicos Madrid; escribe artefactos por expediente y manifest.json.

Ejemplos desde poc-bocm/:

  python3 -m sector_geometry.madrid_viso_docs_download --exp 135/2021/00618 --max-files 5
  python3 -m sector_geometry.madrid_viso_docs_download --limit-expedientes 2 --max-files 3 --delay 0.5
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sector_geometry.madrid_viso_filters import (
    expediente_is_recent,
    filter_nti_documents,
)

POC_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = POC_ROOT / "output"
VISOR_JSON = OUTPUT_DIR / "madrid_viso_expedientes.json"
DOWNLOAD_ROOT = OUTPUT_DIR / "madrid_nti_downloads"

USER_AGENT = "poc-bocm-madrid-viso-docs/1.0 (+datos públicos Madrid)"

ALLOWED_NETLOCS = frozenset(
    {
        "www-2.munimadrid.es",
        "servpub.madrid.es",
        "www-s.madrid.es",
        "sigma.madrid.es",
        "munimadrid.es",
        "www.munimadrid.es",
        "datos.madrid.es",
    }
)


def _norm_exp(grupo: str) -> str:
    return grupo.replace("/", "_").replace("\\", "_").strip()


def _safe_slug(s: str, max_len: int = 96) -> str:
    raw = (s or "").strip()
    raw = raw.replace("/", "-")
    raw = re.sub(r"[^\w\s.\-()+]", "_", raw, flags=re.UNICODE)
    raw = re.sub(r"\s+", " ", raw).strip(" ._")
    return (raw[:max_len] or "doc").rstrip(".")


def norm_grupo_clave(x: str) -> str:
    """Normaliza entrada CLI (135_2021_00618) a la clave JSON (135/2021/00618)."""
    return x.replace("_", "/").replace("\\", "/").strip()


def nti_documents_from_record(rec: dict[str, Any]) -> list[dict[str, Any]]:
    nti = rec.get("ntiArbol") if isinstance(rec.get("ntiArbol"), dict) else None
    if not nti:
        return []
    full = nti.get("documentos")
    if isinstance(full, list) and full:
        return full
    muestra = nti.get("documentosMuestra")
    if isinstance(muestra, list):
        return muestra
    return []


def _host_allowed(parsed: urllib.parse.ParseResult) -> bool:
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in ALLOWED_NETLOCS:
        return True
    # subdominio *.munimadrid.es / *.madrid.es razonables
    if host.endswith(".munimadrid.es") or host.endswith(".madrid.es"):
        return True
    return False


def normalize_nti_download_url(raw: str) -> tuple[str | None, str | None]:
    """
    Devuelve URL absoluta codificada para urllib o (None, motivo).
    El árbol NTI a veces entrega rutas relativas o hrefs rotos (null_{--}, espacios sin escapar).
    """
    u = (raw or "").strip()
    if not u:
        return None, "URL vacía"
    low = u.lower()
    if "null_{" in low or "{--}" in low or "\n" in u or "\r" in u:
        return None, "URL corrupta (placeholder o saltos en href NTI)"

    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/fsdescargas/") or u.startswith("/FSdescargas/"):
        u = "https://www-2.munimadrid.es" + u
    elif u.startswith("/VSURB_WBVISOR/") or u.startswith("/vsurb_wbvisor/"):
        u = "https://servpub.madrid.es" + u
    elif u.startswith("/") and not u.startswith("/http"):
        # Rutas relativas ocasionales del portal
        u = "https://www-2.munimadrid.es" + u

    try:
        parts = urllib.parse.urlsplit(u)
        if parts.scheme not in ("http", "https"):
            return None, "Esquema no http(s)"
        if not parts.netloc:
            return None, "Sin host"
        path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%._-()!")
        out = urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc.lower(), path, parts.query, parts.fragment)
        )
        return out, None
    except Exception as exc:
        return None, f"No normalizable: {exc}"


def _pick_filename(meta: dict[str, Any], url: str, index: int) -> str:
    tool = meta.get("tooltip") or ""
    tit = meta.get("titulo") or ""
    base = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
    cand = tool or tit or base
    ext = ""
    m = re.search(r"\.([a-zA-Z0-9]{1,12})$", base)
    if m:
        ext = "." + m.group(1).lower()
    stem = Path(cand).stem if cand else ""
    slug = _safe_slug(stem) + ext
    if len(slug) <= len(ext) or slug.strip("_") == ext.lstrip("."):
        slug = f"doc_{index:03d}{ext or '.bin'}"
    return f"{index:03d}_{slug}"


def _http_get_bytes(
    url: str,
    *,
    timeout: float = 90.0,
    retries: int = 3,
) -> tuple[int, bytes, str | None]:
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ct = resp.headers.get("Content-Type")
                return int(resp.status), resp.read(), ct
        except urllib.error.HTTPError as e:
            return int(e.code), e.read(), e.headers.get("Content-Type") if e.headers else None
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < retries:
                time.sleep(min(2.0 * (attempt + 1), 10.0))
                continue
            return 0, b"", None
        except (http.client.InvalidURL, ValueError, UnicodeEncodeError):
            return 0, b"", None
    return 0, b"", None


def download_one(
    url: str,
    dest: Path,
    *,
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    normalized, norm_err = normalize_nti_download_url(url)
    if not normalized:
        return {
            "ok": False,
            "httpStatus": None,
            "sha256": None,
            "bytes": None,
            "contentType": None,
            "savedPath": None,
            "error": norm_err or "URL inválida",
        }
    parsed = urllib.parse.urlparse(normalized)
    if not _host_allowed(parsed):
        return {
            "ok": False,
            "httpStatus": None,
            "sha256": None,
            "bytes": None,
            "contentType": None,
            "savedPath": None,
            "error": "host no permitido",
        }

    url = normalized
    last_err: str | None = None
    code = 0
    for attempt in range(retries + 1):
        code, body, ct = _http_get_bytes(url, timeout=timeout, retries=retries)
        ok = code == 200 and body is not None
        h = hashlib.sha256(body or b"").hexdigest()
        if ok:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
            return {
                "ok": True,
                "httpStatus": code,
                "sha256": h,
                "bytes": len(body),
                "contentType": ct,
                "savedPath": str(dest.relative_to(OUTPUT_DIR)),
            }
        last_err = f"HTTP {code}, len(body)={len(body or b'')}"
        if attempt < retries:
            time.sleep(0.6 * (attempt + 1))
    return {
        "ok": False,
        "httpStatus": code or None,
        "sha256": None,
        "bytes": None,
        "contentType": None,
        "savedPath": None,
        "error": last_err,
    }


def run(
    *,
    visor_json: Path,
    limit_expedientes: int,
    max_files_per_exp: int,
    expedientes_extra: list[str],
    delay_s: float,
    timeout: float,
    retries: int,
    skip_existing: bool,
    all_with_nti: bool,
    since_year: int | None,
) -> dict[str, Any]:
    if not visor_json.is_file():
        raise SystemExit(f"No existe {visor_json}: ejecuta primero madrid_viso_fetch")

    bundle = json.loads(visor_json.read_text(encoding="utf-8"))
    by_g: dict[str, Any] = bundle.get("byGrupoExpediente") or {}

    pairs: list[tuple[str, dict[str, Any]]] = list(by_g.items())
    pairs.sort(key=lambda x: x[0])

    # Priorizar expedientes solicitados por flag
    want = {norm_grupo_clave(x) for x in expedientes_extra}
    if want:
        selected: list[tuple[str, dict[str, Any]]] = []
        for g, rec in pairs:
            if g in want or norm_grupo_clave(g) in want:
                selected.append((g, rec))
        pairs = selected
    elif limit_expedientes > 0:
        filtered: list[tuple[str, dict[str, Any]]] = []
        for g, rec in pairs:
            if nti_documents_from_record(rec):
                filtered.append((g, rec))
            if len(filtered) >= limit_expedientes:
                break
        pairs = filtered

    if all_with_nti:
        pairs = [(g, rec) for g, rec in pairs if nti_documents_from_record(rec)]

    if since_year is not None:
        before = len(pairs)
        pairs = [(g, rec) for g, rec in pairs if expediente_is_recent(rec, g, since_year=since_year)]
        print(
            f"Filtro expediente >= {since_year}: {len(pairs)}/{before} expedientes",
            flush=True,
        )

    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, Any] = {}
    total_ok = total_skip = total_err = total_docs_skip = 0
    print(f"Expedientes a procesar: {len(pairs)}", flush=True)

    for g, rec in pairs:
        docs = nti_documents_from_record(rec)
        if since_year is not None:
            raw_n = len(docs)
            docs = filter_nti_documents(docs, rec, g, since_year=since_year)
            total_docs_skip += raw_n - len(docs)
        if not docs:
            continue

        slug_dir = DOWNLOAD_ROOT / _norm_exp(g)
        manifest_path = slug_dir / "manifest.json"
        slice_docs = docs if max_files_per_exp <= 0 else docs[:max_files_per_exp]

        downloads: list[dict[str, Any]] = []
        for i, meta in enumerate(slice_docs):
            url = (meta.get("url") or "").strip()
            if not url:
                downloads.append({"index": i, "url": None, "result": {"ok": False, "error": "sin URL"}})
                total_err += 1
                continue
            parsed = urllib.parse.urlparse(url)
            if not _host_allowed(parsed):
                downloads.append(
                    {"index": i, "url": url, "result": {"ok": False, "error": "host no permitido"}}
                )
                total_err += 1
                continue

            fname = _pick_filename(meta, url, i)
            dest = slug_dir / "files" / fname
            if skip_existing and dest.is_file() and dest.stat().st_size > 0:
                downloads.append(
                    {
                        "index": i,
                        "meta": meta,
                        "url": url,
                        "result": {"ok": True, "skipped": True, "savedPath": str(dest.relative_to(OUTPUT_DIR))},
                    }
                )
                total_skip += 1
                continue
            if delay_s > 0:
                time.sleep(delay_s)
            res = download_one(url, dest, timeout=timeout, retries=retries)
            downloads.append({"index": i, "meta": meta, "url": url, "result": res})
            if res.get("ok"):
                total_ok += 1
            else:
                total_err += 1

        manifest = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "expedienteGrupo": g,
            "visorUrlUsada": rec.get("visorUrlUsada"),
            "ntiListadoUrl": rec.get("ntiListadoUrl"),
            "documentosEnJson": len(docs),
            "maxFilesEsteRun": max_files_per_exp,
            "descargas": downloads,
        }
        slug_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        ok_n = sum(1 for d in downloads if d.get("result", {}).get("ok"))
        summaries[g] = {"manifest": str(manifest_path.relative_to(OUTPUT_DIR)), "ok": ok_n, "intentos": len(downloads)}
        print(f"  {g}: {ok_n}/{len(downloads)} ok", flush=True)

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "visorJson": str(visor_json),
        "downloadRoot": str(DOWNLOAD_ROOT.relative_to(OUTPUT_DIR)),
        "expedientesProcesados": list(summaries.keys()),
        "resumen": summaries,
        "sinceYear": since_year,
        "totales": {
            "ok": total_ok,
            "skipped": total_skip,
            "error": total_err,
            "docsOmitidosPorFecha": total_docs_skip,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Descarga documentos NTI (lista en madrid_viso_expedientes.json).")
    ap.add_argument("--visor-json", type=Path, default=VISOR_JSON)
    ap.add_argument(
        "--limit-expedientes",
        type=int,
        default=0,
        help="Máximo de expedientes con NTI que procesar (0 = sólo si se usa --exp).",
    )
    ap.add_argument(
        "--max-files",
        type=int,
        default=5,
        help="Máx. ficheros por expediente (0 = todos; con --all el default es 0).",
    )
    ap.add_argument("--exp", nargs="*", default=[], help="Expediente(s) grupo, ej: 135/2021/00618")
    ap.add_argument(
        "--all",
        action="store_true",
        help="Todos los expedientes con ntiArbol; descarga todos los ficheros (max-files=0).",
    )
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="No volver a bajar si el fichero local ya existe.",
    )
    ap.add_argument(
        "--since-year",
        type=int,
        default=0,
        help="Solo expedientes/documents desde este año (0=sin filtro). Ej: 2020",
    )
    ap.add_argument("--delay", type=float, default=0.35)
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args()

    extra = list(args.exp)
    lim = args.limit_expedientes
    max_files = args.max_files
    if args.all:
        lim = 0
        max_files = 0
    elif lim <= 0 and not extra:
        lim = 2

    since_year = args.since_year if args.since_year > 0 else None

    report = run(
        visor_json=args.visor_json,
        limit_expedientes=lim if not extra else 0,
        max_files_per_exp=max_files,
        expedientes_extra=extra,
        delay_s=args.delay,
        timeout=args.timeout,
        retries=max(0, args.retries),
        skip_existing=args.skip_existing,
        all_with_nti=bool(args.all),
        since_year=since_year,
    )
    out_summary = OUTPUT_DIR / "madrid_nti_downloads_run.json"
    out_summary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
