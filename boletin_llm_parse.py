"""
Extracción estructurada de anuncios de boletines oficiales (CCAA y similares) con LLM.

- Prompt parametrizable por fuente (BOCM, DOGV, BOJA, …).
- Esquema JSON enriquecido (urbanismo + economía + ayudas + procedimiento).
- Salida normalizada a columnas planas para CSV e histórico incremental.

API compatible con OpenAI (OpenAI, Ollama, vLLM, etc.).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

# Campos de planeamiento / actuación urbanística (plano para CSV)
URBANISMO_FIELD_KEYS = [
    "municipio",
    "tipo_instrumento",
    "nombre_sector",
    "estado_tramitacion",
    "fecha_acuerdo",
    "organo_aprobador",
    "num_viviendas_max",
    "fecha_fin_estimada",
    "sup_total_m2",
    "sup_edificable_m2",
    "tipo_vivienda",
    "promotor_o_propietario",
    "municipio_provincia",
    "resumen",
]

# Columnas extra (multi-tema)
EXTRA_FIELD_KEYS = [
    "categorias_tematicas",
    "economico_resumen",
    "procedimiento_expediente",
    "procedimiento_tipo",
    "importe_total_eur_estimado",
]

# Contexto enviado al LLM (segunda pasada si el cuerpo se recortó)
CONTEXT_FIELD_KEYS = [
    "chars_texto_total",
    "llm_max_context_chars",
    "texto_truncado_llm",
    "requiere_segunda_pasada",
]

FIELDS = ["es_relevante"] + URBANISMO_FIELD_KEYS + EXTRA_FIELD_KEYS + CONTEXT_FIELD_KEYS


@dataclass(frozen=True)
class BoletinContext:
    """Identidad del boletín para el prompt (genérico; BOCM es solo el default)."""

    source_id: str = "bocm"
    bulletin_name: str = "Boletín Oficial de la Comunidad de Madrid (BOCM)"
    region_hint: str = "Comunidad de Madrid, España"


DEFAULT_CONTEXT = BoletinContext()


def build_system_prompt(ctx: BoletinContext) -> str:
    return f"""Eres un experto en derecho administrativo y urbanismo en España. Analizas textos publicados en el {ctx.bulletin_name} (fuente lógica: "{ctx.source_id}").

CONTEXTO GEOGRÁFICO: {ctx.region_hint}

OBJETIVO: extraer hechos útiles sobre vivienda, suelo, planeamiento, ayudas, presupuesto o procedimientos administrativos vinculados a vivienda/urbanismo.

PASO 1 — Relevancia
- Si el documento NO trata de forma sustantiva de vivienda, urbanismo, planeamiento, licencias, rehabilitación, ayudas/subvenciones de vivienda, concertación/plazas vinculadas a política de vivienda, ni presupuesto/transferencias claras del ámbito vivienda: devuelve EXACTAMENTE:
{{"es_relevante": false}}

Excluye como no relevante: empleo público genérico, suministros ajenos, mero calendario, anuncios sin contenido sustantivo.

PASO 2 — Si es relevante
Devuelve un ÚNICO JSON con esta forma (sin markdown, sin texto fuera del JSON):

{{
  "es_relevante": true,
  "categorias_tematicas": ["<lista de etiquetas de la tabla inferior>"],
  "urbanismo": {{
    "municipio": null,
    "tipo_instrumento": null,
    "nombre_sector": null,
    "estado_tramitacion": null,
    "fecha_acuerdo": null,
    "organo_aprobador": null,
    "num_viviendas_max": null,
    "fecha_fin_estimada": null,
    "sup_total_m2": null,
    "sup_edificable_m2": null,
    "tipo_vivienda": null,
    "promotor_o_propietario": null,
    "municipio_provincia": null,
    "resumen": null
  }},
  "economico_presupuestario": {{
    "resumen": null,
    "importe_total_eur": null,
    "programas_o_partidas": null
  }},
  "ayudas_subvenciones": {{
    "convocatoria_o_bases": null,
    "expediente_destacado": null,
    "beneficiario_destacado": null,
    "importe_destacado_eur": null
  }},
  "procedimiento": {{
    "tipo_acto": null,
    "expediente": null,
    "organo_o_tribunal": null,
    "interesado_o_parte": null,
    "plazo_dias": null
  }}
}}

