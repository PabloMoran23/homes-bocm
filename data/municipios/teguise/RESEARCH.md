# Teguise — investigación portal ayuntamiento

Municipio: **Teguise** (`teguise`), provincia Las Palmas, CCAA Canarias. INE **35024**.

## Fuentes base

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal | https://teguise.es | WordPress (Avada). Tablón en `/tablon-anuncios/` (poco urbanismo; mayoría convocatorias). |
| Sede electrónica | https://sede.teguise.es | Plataforma **ATM-Maggioli** (Angular SPA). |
| Informe urbanístico | https://sede.teguise.es/publico/territorio/informeurbanistico | Visor/ficha por parcela (junio 2026, noticia municipal). Sin listado de expedientes. |
| Tablón sede | https://sede.teguise.es/board | SPA; no hay HTML con `preview-document` como espublico gestiona. |
| Oficina técnica | https://teguise.es/servicios/oficina-tecnica/ | Trámites presenciales; sin listado público de expedientes. |
| Repositorio trámites | https://teguise.es/servicios/economia-y-hacienda/repositorio-de-tramites-administrativos/ | Códigos OT/OBR (201 licencia obra mayor, etc.). |
| SITCAN | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-teguise | Recursos enlazan a GEOBDP. API CKAN a veces lenta; fallback HTML del dataset. |
| GEOBDP | https://geobdp.grafcan.es/core/municipios/35024/ | Índice instrumentos de planeamiento del municipio. |

## Cómo se listan expedientes / licencias

- **Planeamiento:** principalmente **SITCAN + GEOBDP** (aprobaciones PGO, modificaciones puntuales, etc.), no un registro de expedientes IP en web.
- **Licencias de obra:** no hay tablón público estructurado de concesiones (como Telde/Móstoles). La sede Maggioli expone trámites (OT-201…) y el informe urbanístico por parcela; el tablón WordPress no publica licencias de forma sistemática.
- **Adapter:** ingesta SITCAN/GEOBDP → `proyectos.jsonl`; licencias → páginas informativas de trámites + intento de tablón sede.

## Geometría / visor

- **geometry_status:** `available` (planeamiento vía GEOBDP; no por expediente de licencia).
- **Fuentes:** GEOBDP Grafcan — cada documento `/core/documentos/{id}.html` incluye `App.Map.zoomToExtent` con GeoJSON en **EPSG:32628** (reproyectado a WGS84 en el adapter).
- **Estrategia:** emparejar título recurso SITCAN ↔ documento GEOBDP; descargar geometría del HTML del documento.
- **Limitaciones:** visor sede (`informeurbanistico`) es consulta por parcela (sin API pública scrapeable para listados). Tablón sede SPA sin geometría enlazada. Licencias sin polígono público.

## Limitaciones técnicas

- SITCAN API (`package_show`) puede timeout; fallback parseando HTML del dataset y listado GEOBDP municipio.
- Sede Maggioli `/board` no devuelve tabla HTML scrapeable (Angular).
- Sin boletín BOCM asociado en cola (`bocm_count: 0`).
