# Córdoba — investigación portal ayuntamiento

**Municipio:** Córdoba (Córdoba, Andalucía)  
**Slug:** `cordoba`  
**Boletín:** sin boletín regional asociado en cola (`bocm_count: 0`)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web / transparencia | https://www.cordoba.es | **Operativa** — Drupal |
| Hub urbanismo | https://www.cordoba.es/transparencia/transparencia-municipal/urbanismo | **Operativa** — acordeón + PDFs |
| Documentos en información pública | https://www.cordoba.es/transparencia/transparencia-municipal/urbanismo/urbanismo-documentos-info-publica | **Operativa** — años 2024–2026, bloques `<details>` |
| GMU (Gerencia Municipal de Urbanismo) | https://www.gmucordoba.es | **Parcial** — TLS/handshake lento desde CI; listado tablón más estable que fichas detalle |
| Tablón GMU | https://www.gmucordoba.es/novedades/itemlist/category/2-tablon-de-anuncios | **Operativa** — Joomla K2, ~14 ítems/página |
| Sede electrónica | https://www.cordoba.es/sede | **Operativa** |
| Trámite licencia nueva planta | https://www.cordoba.es/sede/tramites/urbanismo/solicitud-licencia-urbanistica-obras-nueva-planta | Informativo (presentación electrónica) |
| Datos abiertos (CKAN) | https://datosabiertos.cordoba.es/ckan/ | **Parcial** — callejero CSV; sin dataset de expedientes/licencias |
| PGOU (GMU) | https://www.gmucordoba.es/urbanismo/plan-general-de-ordenacion-urbanistica-pgou | Referencia planeamiento; visor no enlazado a expedientes del tablón |

## Cómo se listan expedientes / planeamiento

1. **Información pública (Drupal):** páginas anuales con bloques `<details><summary>` por actuación (edictos, PCTM, enlaces CSV de verificación documental en sede).
2. **Transparencia urbanismo:** acordeón `ckeditor-accordion` con expedientes puntuales (instrucciones, aprobaciones iniciales) y tablas CSV.
3. **Tablón GMU (Joomla):** títulos de edictos con referencia de expediente y serie; documentos en ficha (PDF) — el adapter usa títulos del listado por fiabilidad en CI.

## Licencias de obra

- No hay dataset público de licencias concedidas con dirección/coordenadas.
- Instrucción GMU y PDF agregado «Licencias y autorizaciones» en transparencia.
- Trámite de solicitud en sede (obra nueva planta).
- El tablón GMU publica algunas **calificaciones ambientales** / actividades (tratadas como filas de licencias cuando el título coincide).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - CKAN `callejero-de-cordoba` (CSV vial, sin enlace a expediente).
  - PGOU y cartografía en GMU / Junta (SITUA, VITUA) sin query REST por código de expediente municipal del tablón.
  - Documentos en información pública: PDF/edicto vía CSV sede, sin geometría embebida.
- **Estrategia:** el orquestador aplicará centroide municipio + jitter (`manifest.centroid`).
- **Limitaciones:**
  - Fichas detalle GMU pueden hacer timeout SSL desde entornos cloud.
  - Sin `geom_geojson` por expediente en fuentes scrapeadas.

## Limitaciones generales

- Consulta de expedientes en tramitación presencial (GMU), no listado masivo web.
- Tablón con paginación limitada en el adapter (`tablon_max_pages: 4`).
- Catálogo sede no expone fácilmente todos los trámites de urbanismo vía HTML estático.

## Adapter implementado

- `municipio.adapters.cordoba:CordobaAyuntamientoAdapter`
- Orígenes: `drupal_info_publica`, `drupal_urbanismo_accordion`, `gmu_joomla_tablon`, trámites/PDFs licencia.
