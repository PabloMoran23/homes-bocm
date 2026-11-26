"""Clasificación por reglas de los anuncios de tablón.

Primera pasada barata para poder filtrar en la base de datos. No decide qué se
publica: ``homes.anuncio.visible_radar`` se fija aparte. Si cambian las reglas,
sube ``REGLAS_VERSION`` y reclasifica (las filas guardan la versión usada).

Orden: de lo más específico a lo más general. El procedimiento del catálogo
Gestiona pesa más que el título, porque el título suele ser genérico
("Anuncio", "Edicto", "Decreto").
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

REGLAS_VERSION = 1

# (clase, subclase, patrón) — se evalúan en orden; gana la primera.
_REGLAS: list[tuple[str, str | None, str]] = [
    ("vivienda_protegida", None, r"vivienda(s)? (protegida|de proteccion|publica|social)|\bvpo\b|\bvpp\b|alquiler (joven|asequible|social)|sorteo de vivienda|sorteo \d+ vivienda|adjudicacion de vivienda|registro (de|publico de) demandantes"),
    ("empleo_publico", None, r"seleccion(es)? de personal|provision(es)? de puestos|oposicion|concurso.oposicion|bolsa de (empleo|trabajo)|plaza(s)? de|tribunal calificador|proceso selectivo|nombramiento de funcionari|empleo publico"),
    ("expropiacion", None, r"expropiaci|ocupacion temporal|bienes y derechos afectados|justiprecio|levantamiento de actas previas"),
    ("enajenacion_patrimonio", None, r"enajenaci|contrataciones patrimoniales|subasta|venta de (parcela|solar|finca|inmueble)|derecho de superficie|cesion de (uso|parcela)|patrimonio municipal del suelo|arrendamiento de (local|inmueble|finca|parcela)|concesion demanial|bienes patrimoniales"),
    ("contratacion_adjudicacion", None, r"adjudicaci|formalizaci[oó]n del contrato|formalizacion de contrato"),
    ("contratacion_licitacion", None, r"licitaci|contrataci[oó]n|perfil del contratante|pliego|anuncio previo de contrat|procedimiento abierto|contrato (de|menor)"),
    ("ambiental", None, r"calidad ambiental|evaluacion (ambiental|de impacto)|impacto ambiental|autorizacion ambiental|licencia ambiental|calificacion ambiental|actividad(es)? clasificada|comunicacion ambiental|informe ambiental estrategico"),
    ("energia", None, r"fotovoltaic|placas solares|autoconsumo|parque eolico|eolic|subestacion|linea (electrica|de (alta|media) tension)|instalacion(es)? de energia|biogas|hidrogeno"),
    ("planeamiento", None, r"plan general|pgou|p\.g\.o\.u|poum|normas subsidiarias|plan parcial|plan especial|estudio de detalle|modificacion puntual|modificacion (n\.?o?|numero) \d|planeamiento|reparcelaci|proyecto de urbanizacion|junta de compensacion|unidad de (actuacion|ejecucion)|sector (de suelo|urbanizable)|convenio urbanistico|catalogo de (bienes|proteccion)|instrumento de ordenacion"),
    ("licencia_actividad", None, r"licencia de (apertura|actividad)|declaracion responsable de (actividad|apertura)|apertura de (establecimiento|local|actividad)|cambio de titularidad|actividad(es)? (economica|comercial)|terraza"),
    ("licencia_obra", "primera_ocupacion", r"primera ocupacion|1.? ?ocupacion|licencia(s)? de primera"),
    ("licencia_obra", "demolicion", r"demolicion|ruina"),
    ("licencia_obra", "suelo_rustico", r"suelo (no urbanizable|rustico)|uso excepcional|declaracion de interes (publico|comunitario)|proyecto de actuacion"),
    ("licencia_obra", None, r"licencia(s)? (de obra|urbanistica)|obra(s)? mayor|obra(s)? menor|declaracion responsable de obra|comunicacion previa de obra|licencia de edificacion|disciplina urbanistica|orden de ejecucion|legalizacion|restauracion de la legalidad"),
    ("subvencion", None, r"subvenci|ayuda(s)? (economica|para|a la|al)|convocatoria de ayudas|bases reguladoras|becas?\b|premio"),
    ("hacienda_presupuesto", None, r"presupuesto|modificacion de credito|credito extraordinario|suplemento de credito|cuenta general|padron fiscal|padron de (la )?tasa|cobranza|recaudacion|operacion(es)? de (credito|tesoreria)|financiacion|tasa(s)?\b|impuesto|ibi\b|ivtm|plusvalia|ordenanza fiscal|precio publico"),
    ("normativa", None, r"ordenanza|reglamento|aprobacion (inicial|definitiva) de (la )?ordenanza"),
    ("convenio", None, r"convenio"),
    ("organos_gobierno", None, r"pleno|junta de gobierno|decreto de alcaldia|resolucion de alcaldia|delegacion de (competencias|funciones)|organos de gobierno|sesion (ordinaria|extraordinaria)|regimen de sesiones|retribuciones|dedicacion exclusiva"),
    ("padron_elecciones", None, r"padron (municipal )?de habitantes|elecciones|censo electoral|mesas electorales|juez de paz"),
    ("sancion", None, r"sancionador|expediente sancionador|sancion(es)?\b|multa(s)?\b|infraccion"),
    ("notificacion", None, r"notificacion|edicto de notificacion|anuncio de notificacion|intento de notificacion|baja de oficio|caducidad de inscripcion"),
    ("bando_aviso", None, r"bando|aviso|fiestas|cortes? de (agua|trafico|calle)|corte de suministro|via publica|circulacion"),
    ("urbanismo_otro", None, r"urbanis|edificaci"),
]
_COMPILED = [(c, s, re.compile(p)) for c, s, p in _REGLAS]


def _norm(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


# Clases que no dicen nada del contenido: solo se usan si no hay otra.
_GENERICAS = {"organos_gobierno", "bando_aviso", "notificacion"}
# Si el título las nombra, mandan sobre el catálogo (salvo empleo público):
# un estudio de detalle archivado en «Licencias Urbanísticas» es planeamiento.
_TEXTO_PRIORITARIO = {"planeamiento", "expropiacion", "enajenacion_patrimonio", "vivienda_protegida", "energia"}


def _match(blob: str) -> tuple[str, str | None] | None:
    if not blob.strip():
        return None
    for clase, subclase, rx in _COMPILED:
        if rx.search(blob):
            return clase, subclase
    return None


def clasificar(anuncio: dict[str, Any]) -> dict[str, Any]:
    """Devuelve ``{"clase", "subclase", "clase_regla", "clase_version"}``.

    Manda el procedimiento/categoría del catálogo si da una clase específica
    (el título suele ser genérico o engañoso: «Propuesta de contratación
    oficial primera» es empleo). Si no, el título y la descripción. Las clases
    genéricas (órganos de gobierno, bandos, notificaciones) solo como último
    recurso. Ojo: en Gestiona «Licencias de Ocupación» es ocupación de vía
    pública, no primera ocupación.
    """
    texto = _match(_norm(" ".join(str(anuncio.get(k) or "") for k in ("titulo", "descripcion"))))
    catalogo = _match(_norm(" ".join(str(anuncio.get(k) or "") for k in ("procedimiento", "categoria"))))
    elegido, regla = None, None
    # urbanismo_otro es específico pero vago: cede ante una clase concreta.
    orden = (("catalogo", catalogo), ("texto", texto))
    if texto and (catalogo is None or catalogo[0] != "empleo_publico") and (
        texto[0] in _TEXTO_PRIORITARIO
        or (catalogo and catalogo[0] == "urbanismo_otro" and texto[0] not in _GENERICAS)
    ):
        orden = (("texto", texto), ("catalogo", catalogo))
    for fuente, hit in orden:
        if hit and hit[0] not in _GENERICAS:
            elegido, regla = hit, fuente
            break
    if elegido is None:
        for fuente, hit in orden:
            if hit:
                elegido, regla = hit, fuente
                break
    if elegido is None:
        return {"clase": "otros", "subclase": None, "clase_regla": None, "clase_version": REGLAS_VERSION}
    return {
        "clase": elegido[0],
        "subclase": elegido[1],
        "clase_regla": regla,
        "clase_version": REGLAS_VERSION,
    }
