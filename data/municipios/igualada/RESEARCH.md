# Igualada — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Web | https://www.igualada.cat (Plone, tema Ajuntament Igualada) |
| Sede / trámites | https://tramits.igualada.cat (e-Tràmits) |
| Transparencia | https://seu-e.cat/ca/web/igualada/... |
| INE | 08102 |

## Fuentes — proyectos / planeamiento

| URL | Contenido |
|-----|-----------|
| `/ca/regidories/urbanisme-i-mobilitat/Urbanisme/arxius-descarregables` | **e-tauler**: ~50 bloques `<h3>` con título de proyecto/IP y enlaces PDF en `/fitxers/.../arxius-e-tauler/` |
| `.../arxius-descarregables/projectes-durbanitzacio` | Misma estructura, proyectos de urbanización |
| `.../Urbanisme/planejament-vigent` | Normativa PGOU (PDFs Plone) |
| `.../noticies/noticies/RSS` | Noticias regiduría urbanismo (filtradas por keywords) |
| https://dtes.gencat.cat/rpucportal/...municipiSel=08102 | RPUC — consulta expedientes (sin scrape masivo en adapter) |

Listado principal: HTML Plone, títulos en catalán, documentos PDF estáticos. Fechas inferidas de prefijos `YYMMDD_` en nombres de fichero cuando existen.

## Fuentes — licencias

No hay dataset público de licencias concedidas con dirección/fecha.

| URL | Uso |
|-----|-----|
| `tramits.igualada.cat/.../TramitsTemes.aspx?IdTema=22` | Trámites urbanismo: prórroga llicència, fiances d'obra, certificat qualificació urbanística, etc. |
| seu-e.cat — tauler d'edictes | Anuncios (portlet JS; no listado estable en HTML inicial) |
| Páginas informativas | Enlace RPUC y sección Urbanisme |

Patrón: filas informativas de trámites (como Mataró/Pozuelo), no concesiones tabuladas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - `/ca/planol` — Google Maps embebido (POIs ciudad, sin capas de expediente).
  - `/ca/regidories/urbanisme-i-mobilitat/emig-cartografia-i-sig` — texto descriptivo EMIG/SIG municipal; sin URL ArcGIS/WFS pública en la página.
  - `geoportal.igualada.cat`, `mapes.igualada.cat` — sin respuesta / no resuelven desde red del agente.
  - RPUC / MUC visor Generalitat (`municipi=08102`) — metadatos de expediente, no polígono enlazable al listado e-tauler por título.
- **Estrategia:** el orquestador usa `centroid` del manifest + jitter.
- **Limitaciones:** proyectos solo PDF; sin visor urbanístico público con `returnGeometry` enlazado a cada anuncio.

## Limitaciones

- Tauler seu-e requiere JS para el listado completo de edictos.
- e-Tràmits no expone API de licencias otorgadas.
- SSL y tiempos de respuesta normales en igualada.cat.