ETIQUETAS permitidas en categorias_tematicas (elige SOLO las que encajen; evita etiquetas irrelevantes):

- urbanismo_planeamiento — Planeamiento: PGOU/PGOU, plan parcial/especial, normas, estudios de detalle, iniciativas de sector/compensación, modificaciones que delimiten suelo o usos. NO uses esta etiqueta solo porque el documento mencione "vivienda" en otro sentido.

- licencia_obra_rehabilitacion — Licencias o autorizaciones de obra, rehabilitación edificatoria o actuaciones equivalentes sobre edificios.

- vivienda_protegida_publica — VPO, VPPL, vivienda pública/protegida, parque público de vivienda, promoción pública (cuando el acto trate de ese régimen, no solo una mención lateral).

- ayudas_subvenciones_vivienda — SOLO cuando el acto principal sea: convocatoria, bases, concesión, denegación, desistimiento, resolución de ayudas o subvenciones ligadas a vivienda (alquiler, adquisición, rehabilitación con incentivo, programas ICV, etc.) hacia beneficiarios. NO uses esta etiqueta para: transferencias de crédito presupuestario, modificaciones del presupuesto de una consejería, reordenación de partidas PEAV o "autoriza transferencia entre programas" sin convocatoria de ayudas a particulares.

- economico_presupuestario_vivienda — Transferencias de crédito, modificaciones presupuestarias, acuerdos de distribución de fondos (p. ej. PEAV), incrementos/realces de líneas presupuestarias del ámbito vivienda/habitatge/EVHA/conselleria homóloga. Si el documento es casi solo importes y programas presupuestarios, esta etiqueta es prioritaria frente a ayudas_subvenciones_vivienda.

- concertacion_residencial_social — Conciertos, plazas residenciales para mayores/dependencia vinculados a política social y vivienda (no subastas de inmuebles).

- enajenacion_patrimonio_vivienda — Subasta, enajenación, venta o aplazamiento de subasta de vivienda o inmueble del patrimonio público (organismos autónomicos, SAREB-style administrativo, etc.). Incluye anuncios de subasta pública de una vivienda.

- procedimiento_notificacion_emplazamiento — SOLO cuando el núcleo sea: emplazamiento en vía judicial o administrativa, edicto para comparecer, o notificación sustitutoria por imposibilidad de notificación personal (p. ej. publicación en BO por no localizar al interesado con trámite de alegaciones). NO uses esta etiqueta para: mero "anuncio" de aplazamiento de subasta, acuerdos de transferencia de crédito, o resoluciones de fondo sin carácter de emplazamiento/notificación sustitutoria.

- contencioso_administrativo — Recursos, salas de lo contencioso, emplazamientos en pleito contra actos de planeamiento, etc.

- otro_vivienda_urbanismo — Solo si el documento es relevante pero no encaja bien en las anteriores; no lo combines masivamente con otras sin necesidad.

Prioridad ante duda: un acuerdo del Consell/Gobierno que "autoriza transferencia de crédito" entre programas de vivienda → economico_presupuestario_vivienda (y NO ayudas_subvenciones_vivienda salvo que también convoque o resuelva subvenciones a terceros). Una subasta de vivienda de un organismo público → enajenacion_patrimonio_vivienda (y NO ayudas_subvenciones_vivienda).

