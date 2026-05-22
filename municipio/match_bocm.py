from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from municipio.manifest import POC_ROOT, MunicipioManifest, municipio_matches

BOCM_CSV = POC_ROOT / "output" / "history_parsed_incremental.csv"
PROJECTS_JSON = POC_ROOT / "web" / "public" / "data" / "projects.json"

STOPWORDS = frozenset(
    """
    de la el en y del los las un una para por con al ayuntamiento urbanismo
    mostoles getafe pozuelo alarcon municipio ayto boletin oficial
    """.split()
)

# Tokens demasiado frecuentes en avisos BOCM/ayto — no discriminan bien.
WEAK_TOKENS = frozenset(
    """
    informacion publica aprobacion inicial definitiva expediente urbanistico
    gerencia municipal ordenacion pormenorizada documentacion grafica
    """.split()
)

RE_CODE = re.compile(
    r"\b(?:AOS|APR|PE|API|PGOU|UZ)[\s.-]*[\d]+(?:[./-][\d\w]+)*\b",
    re.I,
)
RE_EXP_P = re.compile(r"\bP\d{1,2}-\d{4}\b", re.I)
RE_EXP_AP = re.compile(r"\bAP\s*\d+/\d{4}\b", re.I)
RE_YEAR = re.compile(r"^(\d{4})")


def _norm(s: str) -> str:
    t = unicodedata.normalize("NFD", str(s or ""))
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", t).strip()


def _tokens(s: str, min_len: int = 3) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z0-9]+", _norm(s))
        if len(w) >= min_len and w not in STOPWORDS
    }


def _extract_codes(s: str) -> set[str]:
    found = set()
    for pat in (RE_CODE, RE_EXP_P, RE_EXP_AP):
        for m in pat.finditer(s or ""):
            found.add(re.sub(r"\s+", " ", m.group(0).upper()))
    return found


def _year(val: Any) -> int | None:
    m = RE_YEAR.match(str(val or "").strip())
    return int(m.group(1)) if m else None


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val or "").strip().lower() in ("1", "true", "yes", "sí", "si")


@dataclass
class BocmProject:
    id: str
    municipio: str
    title: str
    resumen: str
    nombre_sector: str
    tipo: str
    fecha: str
    bocm_date: str
    art_num: str
    pdf_url: str
    es_relevante: bool
    raw: dict[str, Any] = field(repr=False)

    @property
    def text(self) -> str:
        return " ".join(
            x for x in (self.title, self.resumen, self.nombre_sector, self.tipo) if x
        )


@dataclass
class MatchCandidate:
    ayto_id: str
    bocm_id: str
    score: float
    method: str
    shared: list[str]
    ayto_titulo: str
    bocm_title: str


def _bocm_id_from_row(row: dict[str, Any]) -> str:
    rid = str(row.get("id") or "").strip()
    if rid:
        return rid
    bocm_date = row.get("bocm_date") or row.get("bocmDate") or ""
    art_num = str(row.get("art_num") or row.get("artNum") or "")
    fp = str(row.get("proyecto_fingerprint") or row.get("fp") or "")[:12]
    return f"bocm-{bocm_date}-{art_num}-{fp or 'na'}"


def _row_to_bocm(row: dict[str, Any]) -> BocmProject:
    title = str(row.get("title") or row.get("titulo") or "").strip()
    resumen = str(row.get("resumen") or row.get("summary") or "").strip()
    return BocmProject(
        id=_bocm_id_from_row(row),
        municipio=str(row.get("municipio") or row.get("municipality") or ""),
        title=title,
        resumen=resumen,
        nombre_sector=str(row.get("nombre_sector") or row.get("nombreSector") or ""),
        tipo=str(row.get("tipo_instrumento") or row.get("tipoInstrumento") or ""),
        fecha=str(row.get("fecha_acuerdo") or row.get("fechaAcuerdo") or ""),
        bocm_date=str(row.get("bocm_date") or row.get("bocmDate") or ""),
        art_num=str(row.get("art_num") or row.get("artNum") or ""),
        pdf_url=str(row.get("pdf_url") or row.get("pdfUrl") or ""),
        es_relevante=(
            _truthy(row["es_relevante"])
            if row.get("es_relevante") not in (None, "")
            else _truthy(row.get("esRelevante", True))
        ),
        raw=row,
    )


