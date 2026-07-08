# Burgos — investigación portal ayuntamiento

**Municipio:** Burgos (`burgos`)  
**CCAA:** Castilla y León · **Boletín:** BOCYL (`bocyl`)  
**Fecha investigación:** 2026-07-08

## URLs base y páginas semilla

| Fuente | URL | Mecanismo | Contenido |
|--------|-----|-----------|-----------|
| Portal web | https://www.aytoburgos.es | Liferay DXP | Urbanismo, anuncios, instrumentos PGOU |
| Urbanismo | https://www.aytoburgos.es/urbanismo | Asset Publisher + cards | Actualidad, normativa, enlaces planeamiento |
| Anuncios urbanismo | https://www.aytoburgos.es/anuncios-urbanismo | Liferay Asset Publisher (`gCaAF8Ntm38m`) | ~25 anuncios (exc-urb, tramitaciones, proyectos) |
| Instrumentos planeamiento | https://www.aytoburgos.es/instrumentos-planeamiento-gestion | Liferay Asset Publisher (`o6ZrRXHm8Z7I`) | ~387 expedientes PGOU (est, mod, pla-fom, norm…) |
| Sede STA tablón | https://sede.aytoburgos.es/sta/.../PAGE_CODE=PTS2_TABLON | JSON embebido `dataset_PTS2_TABLON` | 118 publicaciones (filtro Gerencia Urbanismo) |
| Sede catálogo | https://sede.aytoburgos.es/sta/.../PAGE_CODE=CATALOGO | JSON embebido `dataset_CATSERV` | Trámites licencias y urbanismo |
| Visor cartográfico | https://ide.aytoburgos.es/ | IDE municipal (enlace desde /urbanismo) | PGOU y capas urbanísticas |

## Cómo se listan expedientes

- **Instrumentos de planeamiento:** buscador Liferay con paginación (`_cur=0..7`, 50 ítems/página). Cada entrada enlaza a ficha `/-/asset_publisher/.../content/<código>` con título tipo `000001/2026 EST-PGOU`.
- **Anuncios urbanismo:** listado Asset Publisher paginado (3 páginas, 25 entradas). Títulos en HTML junto al enlace (`2/2023 EXC-URB …`).
- **Tablón STA:** DataTables alimentado por `var dataset_PTS2_TABLON = [...]` en el HTML (patrón Getafe/Fuenlabrada). Campos: `descriptionProc`, `pubDateIni`, `remitent`, `dboid`.
- **Actualidad /urbanismo:** cards con enlaces a fichas Asset Publisher (proyectos de urbanización, PERI Gamonal, etc.).

## Cómo se publican licencias

- No hay listado público de licencias concedidas con dirección/coords.
- El tablón STA incluye pocas entradas de licencias/obra (filtro por palabra clave).
- El catálogo CATSERV expone trámites de la familia **Licencias** (NPL-01, LICRLC-01, OPU-01, etc.) y **Urbanismo y Vivienda** — páginas informativas de trámite, no concesiones.
- Estrategia adapter: tablón (matches licencia) + catálogo CATSERV (trámites licencia/obra).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Visor IDE en https://ide.aytoburgos.es/ (enlazado como «Visor cartográfico» desde /urbanismo). Probable stack GIS propio del ayuntamiento; no se localizó ArcGIS REST/WFS público enlazable a expediente desde el portal.
- **Estrategia:** No implementada — conexión a `ide.aytoburgos.es` reseteada desde el entorno del agente; fichas Liferay y tablón STA no incluyen GeoJSON ni enlace directo parcela↔expediente.
- **Limitaciones:** Sin API GIS pública documentada; listados son metadatos + PDFs. El orquestador aplicará centroide municipio + jitter.

## Limitaciones

- Tablón STA global (118 filas) mezcla tributos, empleo, etc.; filtro por remitente «Gerencia Municipal de Urbanismo» reduce a ~6 entradas.
- Paginación Liferay de anuncios devuelve duplicados en `cur=1`; total útil ~25 anuncios.
- Instrumentos planeamiento son metadatos de expediente PGOU, no geometría de obra individual.
- IDE cartográfico inaccesible para scrape automatizado (TCP reset).
