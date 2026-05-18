#!/usr/bin/env python3
"""
Extrae ficha HTML del visor WEB Ayto. Madrid (servpub) + árbol documental NTI (cuando exista).

El índice SIGMA suele enlazar con ?figura=..., pero la misma información de tramitación
responde también con expPlaneamiento.iam?exp=D/A/N&infoPubli=true para expedientes de
planeamiento / tramitados AD.

Salida: output/madrid_viso_expedientes.json (mapa por grupo-expediente normalizado).
ntiArbol incluye lista completa en "documentos" y primeros 40 en "documentosMuestra".

Tras el fetch, poblar SQLite y descargas NTI::

  python3 db/ingest_visor_sqlite.py
  python3 db/download_nti_sqlite.py
  # o bien: python3 db/populate_sigma_assets.py --ingest --download

Uso desde poc-bocm/:
  python3 -m sector_geometry.madrid_viso_fetch                  # targets por defecto (links BOCM + índice IP)
  python3 -m sector_geometry.madrid_viso_fetch --limit 5        # prueba
  python3 -m sector_geometry.madrid_viso_fetch --skip-nti       # solo HTML visor
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sector_geometry.madrid_viso_ficha_parse import parse_visor_ficha
from sector_geometry.madrid_viso_filters import expediente_is_recent

POC_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = POC_ROOT / "output"
INDEX_PATH = OUTPUT_DIR / "madrid_ayto_expedientes_index.json"
LINKS_PATH = OUTPUT_DIR / "madrid_ayto_bocm_links.jsonl"
OUT_JSON = OUTPUT_DIR / "madrid_viso_expedientes.json"
CACHE_DIR = OUTPUT_DIR / "madrid_viso_cache"

VISOR_BASE = "https://servpub.madrid.es/VSURB_WBVISOR/seguimiento"
VISOR_PUB_BASE = "https://servpub.madrid.es"
VISOR_DOC_BASE = f"{VISOR_PUB_BASE}/VSURB_WBVISOR/documentacion"
USER_AGENT = "poc-bocm-madrid-viso-fetch/1.0 (+datos públicos Madrid; reduce carga)"

RE_DOCURL = re.compile(
    r"abrirUrl\s*\(\s*'([^']+)'\s*,\s*'Documentaci[oó]n'\s*\)",
    re.I,
)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _norm_exp(num: str) -> str:
    return re.sub(r"\s+", "", (num or "").strip())


def _grupo_expediente(num: str) -> str:
    n = _norm_exp(num)
    parts = n.split("/")
    if len(parts) == 3 and parts[2].isdigit():
        return f"{parts[0]}/{parts[1]}/{int(parts[2]):05d}"
    return n


def _normalize_sigma_url(url: str) -> str:
    u = (url or "").strip()
    u = u.replace("https://www-s.madrid.es", "https://servpub.madrid.es")
    u = u.replace("http://www-s.madrid.es", "https://servpub.madrid.es")
    return u


def visor_candidates(
    grupo: str,
    *,
    layer_kind: str | None,
    enlace_sigma: str | None,
) -> list[str]:
    """Orden sugerido de URLs a probar hasta obtener ficha."""

    qs_ip = urllib.parse.urlencode({"exp": grupo, "infoPubli": "true"})
    lk = (_fold(layer_kind or ""),)

    def planeamiento() -> str:
        return f"{VISOR_BASE}/expPlaneamiento.iam?{qs_ip}"

    def gestion() -> str:
        return f"{VISOR_BASE}/expGestion.iam?{qs_ip}"

    cand: list[str] = []
    enl = _normalize_sigma_url(enlace_sigma or "")
    if enl and "exp=" in enl and "servpub.madrid.es" in enl:
        if "infoPubli" not in enl:
            sep = "&" if "?" in enl else "?"
            if "?" in enl and not enl.endswith(("?", "&")):
                enl = f"{enl}{sep}infoPubli=true"
            elif "?" not in enl:
                enl = f"{enl}?infoPubli=true"
        cand.append(enl)

    if "gestion" in lk:
        cand.extend([gestion(), planeamiento()])
    else:
        cand.extend([planeamiento(), gestion()])

    # sin duplicados
    seen: set[str] = set()
    out: list[str] = []
    for c in cand:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _http_get(
    url: str,
    *,
    timeout: float = 45.0,
    retries: int = 4,
) -> tuple[int, bytes]:
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return int(resp.status), resp.read()
        except urllib.error.HTTPError as e:
            return int(e.code), e.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < retries:
                time.sleep(min(2.0 * (attempt + 1), 12.0))
                continue
            return 0, b""
    return 0, b""


def _strip_jsonp(body: str) -> str:
    body = body.strip()
    body = re.sub(r"^\s*[a-zA-Z_]\w*\s*\(\s*", "", body)
    if body.endswith(");"):
        body = body[:-2].rstrip()
    elif body.endswith(")"):
        body = body[:-1].rstrip()
    return body.strip()


def _html_text(s: str) -> str:
    s = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_module.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_visor(html: bytes) -> dict[str, Any]:
    text = html.decode("utf-8", errors="replace")
    tnorm = html_module.unescape(_fold(text))

    out: dict[str, Any] = {
        "sinDatosVisor": "no se han encontrado datos" in tnorm,
        "tramitacion": [],
        "documentacionUrls": [],
    }

    m = RE_DOCURL.findall(text)
    out["documentacionUrls"] = list(
        dict.fromkeys(absolutize_documentacion_url(u) for u in m if u)
    )

    hc = html_module.unescape(text)
    if "wbvisor_cabecera" in hc:
        mh = re.search(
            r'<div[^>]*class="wbvisor_cabecera"[^>]*>(.*?)</div>\s*<div',
            hc,
            re.DOTALL | re.I,
        )
        if mh:
            hblock = mh.group(1)
            h1 = re.search(r"<h1[^>]*>(.*?)</h1>", hblock, re.DOTALL | re.I)
            h2 = re.search(r"<h2[^>]*>(.*?)</h2>", hblock, re.DOTALL | re.I)
            out["visorCabecera"] = {
                "h1": _html_text(h1.group(1)) if h1 else None,
                "h2": _html_text(h2.group(1)) if h2 else None,
            }

    ti = hc.upper().find("TRAMITACI")
    if ti >= 0 and not out["sinDatosVisor"]:
        tail = hc[ti:]
        mm = re.search(
            r'<div[^>]*style="[^"]*overflow:\s*auto[^"]*max-height:\s*60px[^"]*"[^>]*>\s*<table[^>]*>([\s\S]*?)</table>',
            tail,
            re.I,
        )
        if mm:
            inner = mm.group(1)
            for tr in re.finditer(r"<tr[^>]*>([\s\S]*?)</tr>", inner, re.I):
                tds = re.findall(r"<td[^>]*>([\s\S]*?)</td>", tr.group(1), re.I)
                if len(tds) < 3:
                    continue
                fecha = _html_text(tds[0])
                tramite = _html_text(tds[1])
                organo = _html_text(tds[2])
                if _fold(fecha) == "fecha" and _fold(tramite).startswith("tram"):
                    continue
                if not fecha and not tramite:
                    continue
                out["tramitacion"].append(
                    {"fecha": fecha or None, "tramite": tramite or None, "organo": organo or None}
                )

    ficha = parse_visor_ficha(hc)
    if ficha:
        out["visorFicha"] = ficha

    return out


def absolutize_documentacion_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return VISOR_PUB_BASE + u
    return u


def pick_listado_for_nti(urls: list[str]) -> tuple[str, str] | None:
    """Devuelve ('htm'|'iam', url_absoluta) priorizando listado.htm sobre listado.iam."""
    abs_urls = [absolutize_documentacion_url(u) for u in urls if u]
    for u in abs_urls:
        if "listado.htm" in u:
            return ("htm", u)
    for u in abs_urls:
        if "listado.iam" in u.lower():
            return ("iam", u)
    return None


def extract_listado_iam_id(listado_url: str) -> str | None:
    au = absolutize_documentacion_url(listado_url)
    parsed = urllib.parse.urlparse(au)
    if "listado.iam" not in parsed.path.lower():
        return None
    ids = urllib.parse.parse_qs(parsed.query).get("id") or []
    return (ids[0] or "").strip() or None


def _flatten_iam_ambito(ambito: dict[str, Any], prefix: list[str]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    nombre = (ambito.get("nombreAmbito") or "").strip()
    path = prefix + ([nombre] if nombre else [])

    documentos = ambito.get("documentos")
    if not isinstance(documentos, dict):
        return docs

    for arch in documentos.get("archivos") or []:
        if not isinstance(arch, dict):
            continue
        id_doc = (arch.get("idDocumentum") or "").strip()
        nombre_doc = (arch.get("nombreDocumento") or "documento.pdf").strip()
        if not id_doc:
            continue
        q = urllib.parse.urlencode({"id": id_doc, "nombre": nombre_doc})
        url = f"{VISOR_DOC_BASE}/verdocumento.iam?{q}"
        docs.append(
            {
                "rutaCarpetas": " / ".join(p for p in path if p),
                "titulo": nombre_doc,
                "tooltip": nombre_doc,
                "url": url,
                "idDocumentum": id_doc,
                "listadoKind": "iam",
            }
        )

    for sub in documentos.get("ambitos") or []:
        if isinstance(sub, dict):
            docs.extend(_flatten_iam_ambito(sub, path))

    return docs


def fetch_iam_document_list(listado_iam_url: str) -> list[dict[str, Any]]:
    """Lista documentos vía listaDocumentos.iam (visor gestión/urbanización)."""
    pid = extract_listado_iam_id(listado_iam_url)
    if not pid:
        return []
    api = f"{VISOR_DOC_BASE}/listaDocumentos.iam?id={urllib.parse.quote(pid)}"
    code, body = _http_get(api, timeout=120.0, retries=5)
    if code != 200 or not body:
        return []
    raw = body.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    docs: list[dict[str, Any]] = []
    for amb in data.get("ambitos") or []:
        if isinstance(amb, dict):
            docs.extend(_flatten_iam_ambito(amb, []))
    return docs


def attach_nti_to_record(record: dict[str, Any], *, delay_s: float) -> bool:
    """Rellena ntiArbol / ntiListadoUrl si hay listado. Devuelve True si hay árbol nuevo."""
    if record.get("ntiArbol"):
        return False
    urls = record.get("documentacionUrls") or []
    picked = pick_listado_for_nti(urls)
    if not picked:
        return False
    kind, listado = picked
    record["ntiListadoUrl"] = listado
    record["ntiListadoKind"] = kind
    try:
        if delay_s > 0:
            time.sleep(delay_s)
        if kind == "htm":
            tree = fetch_nti_tree_json(listado)
            summ = nti_resumen(tree, listado)
            if summ:
                record["ntiArbol"] = summ
                record["ntiArbolTituloRaiz"] = (tree or {}).get("title")
                return True
        elif kind == "iam":
            docs = fetch_iam_document_list(listado)
            if docs:
                record["ntiArbol"] = {
                    "documentosTotal": len(docs),
                    "documentos": docs,
                    "documentosMuestra": docs[:40],
                }
                return True
    except Exception as exc:
        record["ntiFetchError"] = str(exc)[:500]
    return False


def _nti_listado_to_json_url(listado_url: str) -> str | None:
    if "listado.htm" not in listado_url:
        return None
    base = listado_url.rsplit("/", 1)[0]
    return f"{base}/contenido_no_modificable/puesta_disposicion.json"


def fetch_nti_tree_json(listado_url: str) -> dict[str, Any] | None:
    json_url = _nti_listado_to_json_url(listado_url)
    if not json_url:
        return None
    code, body = _http_get(json_url, timeout=60.0)
    if code != 200:
        return None
    raw = body.decode("utf-8", errors="replace").strip()
    if not raw.startswith("jsonCallback(") and not raw.lstrip().startswith("{"):
        return None
    try:
        return json.loads(_strip_jsonp(raw))
    except json.JSONDecodeError:
        return None


def _flatten_nti(
    node: dict[str, Any],
    *,
    prefix: list[str],
    acc: list[dict[str, Any]],
    listado_base: str,
) -> None:
    title = (node.get("title") or "").strip()
    path = prefix + ([title] if title else [])

    if node.get("folder") and node.get("children"):
        for ch in node["children"]:
            if isinstance(ch, dict):
                _flatten_nti(ch, prefix=path, acc=acc, listado_base=listado_base)
        return

    href = (node.get("href") or "").strip()
    if not href:
        return
    abs_url = urllib.parse.urljoin(listado_base + "/", href)
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    nti = data.get("nti") if isinstance(data.get("nti"), dict) else {}
    acc.append(
        {
            "rutaCarpetas": " / ".join([p for p in path if p]),
            "titulo": title or None,
            "tooltip": (node.get("tooltip") or "").strip() or None,
            "url": abs_url,
            "fechaCreacion": (data.get("fechaCreacion") or "").strip() or None,
            "tipodocNti": (nti.get("tipodocNti") or "").strip() or None,
            "fechaDocumento": (nti.get("fecha_documento") or "").strip() or None,
        }
    )


def nti_resumen(tree: dict[str, Any] | None, listado_url: str) -> dict[str, Any] | None:
    if not tree:
        return None
    docs: list[dict[str, Any]] = []
    base = listado_url.rsplit("/", 1)[0]
    _flatten_nti(tree, prefix=[], acc=docs, listado_base=base)
    return {
        "documentosTotal": len(docs),
        "documentos": docs,
        "documentosMuestra": docs[:40],
    }


@dataclass
class Target:
    grupo: str
    layer_kind: str | None = None
    enlace_sigma: str | None = None


def load_index_bundle() -> dict[str, dict[str, Any]]:
    if not INDEX_PATH.is_file():
        return {}
    raw = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    by_grupo: dict[str, dict[str, Any]] = {}
    for row in raw.get("expedientes") or []:
        num = row.get("EXP_TX_NUMERO")
        if not num:
            continue
        g = _grupo_expediente(str(num))
        by_grupo[g] = {
            "sigma_layer_kind": row.get("sigma_layer_kind"),
            "Enlace": row.get("Enlace"),
        }
    return by_grupo


def load_link_targets() -> list[Target]:
    if not LINKS_PATH.is_file():
        return []
    out: list[Target] = []
    seen: set[str] = set()
    for line in LINKS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        exp = rec.get("sigma_expediente")
        if not exp:
            continue
        g = _grupo_expediente(str(exp))
        if g in seen:
            continue
        seen.add(g)
        out.append(
            Target(
                grupo=g,
                layer_kind=None,
                enlace_sigma=rec.get("sigma_enlace"),
            )
        )
    return out


def merge_metadata(t: Target, index_by_grupo: dict[str, dict[str, Any]]) -> Target:
    hit = index_by_grupo.get(t.grupo)
    if not hit:
        return t
    return Target(
        grupo=t.grupo,
        layer_kind=hit.get("sigma_layer_kind") or t.layer_kind,
        enlace_sigma=hit.get("Enlace") or t.enlace_sigma,
    )


def _save_viso_bundle(bundle: dict[str, Any], by_g: dict[str, Any]) -> None:
    bundle["generatedAt"] = datetime.now(timezone.utc).isoformat()
    bundle["conNtiArbol"] = sum(1 for v in by_g.values() if v.get("ntiArbol"))
    bundle["conVisorFicha"] = sum(1 for v in by_g.values() if v.get("visorFicha"))
    bundle["byGrupoExpediente"] = by_g
    OUT_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")


def _best_cached_html(grupo: str) -> bytes | None:
    cache_key = grupo.replace("/", "_")
    files = sorted(
        CACHE_DIR.glob(f"{cache_key}_*.html"),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    for path in files:
        body = path.read_bytes()
        if body and b"wbvisor" in body.lower():
            return body
    return None


def _fetch_and_cache_html(
    grupo: str,
    *,
    layer_kind: str | None,
    enlace_sigma: str | None,
    delay_s: float,
) -> bytes | None:
    cache_key = grupo.replace("/", "_")
    urls = visor_candidates(grupo, layer_kind=layer_kind, enlace_sigma=enlace_sigma)
    for url in urls:
        cfile = CACHE_DIR / f"{cache_key}_{hash(url) & 0xFFFF}.html"
        if cfile.is_file():
            body = cfile.read_bytes()
        else:
            time.sleep(delay_s)
            code, body = _http_get(url)
            if code == 200 and body:
                cfile.write_bytes(body)
        if not body or parse_visor(body).get("sinDatosVisor"):
            continue
        return body
    return None


def run_enrich_ficha_from_cache(
    *,
    limit: int = 0,
    delay_s: float = 0.0,
    fetch_missing: bool = False,
    checkpoint_every: int = 200,
    since_year: int | None = None,
) -> dict[str, Any]:
    """
    Rellena visorFicha en madrid_viso_expedientes.json desde HTML en madrid_viso_cache/.
    Con --fetch-missing descarga fichas sin caché local.
    """
    if not OUT_JSON.is_file():
        raise SystemExit(f"No existe {OUT_JSON}; ejecuta madrid_viso_fetch antes.")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    bundle = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    by_g: dict[str, Any] = dict(bundle.get("byGrupoExpediente") or {})
    index_by_grupo = load_index_bundle()

    keys = sorted(set(by_g.keys()) | set(index_by_grupo.keys()))
    if since_year is not None:
        keys = [
            g
            for g in keys
            if expediente_is_recent(by_g.get(g) or {}, g, since_year=since_year)
        ]
    if limit > 0:
        keys = keys[:limit]

    enriched = fetched = skipped = 0
    for i, grupo in enumerate(keys):
        rec = by_g.setdefault(grupo, {"expedienteGrupo": grupo})
        body = _best_cached_html(grupo)
        if not body and fetch_missing:
            meta = index_by_grupo.get(grupo) or {}
            body = _fetch_and_cache_html(
                grupo,
                layer_kind=meta.get("sigma_layer_kind") if isinstance(meta, dict) else rec.get("sigmaLayerKind"),
                enlace_sigma=(meta.get("Enlace") if isinstance(meta, dict) else None) or rec.get("visorUrlUsada"),
                delay_s=delay_s,
            )
            if body:
                fetched += 1
                parsed = parse_visor(body)
                if parsed.get("tramitacion") and not rec.get("tramitacion"):
                    rec["tramitacion"] = parsed["tramitacion"]
                if parsed.get("documentacionUrls") and not rec.get("documentacionUrls"):
                    rec["documentacionUrls"] = parsed["documentacionUrls"]
                if parsed.get("visorCabecera") and not rec.get("visorCabecera"):
                    rec["visorCabecera"] = parsed["visorCabecera"]
        if not body:
            skipped += 1
            continue
        ficha = parse_visor_ficha(body)
        if not ficha:
            skipped += 1
            continue
        rec["visorFicha"] = ficha
        enriched += 1
        if (i + 1) % 500 == 0:
            print(f"  … {i+1}/{len(keys)} ({enriched} fichas)", flush=True)
        if checkpoint_every > 0 and (i + 1) % checkpoint_every == 0:
            _save_viso_bundle(bundle, by_g)

    _save_viso_bundle(bundle, by_g)
    return {
        "mode": "enrich_ficha_from_cache",
        "procesados": len(keys),
        "visorFicha": enriched,
        "htmlDescargados": fetched,
        "sinHtml": skipped,
        "conVisorFicha": bundle["conVisorFicha"],
        "total": len(by_g),
    }


def run_refresh_nti_only(
    *,
    delay_s: float,
    limit: int,
    checkpoint_every: int = 25,
    since_year: int | None = None,
) -> dict[str, Any]:
    """Sólo rellena ntiArbol en madrid_viso_expedientes.json existente (sin reconsultar visor)."""
    if not OUT_JSON.is_file():
        raise SystemExit(f"No existe {OUT_JSON}; ejecuta madrid_viso_fetch antes.")
    bundle = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    by_g: dict[str, Any] = bundle.get("byGrupoExpediente") or {}
    pending = [(g, r) for g, r in by_g.items() if not r.get("ntiArbol")]
    pending = [
        (g, r)
        for g, r in pending
        if pick_listado_for_nti(r.get("documentacionUrls") or [])
    ]
    if since_year is not None:
        before = len(pending)
        pending = [(g, r) for g, r in pending if expediente_is_recent(r, g, since_year=since_year)]
        print(
            f"Filtro expediente >= {since_year}: {len(pending)}/{before} pendientes NTI",
            flush=True,
        )
    if limit > 0:
        pending = pending[:limit]
    added = errors = 0
    for i, (key, rec) in enumerate(pending):
        try:
            if attach_nti_to_record(rec, delay_s=delay_s):
                added += 1
                n = (rec.get("ntiArbol") or {}).get("documentosTotal") or 0
                print(f"  [{i+1}/{len(pending)}] NTI {key} ({n} docs)", flush=True)
            elif rec.get("ntiFetchError"):
                errors += 1
                print(f"  [{i+1}/{len(pending)}] error {key}: {rec['ntiFetchError'][:80]}", flush=True)
            else:
                print(f"  [{i+1}/{len(pending)}] sin árbol {key}", flush=True)
        except Exception as exc:
            errors += 1
            rec["ntiFetchError"] = str(exc)[:500]
            print(f"  [{i+1}/{len(pending)}] excepción {key}: {exc}", flush=True)
        if checkpoint_every > 0 and (i + 1) % checkpoint_every == 0:
            _save_viso_bundle(bundle, by_g)
            print(f"  … checkpoint {i+1}/{len(pending)} (NTI total {bundle['conNtiArbol']})", flush=True)
    _save_viso_bundle(bundle, by_g)
    return {
        "mode": "refresh_nti_only",
        "pendientes": len(pending),
        "ntiAnadidos": added,
        "errores": errors,
        "conNtiArbol": bundle["conNtiArbol"],
        "total": len(by_g),
    }


def run_fetch(
    *,
    limit: int,
    delay_s: float,
    skip_nti: bool,
    extra: list[str],
    all_index: bool,
    fetch_missing_index: bool,
    merge_existing: bool,
    since_year: int | None = None,
) -> dict[str, Any]:
    index_by_grupo = load_index_bundle()
    existing_by_g: dict[str, Any] = {}
    if merge_existing and OUT_JSON.is_file():
        prev = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        existing_by_g = prev.get("byGrupoExpediente") or {}
    targets = [merge_metadata(x, index_by_grupo) for x in load_link_targets()]

    # Entradas IP con exp= explícito en el índice
    for g, meta in index_by_grupo.items():
        enl = meta.get("Enlace")
        if enl and "exp=" in str(enl) and "figura=" not in str(enl).lower():
            targets.append(
                Target(
                    grupo=g,
                    layer_kind=meta.get("sigma_layer_kind"),
                    enlace_sigma=str(enl),
                )
            )

    seen_g: set[str] = set()
    uniq: list[Target] = []
    for t in targets:
        if t.grupo in seen_g:
            continue
        seen_g.add(t.grupo)
        uniq.append(merge_metadata(t, index_by_grupo))

    for raw in extra:
        g = _grupo_expediente(raw)
        if g not in seen_g:
            seen_g.add(g)
            uniq.append(merge_metadata(Target(grupo=g), index_by_grupo))

    if all_index and index_by_grupo:
        for g in sorted(index_by_grupo.keys()):
            if g in seen_g:
                continue
            meta = index_by_grupo[g]
            seen_g.add(g)
            enl = meta.get("Enlace")
            uniq.append(
                merge_metadata(
                    Target(
                        grupo=g,
                        layer_kind=meta.get("sigma_layer_kind") if isinstance(meta, dict) else None,
                        enlace_sigma=str(enl).strip() if enl else None,
                    ),
                    index_by_grupo,
                )
            )

    if fetch_missing_index and index_by_grupo:
        missing = [
            g
            for g in sorted(index_by_grupo.keys())
            if g not in existing_by_g
            and (
                since_year is None
                or expediente_is_recent({"tramitacion": []}, g, since_year=since_year)
            )
        ]
        uniq = []
        seen_g = set()
        for g in missing:
            meta = index_by_grupo[g]
            enl = meta.get("Enlace")
            uniq.append(
                merge_metadata(
                    Target(
                        grupo=g,
                        layer_kind=meta.get("sigma_layer_kind"),
                        enlace_sigma=str(enl).strip() if enl else None,
                    ),
                    index_by_grupo,
                )
            )
            seen_g.add(g)

    if limit > 0:
        uniq = uniq[:limit]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    by_grupo_out: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []

    for i, t in enumerate(uniq):
        key = t.grupo
        cache_key = key.replace("/", "_")
        urls = visor_candidates(t.grupo, layer_kind=t.layer_kind, enlace_sigma=t.enlace_sigma)
        parsed: dict[str, Any] | None = None
        used_url: str | None = None
        last_body = b""

        for url in urls:
            cfile = CACHE_DIR / f"{cache_key}_{hash(url) & 0xFFFF}.html"
            if cfile.is_file():
                last_body = cfile.read_bytes()
            else:
                time.sleep(delay_s)
                code, last_body = _http_get(url)
                if code == 200 and last_body:
                    cfile.write_bytes(last_body)
            if not last_body:
                continue
            p = parse_visor(last_body)
            if p.get("sinDatosVisor"):
                continue
            if not p.get("tramitacion") and not p.get("documentacionUrls"):
                continue
            parsed = p
            used_url = url
            break

        record: dict[str, Any] = {
            "expedienteGrupo": key,
            "visorUrlUsada": used_url,
            "visorCandidatos": urls,
            "sigmaLayerKind": t.layer_kind,
        }

        if not parsed:
            record["sinDatosVisor"] = True
            if last_body:
                tp = parse_visor(last_body)
                record["sinDatosVisor"] = tp.get("sinDatosVisor", True)
            errors.append({"expediente": key, "urls": urls})
            by_grupo_out[key] = record
            continue

        record.update(parsed)
        if not skip_nti:
            attach_nti_to_record(record, delay_s=delay_s)

        by_grupo_out[key] = record
        nti_n = (record.get("ntiArbol") or {}).get("documentosTotal") or 0
        print(
            f"  [{i+1}/{len(uniq)}] OK {key} (urls {len(record.get('documentacionUrls') or [])}, nti {nti_n})",
            flush=True,
        )

    if merge_existing and existing_by_g:
        merged = dict(existing_by_g)
        merged.update(by_grupo_out)
        by_grupo_out = merged

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "targets": len(uniq),
        "conFicha": sum(1 for v in by_grupo_out.values() if v.get("tramitacion")),
        "conNtiArbol": sum(1 for v in by_grupo_out.values() if v.get("ntiArbol")),
        "conVisorFicha": sum(1 for v in by_grupo_out.values() if v.get("visorFicha")),
        "byGrupoExpediente": by_grupo_out,
        "erroresMuestra": errors[:30],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Visor Madrid + NTI (tramitación y documentos).")
    ap.add_argument("--limit", type=int, default=0, help="Máx. expedientes (0=todos).")
    ap.add_argument("--delay", type=float, default=0.35, help="Pausa entre peticiones (s).")
    ap.add_argument("--skip-nti", action="store_true", help="No descargar JSON NTI.")
    ap.add_argument(
        "--all-index",
        action="store_true",
        help="Incluir todos los expedientes de madrid_ayto_expedientes_index.json (además de links BOCM).",
    )
    ap.add_argument("--extra", nargs="*", default=[], help="Expedientes adicionales D/A/N.")
    ap.add_argument(
        "--refresh-nti-only",
        action="store_true",
        help="Sólo rellenar ntiArbol en JSON existente (listado.htm + listado.iam).",
    )
    ap.add_argument(
        "--fetch-missing-index",
        action="store_true",
        help="Visor+NTI sólo para expedientes del índice SIGMA que no están en el JSON.",
    )
    ap.add_argument(
        "--merge-existing",
        action="store_true",
        help="Fusionar resultados con madrid_viso_expedientes.json previo (por defecto con --fetch-missing-index).",
    )
    ap.add_argument(
        "--checkpoint-every",
        type=int,
        default=25,
        help="Guardar JSON cada N expedientes en --refresh-nti-only (0=desactivar).",
    )
    ap.add_argument(
        "--since-year",
        type=int,
        default=0,
        help="Solo expedientes con año en número o trámite >= este año (0=sin filtro).",
    )
    ap.add_argument(
        "--enrich-ficha",
        action="store_true",
        help="Extraer visorFicha (promotor, resumen, m²…) desde HTML en caché o descargando.",
    )
    ap.add_argument(
        "--fetch-missing-html",
        action="store_true",
        help="Con --enrich-ficha: descargar HTML si no hay caché local.",
    )
    args = ap.parse_args()
    since_year = args.since_year if args.since_year > 0 else None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.enrich_ficha:
        bundle = run_enrich_ficha_from_cache(
            limit=args.limit,
            delay_s=args.delay,
            fetch_missing=args.fetch_missing_html,
            checkpoint_every=max(0, args.checkpoint_every),
            since_year=since_year,
        )
        print(
            f"visorFicha: {bundle.get('visorFicha')} enriquecidos "
            f"({bundle.get('conVisorFicha')}/{bundle.get('total')} total, "
            f"+{bundle.get('htmlDescargados')} HTML nuevos)",
            flush=True,
        )
        return

    if args.refresh_nti_only:
        bundle = run_refresh_nti_only(
            limit=args.limit,
            delay_s=args.delay,
            checkpoint_every=max(0, args.checkpoint_every),
            since_year=since_year,
        )
        print(
            f"NTI refresh: +{bundle.get('ntiAnadidos')} árboles "
            f"({bundle.get('conNtiArbol')}/{bundle.get('total')} total)",
            flush=True,
        )
        return

    merge = args.merge_existing or args.fetch_missing_index
    bundle = run_fetch(
        limit=args.limit,
        delay_s=args.delay,
        skip_nti=args.skip_nti,
        extra=args.extra,
        all_index=args.all_index,
        fetch_missing_index=args.fetch_missing_index,
        merge_existing=merge,
        since_year=since_year,
    )
    OUT_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Escrito {OUT_JSON} ({bundle.get('conFicha')} tramitación, "
        f"{bundle.get('conNtiArbol')} NTI / {bundle.get('targets')} targets)",
        flush=True,
    )


if __name__ == "__main__":
    main()