def load_bocm_projects(manifest: MunicipioManifest, relevant_only: bool = True) -> list[BocmProject]:
    aliases = manifest.proyectos.municipio_aliases
    rows: list[dict[str, Any]] = []
    if BOCM_CSV.is_file():
        with BOCM_CSV.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    elif PROJECTS_JSON.is_file():
        with PROJECTS_JSON.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            rows = data
    else:
        raise FileNotFoundError(f"Sin fuente BOCM: {BOCM_CSV} ni {PROJECTS_JSON}")

    out: list[BocmProject] = []
    for row in rows:
        municipio = row.get("municipio") or row.get("municipality")
        if not municipio_matches(municipio, aliases):
            continue
        rec = _row_to_bocm(row)
        if relevant_only and not rec.es_relevante:
            continue
        out.append(rec)
    return out


def load_ayto_proyectos(manifest: MunicipioManifest) -> list[dict[str, Any]]:
    path = manifest.output_dir / "proyectos.jsonl"
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return [r for r in rows if str(r.get("source") or "") == "ayuntamiento"]


def _ayto_text(ayto: dict[str, Any]) -> str:
    parts = [
        ayto.get("titulo") or "",
        ayto.get("expte") or "",
        ayto.get("tipo") or "",
        str(ayto.get("url") or "").rsplit("/", 1)[-1].replace("-", " "),
    ]
    if ayto.get("slug"):
        parts.append(str(ayto["slug"]).replace("-", " "))
    return " ".join(p for p in parts if p)


def score_pair(ayto: dict[str, Any], bocm: BocmProject) -> tuple[float, str, list[str]]:
    at = _ayto_text(ayto)
    bt = bocm.text
    ca, cb = _extract_codes(at), _extract_codes(bt)
    if ca & cb:
        return 0.92, "code", sorted(ca & cb)

    ta, tb = _tokens(at), _tokens(bt)
    if not ta or not tb:
        return 0.0, "none", []

    inter = ta & tb
    strong = {w for w in inter if w not in WEAK_TOKENS}
    if not strong:
        return 0.0, "none", []

    union = ta | tb
    jaccard = len(strong) / len(union)
    long_shared = [w for w in strong if len(w) >= 6]
    bonus = min(0.22, len(long_shared) * 0.08)
    score = jaccard + bonus

    ya = _year(ayto.get("fecha"))
    yb = _year(bocm.bocm_date or bocm.fecha)
    if ya and yb and abs(ya - yb) > 8:
        score *= 0.65
    elif ya and yb and abs(ya - yb) > 4:
        score *= 0.85

    tipo_a = _norm(str(ayto.get("tipo") or ""))
    tipo_b = _norm(bocm.tipo)
    if tipo_a and tipo_b and (tipo_a in tipo_b or tipo_b in tipo_a):
        score += 0.05

    return min(score, 0.89), "tokens", sorted(strong)[:12]


