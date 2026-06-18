# Alcobendas — investigación portal ayuntamiento

## Resumen

Portal **Drupal** en `https://www.alcobendas.org` (Akamai CDN). El scraping requiere
`User-Agent` identificable y cabecera `Accept-Encoding: gzip` (sin ella Akamai devuelve 403).

No hay API REST pública de expedientes; la ingesta se basa en HTML + PDFs del portal.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de edictos | `/es/tramites/tablon-edictos` | Drupal Views | Anuncios/licencias en trámite (PDF + fechas) |
| Acuerdos IP (Urbanismo) | `/es/ayuntamiento/informacion-administrativa/acuerdos-informacion-publica?field_departamento_target_id=2466` | Acordeón `ps-id-*` | Planes parciales/especiales, modificaciones PGOU |
| Convenios urbanísticos | `/es/ayuntamiento/informacion-administrativa/convenios?field_area_tematica_target_id=1110` | Acordeón | Convenios de ejecución urbanística |
| PGOU y planeamiento | `/es/temas/ciudad-sostenible/urbanismo/PGOU` (+ subpáginas) | HTML + PDF | Documentación PGOU, planos, modificaciones |
| Planes especiales | `/es/temas/ciudad-sostenible/urbanismo/planes-especiales` | Listado PDF | Planes especiales vigentes |
| Desarrollos | `/es/temas/ciudad-sostenible/urbanismo/desarrollos-en-ejecucion`, `nuevos-desarrollos` | HTML + enlaces | Planes parciales en ejecución/desarrollo |
| Export JSON Drupal | `/ayto-exportacion-contenido/json?id={nid}` | JSON nodo | Respaldo puntual (no usado en producción) |

## Estructura HTML relevante

### Tablón de edictos

- Vista Drupal: filas `div.views-row`
- Campos: `field--name-name` (título), `Fecha inicio: DD-MM-YYYY`, PDF en `/sites/default/files/`

### Acuerdos en información pública / Convenios

- Acordeón: `div.title_container[data-target="#ps-id-NNNNN"]` → `div.titulo` (título expediente)
- Contenido: `div.collapse#ps-id-NNNNN` con enlaces PDF y ocasionalmente BOCM externo

## Licencias

El ayuntamiento **no publica un listado tabular de concesiones** con coordenadas (no hay paridad
con el visor de Madrid capital). Las licencias proceden del tablón de edictos filtrando títulos
que mencionan licencia/instalación/edicto urbanístico.

## Limitaciones

- Akamai puede bloquear IPs automatizadas (403); el adapter reintenta con backoff.
- El tablón muestra solo edictos vigentes (~pocos activos); el histórico no está paginado en la vista pública.
- Sin geolocalización en fuentes del ayuntamiento (`lat`/`lon` = null).
- La sede electrónica (`tramitessede.alcobendas.org`) es para trámites, no listados públicos scrapeables.

## Referencia adapters

- Estilo acordeón/PDF: similar a `pozuelo.py` (Drupal expedientes)
- Tablón edictos: similar a `mostoles.py` (filtrado por regex en títulos)
