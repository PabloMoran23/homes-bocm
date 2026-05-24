"""Clasificación heurística de expedientes SIGMA en cuatro ejes."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        n = float(str(value).replace(",", "."))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def classify_tipo_obra(
    *,
    blob: str,
    figura: Any,
    viviendas: int,
    tipo_legal: str,
    contenido: str,
    layer: Any,
) -> str:
    figura_blob = _norm(figura)

    if _has(
        blob,
        r"garaj",
        r"aparcam",
        r"estacionam",
        r"parkings?",
        r"\bp\+p\b",
        r"plaza de garaje",
    ):
        return "garaje_aparcamiento"

    if _has(
        blob,
        r"terraza",
        r"cerram",
        r"mesas y sillas",
        r"pecuau",
        r"control urbanistico ambiental",
        r"control urbanístico ambiental",
        r"ordenacion de uso",
        r"ordenación de uso",
    ) or _has(figura_blob, r"pecuau"):
        return "ordenacion_usos_actividad"

    if _has(
        blob,
        r"\bacera",
        r"via publica",
        r"vía pública",
        r"viario",
        r"paviment",
        r"calzada",
        r"peaton",
        r"peatonal",
        r"intercambiador",
        r"renaturalizacion de calle",
    ):
        return "infraestructura_viaria"

    if _has(
        blob,
        r"bar[\s-]?restaurante",
        r"\brestaurante\b",
        r"\bbar\b",
        r"hosteler",
        r"\bhotel\b",
        r"hospedaje",
        r"\boficina",
        r"comercial",
        r"terciario",
        r"actividad economica",
        r"actividad económica",
        r"local comercial",
    ) or _has(figura_blob, r"plan especial de juntas", r"\bpej\b"):
        return "uso_terciario"

    if viviendas >= 100 or (
        viviendas > 0
        and _has(blob, r"viviend", r"residencial", r"bloque de viviend", r"unidades de viviend")
    ):
        return "vivienda_residencial"

    if _has(
        blob,
        r"colegio",
        r"centro de salud",
        r"hospital",
        r"equipamiento",
        r"dotacional",
        r"deportivo",
        r"cultural",
        r"tanatorio",
        r"centro docente",
    ):
        return "equipamiento_publico"

    if _has(blob, r"catalog", r"protecci", r"patrimonial", r"bien de interes", r"\bbic\b"):
        return "proteccion_patrimonio"

    if layer == "gestion" or _has(
        blob,
        r"reparcelaci",
        r"junta de compensacion",
        r"equidistribucion",
        r"expropiacion",
    ):
        return "reparcelacion_gestion"

    if tipo_legal == "modificacion_pgou" or _has(blob, r"modificacion del plan general", r"\bmpg\b"):
        return "modificacion_planeamiento"

    if layer == "urbanizacion" or _has(
        blob,
        r"proyecto de urbanizacion",
        r"urbanizaci",
        r"infraestructura",
        r"\bredes\b",
        r"servicios urbanos",
        r"canalizacion",
        r"alcantarill",
    ):
        return "urbanizacion_redes"

    if viviendas > 0 or _has(
        blob,
        r"viviend",
        r"residencial",
        r"unifamiliar",
        r"plurifamiliar",
        r"bloque",
    ):
        return "vivienda_residencial"

    if _has(
        blob,
        r"ampliacion",
        r"ampliación",
        r"reforma",
        r"rehabilit",
        r"edificabilidad",
        r"volumen",
        r"ordenacion de vol",
        r"ordenación de vol",
        r"edificio",
        r"parcela",
        r"solar",
    ) or tipo_legal in {"estudio_detalle", "plan_especial", "plan_parcial"}:
        return "edificio_ampliacion"

    mapping = {
        "vivienda_residencial": "vivienda_residencial",
        "urbanizacion_infraestructura": "urbanizacion_redes",
        "gestion_reparcelacion": "reparcelacion_gestion",
        "proteccion_catalogo": "proteccion_patrimonio",
        "dotacional_equipamiento": "equipamiento_publico",
        "terciario_comercial_hotelero": "uso_terciario",
        "uso_actividad_edificio_existente": "ordenacion_usos_actividad",
        "ordenacion_parcela": "edificio_ampliacion",
    }
    if contenido in mapping:
        return mapping[contenido]

    if tipo_legal == "ajuste_administrativo":
        return "sin_determinar"

    return "sin_determinar"


def classify_sigma_project(
    *,
    visor_ficha: dict[str, Any] | None,
    resumen_contenido: str | None,
    sigma_layer_kind: str | None,
    catalog: dict[str, Any] | None = None,
    area_approx_m2: float | None = None,
    num_viviendas_max: int | None = None,
) -> dict[str, Any]:
    ficha = visor_ficha or {}
    catalog = catalog or {}
    figura = ficha.get("figuraTipo") or catalog.get("tipo_figura") or catalog.get("TFIG_TX_ABREV")
    tipo_planeamiento = ficha.get("tipoPlaneamiento")
    fase = catalog.get("fase") or catalog.get("FAS_TX_DENOM")
    layer = sigma_layer_kind or catalog.get("sigma_layer_kind") or catalog.get("source")
    visor_m2 = _num(ficha.get("superficieAmbitoM2"))
    area = area_approx_m2 or visor_m2
    viviendas = int(num_viviendas_max or 0)

    denominacion = catalog.get("denominacion") or catalog.get("EXP_TX_DENOM")
    blob = _norm(
        " ".join(
            str(x or "")
            for x in (
                resumen_contenido,
                ficha.get("descripcionAmbito"),
                ficha.get("denominacionVisor"),
                ficha.get("ambitoOrdenacion"),
                denominacion,
                figura,
                tipo_planeamiento,
                layer,
                fase,
            )
        )
    )
    reasons: list[str] = []

    if _has(blob, r"modificacion (puntual )?(del )?(plan general|pgou)", r"\bmpg\b"):
        tipo_legal = "modificacion_pgou"
    elif _has(blob, r"estudio de detalle", r"\bed\b"):
        tipo_legal = "estudio_detalle"
    elif _has(blob, r"plan parcial", r"\bpp\b"):
        tipo_legal = "plan_parcial"
    elif _has(blob, r"plan especial", r"\bpe\b"):
        tipo_legal = "plan_especial"
    elif _has(blob, r"urbanizacion", r"proyecto de urbanizacion"):
        tipo_legal = "proyecto_urbanizacion"
    elif _has(blob, r"reparcelacion", r"junta de compensacion", r"gestion"):
        tipo_legal = "gestion_reparcelacion"
    elif _has(blob, r"catalogacion", r"catalogo", r"proteccion"):
        tipo_legal = "catalogacion_proteccion"
    elif _has(blob, r"subsanacion", r"error material"):
        tipo_legal = "ajuste_administrativo"
    else:
        tipo_legal = "otro_instrumento"
    reasons.append(f"tipo:{tipo_legal}")

    if area is None:
        escala = "sin_escala"
    elif area < 500:
        escala = "micro_parcela"
    elif area < 2_000:
        escala = "parcela"
    elif area < 10_000:
        escala = "manzana_o_ambito_pequeno"
    elif area < 50_000:
        escala = "ambito_medio"
    else:
        escala = "gran_ambito"
    if viviendas >= 500 and escala not in {"gran_ambito", "ambito_medio"}:
        escala = "gran_ambito"
        reasons.append("escala:ajustada_por_viviendas")
    else:
        reasons.append(f"escala:{escala}")

    if layer == "urbanizacion" or _has(blob, r"urbanizaci", r"infraestructura", r"\bviario\b", r"redes", r"servicios urbanos"):
        contenido = "urbanizacion_infraestructura"
    elif layer == "gestion" or _has(blob, r"reparcelaci", r"junta de compensacion", r"equidistribucion", r"expropiacion"):
        contenido = "gestion_reparcelacion"
    elif _has(blob, r"catalog", r"protecci", r"patrimonial", r"bien de interes", r"\bbic\b"):
        contenido = "proteccion_catalogo"
    elif viviendas > 0 or _has(blob, r"viviend", r"residencial", r"alojamiento dotacional"):
        contenido = "vivienda_residencial"
    elif _has(blob, r"dotacional", r"equipamiento", r"colegio", r"escuela", r"hospital", r"centro de salud", r"deportivo", r"cultural"):
        contenido = "dotacional_equipamiento"
    elif _has(blob, r"terciario", r"comercial", r"hotel", r"oficina", r"actividad economica"):
        contenido = "terciario_comercial_hotelero"
    elif _has(blob, r"pecuau", r"control urbanistico ambiental", r"local", r"terraza", r"aparcamiento", r"garaje", r"actividad"):
        contenido = "uso_actividad_edificio_existente"
    elif tipo_legal in {"estudio_detalle", "plan_especial"}:
        contenido = "ordenacion_parcela"
    else:
        contenido = "sin_clasificar"
    reasons.append(f"contenido:{contenido}")

    fase_blob = _norm(fase)
    if layer == "gestion":
        fase_normalizada = "gestion"
    elif layer == "urbanizacion":
        fase_normalizada = "urbanizacion"
    elif _has(fase_blob, r"informacion publica"):
        fase_normalizada = "informacion_publica"
    elif _has(fase_blob, r"aprobacion definitiva"):
        fase_normalizada = "aprobacion_definitiva"
    elif _has(fase_blob, r"aprobacion provisional"):
        fase_normalizada = "aprobacion_provisional"
    elif _has(fase_blob, r"aprobacion inicial"):
        fase_normalizada = "aprobacion_inicial"
    elif _has(fase_blob, r"archiv", r"desist", r"caduc"):
        fase_normalizada = "archivado_o_detenido"
    elif _has(fase_blob, r"inicio", r"incoad"):
        fase_normalizada = "expediente_abierto"
    else:
        fase_normalizada = "en_tramitacion"

    if contenido == "vivienda_residencial" and (escala in {"gran_ambito", "ambito_medio"} or viviendas >= 100):
        categoria = "gran_desarrollo_residencial"
    elif contenido == "vivienda_residencial":
        categoria = "residencial_o_vivienda"
    elif contenido == "urbanizacion_infraestructura":
        categoria = "urbanizacion_infraestructuras"
    elif contenido == "gestion_reparcelacion":
        categoria = "gestion_reparcelacion"
    elif contenido == "proteccion_catalogo":
        categoria = "proteccion_catalogo"
    elif contenido == "dotacional_equipamiento":
        categoria = "equipamiento_dotacional"
    elif contenido == "terciario_comercial_hotelero":
        categoria = "terciario_comercial_hotelero"
    elif contenido == "uso_actividad_edificio_existente":
        categoria = "plan_especial_uso_actividad"
    elif tipo_legal == "modificacion_pgou":
        categoria = "modificacion_planeamiento_general"
    elif tipo_legal in {"estudio_detalle", "plan_especial"} and escala in {"micro_parcela", "parcela", "manzana_o_ambito_pequeno"}:
        categoria = "ordenacion_parcela_manzana"
    elif tipo_legal == "ajuste_administrativo":
        categoria = "ajuste_administrativo"
    else:
        categoria = "planeamiento_otros"

    tipo_obra = classify_tipo_obra(
        blob=blob,
        figura=figura,
        viviendas=viviendas,
        tipo_legal=tipo_legal,
        contenido=contenido,
        layer=layer,
    )
    reasons.append(f"tipo_obra:{tipo_obra}")

    evidence = sum(
        1
        for ok in (
            bool(figura),
            bool(tipo_planeamiento),
            bool(resumen_contenido),
            area is not None,
            bool(layer),
            bool(fase),
            viviendas > 0,
        )
        if ok
    )
    if contenido == "sin_clasificar" or evidence <= 2:
        confianza = "baja"
    elif evidence >= 5 and resumen_contenido:
        confianza = "alta"
    else:
        confianza = "media"

    return {
        "tipo_legal": tipo_legal,
        "escala": escala,
        "contenido_principal": contenido,
        "fase_normalizada": fase_normalizada,
        "categoria_proyecto": categoria,
        "tipo_obra": tipo_obra,
        "clasificacion_confianza": confianza,
        "clasificacion_fuentes": {
            "reasons": reasons,
            "figuraTipo": figura,
            "tipoPlaneamiento": tipo_planeamiento,
            "sigmaLayerKind": layer,
            "fase": fase,
            "areaApproxM2": area,
            "superficieVisorM2": visor_m2,
            "numViviendasMax": viviendas or None,
            "hasResumenContenido": bool(resumen_contenido),
            "tipoObra": tipo_obra,
        },
    }