REGLAS para "urbanismo":
- tipo_instrumento: Plan Parcial / Plan Especial / Modificación PGOU o PGOU / Estudio de Detalle / Proyecto de Urbanización / Normas Subsidiarias / Licencia de obra / Plan General / Iniciativa de compensación o sector / Otro (texto breve).
- estado_tramitacion: Aprobación Inicial / Aprobación Provisional / Aprobación Definitiva / Información Pública / Aprobación a efectos / Licencia concedida / Otro.
- Fechas en formato YYYY-MM-DD si hay día; si solo año, "YYYY".
- num_viviendas_max: entero si aparece (tablas, "nº máximo de viviendas", rangos → el máximo).
- tipo_vivienda: libre / protegida / mixta / unifamiliar / colectiva / null.
- resumen en urbanismo: 1-2 frases sobre el acto urbanístico; si no hay urbanismo, null.

REGLAS para "economico_presupuestario": resumen breve; importe_total_eur si hay un total o transferencia principal clara (número). programas_o_partidas puede ser texto o lista breve de códigos/nombres de programa que aparezcan.

REGLAS para "ayudas_subvenciones": solo si aplica la categoría ayudas_subvenciones_vivienda; rellena convocatoria/bases, expediente, beneficiario e importe concedido o denegado si constan.

REGLAS para "procedimiento": tipo_acto y expediente cuando el documento sea un trámite (emplazamiento, notificación, archivo, subasta aplazada, etc.). Si el acto es presupuestario puro, deja procedimiento casi vacío salvo que cite un expediente administrativo explícito (p. ej. 14.006/20-084).

Si un bloque no aplica, deja sus campos en null. No inventes cifras ni fechas: null si no constan.

