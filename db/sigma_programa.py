"""Agrupa expedientes SIGMA co-territoriales en programas urbanísticos inferidos."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from geo_utils import bbox_area_m2, bbox_overlap_ratio

OVERLAP_MIN = 0.90
MAX_PROGRAMA_MIEMBROS = 12
# Por encima de ~150 ha (1,5 km²) o ~5 % del municipio: no agrupar (normativa / ámbito amplio).
MAX_AGRUPABLE_AREA_M2 = 150 * 10_000
MADRID_MUNICIPIO_AREA_M2 = 604_000_000
MAX_AGRUPABLE_FRACCION_CIUDAD = 0.05
GENERIC_AMBITO_RE = re.compile(r"^\d+(\.\d+)*\.?[A-Z]?\.?$")
PREFIX_AMBITO_RE = re.compile(
    r"^(APE|APR|API|PS|UZP|MPE|PE|PP|PR|ED|MOD|MP|ZAC|ZEP|ZEE|ZAR)\.\d",
    re.I,
)
AMBITO_FROM_TEXT_RE = re.compile(
    r"\b(APE|APR|API|PS|UZP|MPE|PE|PP|PR|ED|MOD|MP|ZAC|ZEP|ZEE|ZAR)\.\d{1,2}\.\d{1,3}(?:/[A-Z0-9-]+)?",
    re.I,
)
NORMATIVA_CIUDAD_RE = re.compile(
    r"\b("
    r"pgoum|plan general|modificacion del plan general|modificación del plan general|"
    r"normas urban[íi]sticas|nnuu|revisi[oó]n parcial del pgou|"
    r"cat[aá]logo de edificios|cat[aá]logo de parques|cubiertas verdes"
    r")\b",
    re.I,
)

ROL_ORDER = {
    "ordenacion": 0,
    "gestion": 1,
    "urbanizacion": 2,
    "proteccion": 3,
    "otro": 9,
}

TIPO_LEGAL_ROL: dict[str, str] = {
    "modificacion_pgou": "ordenacion",
    "estudio_detalle": "ordenacion",
    "plan_parcial": "ordenacion",
    "plan_especial": "ordenacion",
    "gestion_reparcelacion": "gestion",
    "proyecto_urbanizacion": "urbanizacion",
    "catalogacion_proteccion": "proteccion",
    "ajuste_administrativo": "otro",
    "otro_instrumento": "otro",
}

LAYER_ROL: dict[str, str] = {
    "informacion_publica": "ordenacion",
    "tramitados_ad": "ordenacion",
    "tramitados_gestion": "gestion",
    "tramitados_urbanizacion": "urbanizacion",
    "gestion": "gestion",
    "urbanizacion": "urbanizacion",
}


@dataclass
class ExpedienteProgramaInput:
    expediente_grupo: str
    exp_numero_original: str | None = None
    denominacion: str | None = None
    ambito_ordenacion: str | None = None
    distrito: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    area_m2: float | None = None
    tipo_legal: str | None = None
    tipo_obra: str | None = None
    categoria_proyecto: str | None = None
    sigma_layer_kind: str | None = None
    anio: int | None = None


@dataclass
class ProgramaMiembroOut:
    expediente_grupo: str
    rol: str
    orden_fase: int
    overlap_ratio: float | None = None
    denominacion: str | None = None
    anio: int | None = None


@dataclass
class ProgramaOut:
    programa_id: str
    titulo: str
    ambito_ordenacion: str | None
    distrito: str | None
    anio_inicio: int | None
    anio_fin: int | None
    confianza: str
    metodo_agrupacion: str
    expediente_lider: str
    miembros: list[ProgramaMiembroOut] = field(default_factory=list)

    @property
    def miembros_count(self) -> int:
        return len(self.miembros)


def _norm_key(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.strip().lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def norm_ambito_ordenacion(raw: str | None) -> str | None:
    if not raw:
        return None
    s = re.sub(r"\s+", " ", str(raw).strip().upper())
    if len(s) < 3 or s in {"-", "MADRID", "CIUDAD", "PGOU"}:
        return None
    if GENERIC_AMBITO_RE.match(s):
        return None
    if not PREFIX_AMBITO_RE.match(s):
        return None
    return s


def resolve_ambito_ordenacion(exp: ExpedienteProgramaInput) -> str | None:
    """Ámbito del visor o inferido desde la denominación (p. ej. APR.06.02)."""
    norm = norm_ambito_ordenacion(exp.ambito_ordenacion)
    if norm:
        return norm
    denom = exp.denominacion or ""
    match = AMBITO_FROM_TEXT_RE.search(denom)
    if not match:
        return None
    return norm_ambito_ordenacion(match.group(0))


def anio_desde_referencia(exp: ExpedienteProgramaInput) -> int | None:
    for ref in (exp.exp_numero_original, exp.expediente_grupo):
        if not ref:
            continue
        parts = ref.strip().split("/")
        if len(parts) < 2:
            continue
        try:
            y = int(parts[1])
        except ValueError:
            continue
        if 1980 <= y <= 2100:
            return y
    return exp.anio


def infer_rol(exp: ExpedienteProgramaInput) -> str:
    if exp.tipo_legal and exp.tipo_legal in TIPO_LEGAL_ROL:
        rol = TIPO_LEGAL_ROL[exp.tipo_legal]
        if rol != "otro":
            return rol
    layer = (exp.sigma_layer_kind or "").lower()
    if layer in LAYER_ROL:
        return LAYER_ROL[layer]
    if exp.tipo_obra == "urbanizacion_redes":
        return "urbanizacion"
    if exp.tipo_obra == "reparcelacion_gestion":
        return "gestion"
    if exp.categoria_proyecto == "modificacion_planeamiento_general":
        return "ordenacion"
    return "otro"


def es_normativa_ciudad(exp: ExpedienteProgramaInput) -> bool:
    if exp.categoria_proyecto == "modificacion_planeamiento_general":
        return True
    d = exp.denominacion or ""
    return bool(NORMATIVA_CIUDAD_RE.search(d))


def effective_area_m2(exp: ExpedienteProgramaInput) -> float | None:
    if exp.area_m2 is not None and exp.area_m2 > 0:
        return exp.area_m2
    if exp.bbox is not None:
        return bbox_area_m2(exp.bbox)
    return None


def es_expediente_aislado(exp: ExpedienteProgramaInput) -> bool:
    """Expedientes de ámbito municipal amplio: no entran en programas inferidos."""
    if es_normativa_ciudad(exp):
        return True
    area = effective_area_m2(exp)
    if area is None:
        return False
    if area >= MAX_AGRUPABLE_AREA_M2:
        return True
    if area >= MADRID_MUNICIPIO_AREA_M2 * MAX_AGRUPABLE_FRACCION_CIUDAD:
        return True
    return False


def roles_complementarios(miembros: list[ExpedienteProgramaInput]) -> bool:
    roles = {infer_rol(m) for m in miembros}
    roles.discard("otro")
    return len(roles) >= 2


def pick_lider(miembros: list[ExpedienteProgramaInput]) -> ExpedienteProgramaInput:
    ordenacion = [m for m in miembros if infer_rol(m) == "ordenacion"]
    pool = ordenacion or miembros
    return max(
        pool,
        key=lambda m: (
            -(m.area_m2 or 0),
            -(anio_desde_referencia(m) or 0),
            m.expediente_grupo,
        ),
    )


def titulo_programa(
    lider: ExpedienteProgramaInput,
    ambito: str | None,
    miembros: list[ExpedienteProgramaInput],
) -> str:
    if ambito:
        denom = (lider.denominacion or "").strip()
        if denom and ambito not in denom.upper():
            short = denom if len(denom) <= 72 else f"{denom[:69]}…"
            return f"{ambito} · {short}"
        return ambito
    return (lider.denominacion or lider.expediente_grupo).strip()[:96]


def slug_programa_id(
    ambito: str | None,
    metodo: str,
    miembros: list[ExpedienteProgramaInput],
) -> str:
    if ambito:
        base = f"amb-{_norm_key(ambito)}"
        if len(base) <= 72:
            return base
        h = hashlib.sha1(ambito.encode()).hexdigest()[:8]
        return f"amb-{_norm_key(ambito)[:48]}-{h}"
    lider = pick_lider(miembros)
    grupos = sorted(m.expediente_grupo for m in miembros)
    digest = hashlib.sha1("|".join(grupos).encode()).hexdigest()[:10]
    prefix = "geom" if metodo == "geom_overlap" else "prog"
    return f"{prefix}-{_norm_key(lider.expediente_grupo)[:32]}-{digest}"


def _geom_star_clusters(
    remaining: list[ExpedienteProgramaInput],
    overlap_map: dict[tuple[str, str], float],
) -> list[list[ExpedienteProgramaInput]]:
    """Agrupa por solape directo con un líder (sin cierre transitivo)."""
    used: set[str] = set()
    clusters: list[list[ExpedienteProgramaInput]] = []
    leaders = sorted(remaining, key=lambda e: (-(e.area_m2 or 0), e.expediente_grupo))

    for leader in leaders:
        if leader.expediente_grupo in used:
            continue
        members = [leader]
        for other in remaining:
            if other.expediente_grupo in used or other.expediente_grupo == leader.expediente_grupo:
                continue
            key = tuple(sorted((leader.expediente_grupo, other.expediente_grupo)))
            if overlap_map.get(key, 0) >= OVERLAP_MIN:
                members.append(other)
        if len(members) < 2 or len(members) > MAX_PROGRAMA_MIEMBROS:
            continue
        if not roles_complementarios(members):
            continue
        clusters.append(members)
        used.update(m.expediente_grupo for m in members)

    return clusters


def _build_programa(
    miembros: list[ExpedienteProgramaInput],
    metodo: str,
    ambito: str | None,
    confianza: str,
    overlap_map: dict[tuple[str, str], float],
) -> ProgramaOut | None:
    if len(miembros) < 2 or len(miembros) > MAX_PROGRAMA_MIEMBROS:
        return None
    if any(es_normativa_ciudad(m) for m in miembros) and len(miembros) > 1:
        if not ambito and not roles_complementarios(miembros):
            return None

    lider = pick_lider(miembros)
    lider_grupo = lider.expediente_grupo
    miembros_out: list[ProgramaMiembroOut] = []
    for m in sorted(miembros, key=lambda x: (ROL_ORDER.get(infer_rol(x), 9), anio_desde_referencia(x) or 9999, x.expediente_grupo)):
        rol = infer_rol(m)
        pair = tuple(sorted((lider_grupo, m.expediente_grupo)))
        overlap = overlap_map.get(pair) if pair[0] != pair[1] else 1.0
        miembros_out.append(
            ProgramaMiembroOut(
                expediente_grupo=m.expediente_grupo,
                rol=rol,
                orden_fase=ROL_ORDER.get(rol, 9),
                overlap_ratio=round(overlap, 3) if overlap is not None else None,
                denominacion=(m.denominacion or m.expediente_grupo)[:140] or None,
                anio=anio_desde_referencia(m),
            )
        )

    years = [anio_desde_referencia(m) for m in miembros]
    years = [y for y in years if y]
    anio_inicio = min(years) if years else None
    anio_fin = max(years) if years else None

    programa_id = slug_programa_id(ambito, metodo, miembros)
    return ProgramaOut(
        programa_id=programa_id,
        titulo=titulo_programa(lider, ambito, miembros),
        ambito_ordenacion=ambito,
        distrito=next((m.distrito for m in miembros if m.distrito), None),
        anio_inicio=anio_inicio,
        anio_fin=anio_fin,
        confianza=confianza,
        metodo_agrupacion=metodo,
        expediente_lider=lider_grupo,
        miembros=miembros_out,
    )


def compute_sigma_programas(expedientes: list[ExpedienteProgramaInput]) -> list[ProgramaOut]:
    """Genera clusters de programas a partir de expedientes enriquecidos."""
    agrupables = [e for e in expedientes if not es_expediente_aislado(e)]
    by_grupo = {e.expediente_grupo: e for e in agrupables}
    assigned: set[str] = set()
    programas: list[ProgramaOut] = []
    overlap_map: dict[tuple[str, str], float] = {}

    with_bbox = [e for e in agrupables if e.bbox is not None]
    for i, a in enumerate(with_bbox):
        for b in with_bbox[i + 1 :]:
            assert a.bbox and b.bbox
            ratio = bbox_overlap_ratio(a.bbox, b.bbox)
            if ratio >= OVERLAP_MIN:
                key = tuple(sorted((a.expediente_grupo, b.expediente_grupo)))
                overlap_map[key] = ratio

    # 1) Agrupación por ámbito de ordenación (visor o inferido desde denominación)
    by_ambito: dict[str, list[ExpedienteProgramaInput]] = {}
    for exp in agrupables:
        amb = resolve_ambito_ordenacion(exp)
        if not amb:
            continue
        by_ambito.setdefault(amb, []).append(exp)

    for ambito, members in sorted(by_ambito.items()):
        if len(members) < 2 or not roles_complementarios(members):
            continue
        prog = _build_programa(members, "ambito_ordenacion", ambito, "alta", overlap_map)
        if not prog:
            continue
        programas.append(prog)
        assigned.update(m.expediente_grupo for m in members)

    # 2) Solape geométrico directo con líder (sin union-find transitivo)
    remaining = [e for e in with_bbox if e.expediente_grupo not in assigned]
    for members in _geom_star_clusters(remaining, overlap_map):
        prog = _build_programa(members, "geom_overlap", None, "media", overlap_map)
        if not prog:
            continue
        programas.append(prog)
        assigned.update(m.expediente_grupo for m in members)

    # IDs únicos (colisión improbable)
    seen_ids: set[str] = set()
    unique: list[ProgramaOut] = []
    for p in programas:
        pid = p.programa_id
        n = 2
        while pid in seen_ids:
            pid = f"{p.programa_id}-{n}"
            n += 1
        seen_ids.add(pid)
        if pid != p.programa_id:
            p = ProgramaOut(
                programa_id=pid,
                titulo=p.titulo,
                ambito_ordenacion=p.ambito_ordenacion,
                distrito=p.distrito,
                anio_inicio=p.anio_inicio,
                anio_fin=p.anio_fin,
                confianza=p.confianza,
                metodo_agrupacion=p.metodo_agrupacion,
                expediente_lider=p.expediente_lider,
                miembros=p.miembros,
            )
        unique.append(p)

    return unique


def programas_to_export(programas: list[ProgramaOut]) -> dict[str, Any]:
    by_expediente: dict[str, dict[str, Any]] = {}
    by_programa: dict[str, dict[str, Any]] = {}
    for p in programas:
        by_programa[p.programa_id] = {
            "programaId": p.programa_id,
            "titulo": p.titulo,
            "ambitoOrdenacion": p.ambito_ordenacion,
            "distrito": p.distrito,
            "anioInicio": p.anio_inicio,
            "anioFin": p.anio_fin,
            "confianza": p.confianza,
            "metodoAgrupacion": p.metodo_agrupacion,
            "expedienteLider": p.expediente_lider,
            "miembrosCount": p.miembros_count,
            "miembros": [
                {
                    "expedienteGrupo": m.expediente_grupo,
                    "rol": m.rol,
                    "ordenFase": m.orden_fase,
                    "overlapRatio": m.overlap_ratio,
                    "denominacion": m.denominacion,
                    "anio": m.anio,
                }
                for m in p.miembros
            ],
        }
        for m in p.miembros:
            by_expediente[m.expediente_grupo] = {
                "programaId": p.programa_id,
                "rol": m.rol,
                "ordenFase": m.orden_fase,
            }
    return {"byExpediente": by_expediente, "byPrograma": by_programa}
