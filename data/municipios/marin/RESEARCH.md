# Marín — investigación portal ayuntamiento

Municipio: **Marín** (`marin`) — Galicia, provincia Pontevedra (Ría de Pontevedra).  
INE: **36037**. Sin boletín asociado en cola (`bocm_count: 0`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.concellodemarin.es/ | WordPress (Yoast, categorías). |
| Urbanismo | https://www.concellodemarin.es/urbanismo/ | Concellería de Urbanismo, enlaces a PXOM y servizos. |
| PXOM | https://www.concellodemarin.es/urbanismo/pxom/ | Texto informativo PXOM aprobado 2012 (sin visor embebido). |
| Edictos | https://www.concellodemarin.es/edictos/ | Anuncios administrativos (PDFs puntuales, no tablón estructurado). |
| Impresos oficiais | https://www.concellodemarin.es/impresos-oficiais/ | Formularios URBANISMO (licenza, comunicación previa, primeira ocupación, tasas). |
| Oficina ARI | https://www.concellodemarin.es/urbanismo/oficina-ari/ | Áreas de rehabilitación integral (Casco Vello, Banda do Río Lameira). |
| REST WP | https://www.concellodemarin.es/wp-json/wp/v2/posts?categories=10 | Categoría **Urbanismo** (id 10), ~265 entradas; filtro por keywords de planeamiento. |
| Sede electrónica | https://sede.concellodemarin.es/ | ASP.NET (`Default.aspx`, login Cl@ve/certificado). **Timeout** desde el entorno del agente (documentado). |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36037&lang=es_ES | POST `query_document.php` (clases 14 PG, 13 desarrollo) + token de sesión. |
| SIOTUGA estado | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | Estado normativo municipal en cartografía Xunta. |
| SIOTUGA visor | https://siotuga.xunta.gal/siotuga/visor | Visor cartográfico autonómico (capas por instrumento, no por expediente local). |

## Expedientes / proyectos

- **Noticias WP (cat. Urbanismo):** titulares sobre PXOM, Plan Especial de Protección (casco/Cantodarea), PMUS, estudios de detalle, aprobaciones Xunta, etc. Fecha = `date` del post; URL estable del permalink.
- **SIOTUGA:** 3 docs clase 14 (normas subsidiarias, PXOM…) y 2 clase 13 (p. ej. solo industrial Amoedo, plan parcial) con metadatos `docnome`, `figura`, fechas BOP/DOG.
- **Edictos / sede:** no hay listado HTML de expedientes urbanísticos con código `EXP` enlazable (sede inaccesible en crawl automatizado).
- **Estrategia adapter:** semillas fijas + SIOTUGA + posts WP filtrados (`RE_PROYECTO` / exclusión de obras viarias, axudas, orzamentos).

## Licencias

- **No** hay dataset ni tablón sistemático de licencias concedidas con dirección/coordenadas.
- Trámites descritos en **impresos oficiais** (URBANISMO) y presentación telemática vía sede (certificado / Cl@ve).
- Estrategia: filas informativas de trámites + PDF tasas urbanismo (patrón Carballo/Vilagarcía).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIOTUGA visor / `urb`: cartografía de instrumentos de planeamiento por INE 36037, no por título de noticia WP ni código de expediente municipal.
  - Web municipal: sin visor SIG ni GeoJSON en datos abiertos.
  - Sede: sin geometría en listados (y no accesible en el entorno de prueba).
- **Estrategia:** metadatos de planeamiento vía SIOTUGA + noticias WP; el adapter **no** rellena `geom_geojson` (sin join estable documento↔polígono). Orquestador: centroide municipio + jitter.
- **Limitaciones:** SIOTUGA requiere cookie jar + token; WMS legacy (`getIotpuWMS.php`) no disponible en host actual (404).

## Limitaciones técnicas

- Dominio `.gal` del concello redirige mal desde algunos entornos; usar **concellodemarin.es**.
- Sede `sede.concellodemarin.es`: conexión vacía/timeout en agente cloud (no `insecure_ssl`).
- WP REST: paginación 100×N; filtro heurístico para excluir noticias de obras sin planeamiento.