Responde SOLO con el JSON."""


_RE_VIVIENDAS = re.compile(
    r"""
    (?:
        n[uú]mero\s+(?:m[aá]ximo\s+)?de\s+viviendas[^:]*?:\s*(\d[\d.,]*)
      | (\d[\d.,]*)\s+viviendas?
      | viviendas?\s*(?:m[aá]x(?:imo)?|totales?|previstas?)[^:]*?:\s*(\d[\d.,]*)
      | nº\s*(?:m[aá]x\s*)?viviendas?[^:]*?:\s*(\d[\d.,]*)
      | de\s+(\d[\d.,]*)\s+viviendas\s+a\s+(\d[\d.,]*)
      | habitatges?\s+(?:m[aá]xims?|totals?)[^:]*?:\s*(\d[\d.,]*)
      | vivendes?\s+(?:m[aá]ximes?|totals?)[^:]*?:\s*(\d[\d.,]*)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RE_FECHA_FIN = re.compile(
    r"""
    (?:
        plazo\s+de\s+ejecuci[oó]n[^:]*?:\s*([^\n]{3,60})
      | fecha\s+(?:prevista|estimada|fin)[^:]*?:\s*([^\n]{3,40})
      | a[ñn]o\s+(?:de\s+)?finalizaci[oó]n[^:]*?:\s*(\d{4})
      | etapa\s+\d+[^:]*?:\s*(?:hasta\s+)?(\d{4})
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RE_IMPORTE = re.compile(
    r"(?:importe|subvenci[oó]n|total|cr[eé]dito)[^:]{0,40}:\s*([\d]{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:€|euros?)",
    re.IGNORECASE,
)


def extract_numeric_snippets(full_text: str) -> str:
    """Fragmentos del texto completo con cifras de viviendas, plazos e importes."""
    snippets: list[str] = []

    for match in _RE_VIVIENDAS.finditer(full_text):
        start = max(0, match.start() - 120)
        end = min(len(full_text), match.end() + 120)
        snippets.append("VIVIENDAS: " + full_text[start:end].replace("\n", " ").strip())

    for match in _RE_FECHA_FIN.finditer(full_text):
        start = max(0, match.start() - 80)
        end = min(len(full_text), match.end() + 120)
        snippets.append("FECHA/PLAZO: " + full_text[start:end].replace("\n", " ").strip())

    for match in _RE_IMPORTE.finditer(full_text):
        start = max(0, match.start() - 60)
        end = min(len(full_text), match.end() + 80)
        snippets.append("IMPORTE: " + full_text[start:end].replace("\n", " ").strip())

    if not snippets:
        return ""

    seen: set[str] = set()
    unique: list[str] = []
    for s in snippets:
        key = s[:72]
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return "\n\n[FRAGMENTOS CLAVE EXTRAÍDOS DEL TEXTO COMPLETO]\n" + "\n".join(unique[:12])


def truncate_text(text: str, max_chars: int = 4000) -> tuple[str, bool]:
    """
    Recorta texto largo para el prompt (cabecera + cola). Devuelve (texto, ¿se recortó?).
    """
    if len(text) <= max_chars:
        return text, False
    head = int(max_chars * 0.75)
    tail = max_chars - head
    return text[:head] + "\n\n[...texto recortado...]\n\n" + text[-tail:], True


def build_context_meta(
    full_text: str,
    *,
    max_context_chars: int,
    body_truncated: bool,
) -> dict[str, Any]:
    """Metadatos para CSV: marcar documentos que merecen segunda pasada (texto no cabía entero)."""
    n = len(full_text)
    return {
        "chars_texto_total": n,
        "llm_max_context_chars": max_context_chars,
        "texto_truncado_llm": body_truncated,
        "requiere_segunda_pasada": body_truncated,
    }


def merge_context_into_flat(flat: dict[str, Any], ctx_meta: dict[str, Any]) -> None:
    for k in CONTEXT_FIELD_KEYS:
        if k in ctx_meta:
            flat[k] = ctx_meta[k]


def context_meta_for_fulltext(full_text: str, max_context_chars: int = 4000) -> dict[str, Any]:
    """Metadatos de truncado sin llamar al LLM (p. ej. texto corto o fallo de API)."""
    _, body_truncated = truncate_text(full_text, max_chars=max_context_chars)
    return build_context_meta(
        full_text, max_context_chars=max_context_chars, body_truncated=body_truncated
    )


def _as_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if x is not None and str(x).strip()]
    s = str(val).strip()
    return [s] if s else []


def _merge_urbanismo(raw: dict[str, Any]) -> dict[str, Any]:
    block = raw.get("urbanismo")
    if not isinstance(block, dict):
        block = {}
    out = {}
    for k in URBANISMO_FIELD_KEYS:
        v = block.get(k)
        if v is None and k in raw:
            v = raw.get(k)
        out[k] = v
    return out


def _infer_text_blob(raw: dict[str, Any]) -> str:
    """Texto concatenado de valores extraídos (sin nombres de campos JSON → menos falsos positivos)."""
    parts: list[str] = []
    for key in ("urbanismo", "economico_presupuestario", "ayudas_subvenciones", "procedimiento"):
        block = raw.get(key)
        if isinstance(block, dict):
            for v in block.values():
                if isinstance(v, str) and v.strip():
                    parts.append(v)
                elif isinstance(v, list):
                    parts.extend(str(x) for x in v if x is not None and str(x).strip())
    for k in ("resumen", "municipio", "tipo_instrumento", "nombre_sector", "organo_aprobador"):
        v = raw.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v)
    return " ".join(parts).lower()


def _infer_categorias(urban: dict[str, Any], raw: dict[str, Any]) -> list[str]:
    cats: list[str] = []
    r = _infer_text_blob(raw)

    if urban.get("nombre_sector") or urban.get("tipo_instrumento"):
        cats.append("urbanismo_planeamiento")
    if urban.get("tipo_instrumento") and "licencia" in str(urban.get("tipo_instrumento")).lower():
        cats.append("licencia_obra_rehabilitacion")

    # Subasta o enajenación de vivienda / inmueble patrimonial
    if ("subasta" in r or "enajen" in r) and ("vivienda" in r or "inmueble" in r or "finca" in r):
        cats.append("enajenacion_patrimonio_vivienda")

    # Presupuesto / crédito en ámbito vivienda (incl. valenciano/catalán)
    if (
        "transferencia de crédito" in r
        or "transferència de crèdit" in r
        or "transferencia de credito" in r
        or "modificación del presupuesto" in r
        or "modificació del pressupost" in r
        or "modificación presupuestaria" in r
        or "peav" in r
        or "incremento de crédito" in r
        or "increment de crèdit" in r
        or ("crédito" in r and "programa" in r and "431" in r)
        or ("crèdit" in r and "programa" in r)
    ):
        cats.append("economico_presupuestario_vivienda")

    # Ayudas/subvenciones a beneficiarios (no basta "línea de subvención" en un crédito presupuestario)
    transferencia_acuerdo = (
        ("autoriza" in r and "transferencia" in r)
        or ("autoritza" in r and "transferència" in r)
        or ("acuerdo" in r and "transferencia de crédito" in r)
        or ("acord" in r and ("transferència" in r or "crèdit" in r))
    )
    ayudas_fuerte = (
        "bases reguladoras" in r
        or "convocatoria de las subvenciones" in r
        or ("convocatòria" in r and "subvenc" in r)
        or ("resolución definitiva" in r and "subvenc" in r)
        or "desistimiento de ayudas" in r
        or "ayuda al alquiler" in r
        or "ayudas para el alquiler" in r
        or "subvención provisional" in r
        or "subvención definitiva" in r
    )
    ayudas_media = "subvenc" in r and (
        "conced" in r or "deneg" in r or "convoc" in r or "solicitud" in r or "beneficiar" in r
    )
    if (ayudas_fuerte or ayudas_media) and not transferencia_acuerdo:
        cats.append("ayudas_subvenciones_vivienda")
    elif ayudas_fuerte and transferencia_acuerdo:
        # Acuerdo que solo mueve créditos: ya está economico; ayudas si hay convocatoria/resolución a terceros
        if "convocatoria" in r or "conced" in r or "deneg" in r or "solicitud" in r:
            cats.append("ayudas_subvenciones_vivienda")

    if "concierto" in r and "plaza" in r:
        cats.append("concertacion_residencial_social")

    notif_sustitutoria = (
        "emplazamiento" in r
        or ("edicto" in r and ("comparecer" in r or "personarse" in r))
        or (
            "notificación" in r
            and (
                "personal" in r
                or "sustitut" in r
                or "imposible" in r
                or "59.4" in r
                or "tablón" in r
                or "perceptiva" in r
                or "preceptiva" in r
            )
        )
    )
    if notif_sustitutoria:
        cats.append("procedimiento_notificacion_emplazamiento")

    if "contencioso" in r or "tribunal superior" in r:
        cats.append("contencioso_administrativo")
    if "vpo" in r or "protección pública" in r or "proteccion publica" in r or "vppl" in r:
        cats.append("vivienda_protegida_publica")
    if not cats and raw.get("es_relevante"):
        cats.append("otro_vivienda_urbanismo")
    # dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in cats:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _parse_importe(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    s = str(val).strip()
    if re.match(r"^[\d.,]+$", s):
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
    try:
        x = float(s)
        return int(x) if x == int(x) else x
    except ValueError:
        return None


def normalize_llm_result(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Convierte la respuesta del modelo (anidada o legada) en un dict plano con FIELDS.
    """
    flat: dict[str, Any] = {k: None for k in FIELDS}

    if not raw:
        flat["es_relevante"] = None
        return flat

    if raw.get("es_relevante") is False:
        flat["es_relevante"] = False
        return flat

    urban = _merge_urbanismo(raw)
    for k in URBANISMO_FIELD_KEYS:
        flat[k] = urban.get(k)

    cats = _as_list(raw.get("categorias_tematicas"))
    if not cats:
        cats = _infer_categorias(urban, raw)
    flat["categorias_tematicas"] = ";".join(cats) if cats else None

    econ = raw.get("economico_presupuestario") if isinstance(raw.get("economico_presupuestario"), dict) else {}
    econ = econ or {}
    flat["economico_resumen"] = econ.get("resumen")

    ay = raw.get("ayudas_subvenciones") if isinstance(raw.get("ayudas_subvenciones"), dict) else {}
    ay = ay or {}
    proc = raw.get("procedimiento") if isinstance(raw.get("procedimiento"), dict) else {}
    proc = proc or {}

    flat["procedimiento_expediente"] = proc.get("expediente") or ay.get("expediente_destacado")
    flat["procedimiento_tipo"] = proc.get("tipo_acto")

    imp = econ.get("importe_total_eur")
    if imp is None:
        imp = ay.get("importe_destacado_eur")
    flat["importe_total_eur_estimado"] = _parse_importe(imp)

    # Resumen global si urbanismo.resumen vacío pero hay otros bloques
    if not flat.get("resumen"):
        parts = []
        if flat.get("economico_resumen"):
            parts.append(str(flat["economico_resumen"]))
        if ay.get("convocatoria_o_bases"):
            parts.append(str(ay["convocatoria_o_bases"]))
        if proc.get("tipo_acto"):
            parts.append(str(proc["tipo_acto"]))
        if parts:
            flat["resumen"] = " | ".join(parts)[:1200]

    flat["es_relevante"] = True
    return flat


def parse_llm_response_content(raw_text: str) -> dict[str, Any]:
    raw_text = raw_text or ""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]+\}", raw_text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


