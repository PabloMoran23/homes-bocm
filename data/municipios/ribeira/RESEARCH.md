# Ribeira — portal ayuntamiento

## Fuentes base

| Recurso | URL |
|---------|-----|
| Web corporativa (Liferay) | https://www.ribeira.gal |
| Planeamento urbanístico | https://www.ribeira.gal/planeamento-urbanistico |
| Exposicións públicas | https://www.ribeira.gal/exposicions-publicas |
| Anuncios / tablón (enlace) | https://www.ribeira.gal/anuncios |
| PERI polígono 8 | https://www.ribeira.gal/plan-especial-de-reforma-interior-del-pol%C3%8Dgono-8-del-plan-general-de-ordenaci%C3%93n-municipal. |
| PERI polígono 27 (PIRE) | https://www.ribeira.gal/pire-plan-especial-de-reforma-interior-do-pol%C3%ADgono-27- |
| Sede electrónica | https://sede.ribeira.gal |
| Catálogo trámites | https://sede.ribeira.gal/Editors/DlgTramiteSede.aspx |
| SIOTUGA inventario INE 15057 | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15057&lang=es_ES |
| SIOTUGA estado urbanístico | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES |

## Proyectos / expedientes

- **SIOTUGA:** plan xeral + instrumentos de desarrollo vía `query_document.php` (`idclase` 14 = PG, 13 = desarrollo). Metadatos y fechas BOP; ~23 filas para Ribeira.
- **Liferay:** páginas de planeamento y PERI/PIRE con título (`<h1>`), fecha en galego/castellano y PDFs en `/documents/34600/.../*.pdf`.
- **Exposiciones públicas:** sección dedicada; enlaces cruzados a PERI y planeamento. El listado asset publisher `e68fDEVIe6E7` no expone entradas paginadas scrapeables (solo referencias en menú).
- **Obras e urbanismo:** noticias de obras públicas (asset publisher `O4qFBPDJVelD`); no se ingiere en el adapter (ruido vs. planeamiento).

## Licencias

- **No** hay registro público de licencias concedidas con fecha y ubicación.
- Trámites en sede: comunicación previa obra menor, información urbanística, licencia de segregación, proyecto de ejecución/comunicación previa (`DlgTramiteSede.aspx`, postback ASP.NET).
- El adapter ingiere filas **informativas** de trámite.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** Visor SIOTUGA (`siotuga/urb`, concello 15057) con capas de planeamento aprobado; no hay join estable código expediente → polígono para scraping automático.
- **Estrategia:** Metadatos SIOTUGA + documentos Liferay; el orquestador aplica centroide municipal (`manifest.config.centroid`) en `geocode`. No se rellena `geom_geojson` en el adapter.
- **Limitaciones:** Rutas Unicode `/tablón-de-anuncios` devuelven 404 desde el entorno del agente (contenido enlazado desde `/anuncios` también 404). Sin WFS municipal público identificado.

## Limitaciones técnicas

- Token SIOTUGA requiere CookieJar compartido con el POST a `query_document.php`.
- BOCM: sin boletín asociado en cola (`bocm_count: 0`).
- Sede: trámites sin URLs estables (solo catálogo modal).