def match_proyectos(
    manifest: MunicipioManifest,
    *,
    min_score: float = 0.35,
    mutual_best: bool = True,
    relevant_only: bool = True,
) -> dict[str, Any]:
    ayto_rows = load_ayto_proyectos(manifest)
    bocm_rows = load_bocm_projects(manifest, relevant_only=relevant_only)

    if not ayto_rows:
        return {
            "slug": manifest.slug,
            "error": "sin proyectos.jsonl del ayuntamiento",
            "ayto_count": 0,
            "bocm_count": len(bocm_rows),
            "matches": [],
        }
    if not bocm_rows:
        return {
            "slug": manifest.slug,
            "error": "sin proyectos BOCM para el municipio",
            "ayto_count": len(ayto_rows),
            "bocm_count": 0,
            "matches": [],
        }

    # Best BOCM per ayto
    ayto_best: dict[str, MatchCandidate] = {}
    for ayto in ayto_rows:
        aid = str(ayto.get("id") or "")
        if not aid:
            continue
        best_score = 0.0
        best: MatchCandidate | None = None
        for bocm in bocm_rows:
            sc, method, shared = score_pair(ayto, bocm)
            if sc > best_score:
                best_score = sc
                best = MatchCandidate(
                    ayto_id=aid,
                    bocm_id=bocm.id,
                    score=round(sc, 4),
                    method=method,
                    shared=shared,
                    ayto_titulo=str(ayto.get("titulo") or "")[:500],
                    bocm_title=bocm.title[:500] or bocm.resumen[:200],
                )
        if best and best.score >= min_score:
            ayto_best[aid] = best

    # Best ayto per BOCM (for mutual filter)
    bocm_best: dict[str, str] = {}
    for bocm in bocm_rows:
        best_score = 0.0
        best_aid = ""
        for ayto in ayto_rows:
            aid = str(ayto.get("id") or "")
            sc, _, _ = score_pair(ayto, bocm)
            if sc > best_score:
                best_score = sc
                best_aid = aid
        if best_aid and best_score >= min_score:
            bocm_best[bocm.id] = best_aid

    matches: list[dict[str, Any]] = []
    for aid, cand in ayto_best.items():
        if mutual_best and bocm_best.get(cand.bocm_id) not in (None, aid):
            continue
        bocm = next((b for b in bocm_rows if b.id == cand.bocm_id), None)
        matches.append(
            {
                "ayto_id": cand.ayto_id,
                "bocm_id": cand.bocm_id,
                "score": cand.score,
                "method": cand.method,
                "shared": cand.shared,
                "ayto_titulo": cand.ayto_titulo,
                "bocm_title": cand.bocm_title,
                "bocm_resumen": (bocm.resumen[:400] if bocm else ""),
                "bocm_tipo": bocm.tipo if bocm else "",
                "bocm_fecha": bocm.bocm_date if bocm else "",
                "bocm_pdf_url": bocm.pdf_url if bocm else "",
                "ayto_url": next((a.get("url") for a in ayto_rows if a.get("id") == aid), ""),
            }
        )

    matched_bocm_ids = {m["bocm_id"] for m in matches}
    unmatched_ayto = [a for a in ayto_rows if a.get("id") not in {m["ayto_id"] for m in matches}]

    return {
        "slug": manifest.slug,
        "nombre": manifest.nombre,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_score": min_score,
        "mutual_best": mutual_best,
        "ayto_count": len(ayto_rows),
        "bocm_count": len(bocm_rows),
        "matched_count": len(matches),
        "ayto_match_rate": round(len(matches) / len(ayto_rows), 4) if ayto_rows else 0,
        "bocm_match_rate": round(len(matched_bocm_ids) / len(bocm_rows), 4) if bocm_rows else 0,
        "matches": matches,
        "unmatched_ayto_sample": [
            {"id": a.get("id"), "titulo": (a.get("titulo") or "")[:200]}
            for a in unmatched_ayto[:15]
        ],
    }


def write_match_outputs(manifest: MunicipioManifest, result: dict[str, Any]) -> dict[str, str]:
    manifest.ensure_output_dir()
    out_dir = manifest.output_dir
    report_path = out_dir / "bocm-match-report.json"
    jsonl_path = out_dir / "bocm-matches.jsonl"

    matches = result.get("matches") or []
    with jsonl_path.open("w", encoding="utf-8") as f:
        for m in matches:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    summary = {k: v for k, v in result.items() if k != "matches"}
    summary["matches_path"] = str(jsonl_path)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"report": str(report_path), "matches": str(jsonl_path)}


def match_many(
    slugs: list[str],
    *,
    min_score: float = 0.35,
    mutual_best: bool = True,
) -> dict[str, Any]:
    from municipio.manifest import load_manifest

    results: dict[str, Any] = {}
    totals = {"ayto": 0, "bocm": 0, "matched": 0}
    for slug in slugs:
        manifest = load_manifest(slug)
        result = match_proyectos(manifest, min_score=min_score, mutual_best=mutual_best)
        paths = write_match_outputs(manifest, result)
        summary = {k: v for k, v in result.items() if k not in ("matches", "unmatched_ayto_sample")}
        summary["paths"] = paths
        results[slug] = summary
        totals["ayto"] += result.get("ayto_count", 0)
        totals["bocm"] += result.get("bocm_count", 0)
        totals["matched"] += result.get("matched_count", 0)

    global_path = POC_ROOT / "output" / "municipios" / "bocm-match-summary.json"
    global_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_score": min_score,
        "mutual_best": mutual_best,
        "totals": totals,
        "municipios": results,
    }
    global_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["summary_path"] = str(global_path)
    return payload