def extract_raw_from_llm(
    client: OpenAI,
    full_text: str,
    pdf_name: str,
    *,
    ctx: BoletinContext | None = None,
    model: str | None = None,
    max_context_chars: int = 4000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Llama al modelo y devuelve (JSON anidado del modelo, metadatos de contexto).

    Metadatos: chars_texto_total, llm_max_context_chars, texto_truncado_llm,
    requiere_segunda_pasada (True si el cuerpo principal se recortó antes del LLM).
    """
    ctx = ctx or DEFAULT_CONTEXT
    model = model or os.getenv("LLM_MODEL", "gemma4-small-8k:latest")
    body, body_truncated = truncate_text(full_text, max_chars=max_context_chars)
    snippets = extract_numeric_snippets(full_text)
    context = body + snippets
    ctx_meta = build_context_meta(
        full_text, max_context_chars=max_context_chars, body_truncated=body_truncated
    )

    user_msg = (
        f"Documento ({ctx.source_id}) — archivo: {pdf_name}\n\n"
        f"{context}\n\n"
        "Responde ÚNICAMENTE con el JSON acordado en las instrucciones, sin markdown."
    )

    kwargs: dict[str, Any] = dict(
        model=model,
        messages=[
            {"role": "system", "content": build_system_prompt(ctx)},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
    )

    try:
        response = client.chat.completions.create(
            **kwargs, response_format={"type": "json_object"}
        )
    except Exception:
        response = client.chat.completions.create(**kwargs)

    raw_content = response.choices[0].message.content or ""
    parsed = parse_llm_response_content(raw_content)
    return (parsed if parsed else {}, ctx_meta)


def parse_with_llm(
    client: OpenAI,
    full_text: str,
    pdf_name: str,
    *,
    ctx: BoletinContext | None = None,
    model: str | None = None,
    max_context_chars: int = 4000,
) -> dict[str, Any]:
    """
    Extrae y normaliza campos. Devuelve dict con claves FIELDS (plano),
    incluyendo requiere_segunda_pasada si el texto se recortó para el LLM.
    """
    parsed, ctx_meta = extract_raw_from_llm(
        client,
        full_text,
        pdf_name,
        ctx=ctx,
        model=model,
        max_context_chars=max_context_chars,
    )
    if not parsed:
        flat = {k: None for k in FIELDS} | {"es_relevante": None}
        merge_context_into_flat(flat, ctx_meta)
        return flat

    flat = normalize_llm_result(parsed)
    merge_context_into_flat(flat, ctx_meta)
    return flat


def flatten_record(llm_flat: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    record = {f: llm_flat.get(f) for f in FIELDS}
    record["pdf_file"] = Path(meta.get("pdf", "")).name
    record["txt_chars"] = meta.get("chars", 0)
    record["pages"] = meta.get("pages", 0)
    return record
