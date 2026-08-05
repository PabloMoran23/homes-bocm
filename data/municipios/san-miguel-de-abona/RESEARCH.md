# San Miguel de Abona — investigación portal ayuntamiento

Municipio: **San Miguel de Abona** (`san-miguel-de-abona`)  
Provincia: Santa Cruz de Tenerife · CCAA: Canarias  
Código INE municipio (Grafcan): `38035`

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (WordPress) | https://www.sanmigueldeabona.es/ | Noticias, áreas, formularios |
| Sede electrónica (Galileo) | https://sede.sanmigueldeabona.es/ | Trámites, edictos, ordenanzas, territorio |
| Modelos y formularios | https://www.sanmigueldeabona.es/modelos-formularios/ | PDFs solicitud licencias urbanísticas (120, 130, 131, 311…) |
| Información pública | `/2026/06/29/informacion-publica-3/`, `/2025/10/06/informacion-publica-2/`, `/2022/11/05/informacion-publica/` | Anuncios IP con PDFs (PAMU Las Zocas, presupuesto, etc.) |
| PGO supletorio | Posts 2014–2026 sobre plan general supletorio | Noticias + PDFs BOC/BOP |
| Mapas / callejero | https://www.sanmigueldeabona.es/mapas/ | Enlace visor IDECanarias |
| Edictos RSS | https://sede.sanmigueldeabona.es/publico/sindicacion/edictos/RSS | Sindicación edictos (pocos ítems activos) |
| Procedimientos | https://sede.sanmigueldeabona.es/publico/procedimientos | Catálogo trámites (licencias, planeamiento) |
| Informe urbanístico | https://sede.sanmigueldeabona.es/publico/territorio/informeurbanistico | Trámite consulta urbanística |

## Cómo se listan expedientes / proyectos

- **WordPress:** posts de «información pública» y noticias de planeamiento (PGO supletorio, PAMU Las Zocas) con PDFs en `wp-content/uploads/`. Descubrimiento vía sitemap (`post-sitemap*.xml`) filtrando URLs con `informacion-publica`, `plan-general`, `pgo`, etc.
- **Sede Galileo:** tablón de edictos en HTML + RSS; sin API JSON pública. El RSS solo contiene entradas históricas (p. ej. acuerdos de pleno 2014).
- **No hay** visor de expedientes urbanísticos ni listado tabular de proyectos en curso como en Drupal/espublico.

## Cómo se publican licencias

- **No hay** listado público de licencias concedidas (decreto, tablón con coords, etc.).
- Trámites documentados en **modelos-formularios** (obra mayor 120, obra menor 130, comunicación previa 131, segregación 311…).
- Sede: catálogo de procedimientos y carpeta ciudadana (requiere certificado).
- El adapter devuelve filas informativas de trámites + formularios; `min_rows: 0` aceptable para licencias reales.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** IDECanarias/Grafcan embed municipal (`http://visor.grafcan.es/ol3/grafcan/embed_mun.php?mun=38035`) — capas WMS callejero/catastro (`wms_MIX`, `wms_CA`, `wms_TOPO`). Visor general: http://visor.grafcan.es/visorweb/
- **Estrategia:** el visor permite localizar vías/parcelas catastrales pero **no** expone consulta por código de expediente ni polígonos de ámbitos de planeamiento enlazables al portal municipal.
- **Limitaciones:** sin ArcGIS REST/WFS público con geometría de expedientes; proyectos publicados solo como PDF/noticia. El orquestador usará centroide municipal + jitter.

## Limitaciones generales

- Sede Galileo: edictos sin paginación scrapeable fiable (datatables vacío en CI); RSS con muy pocos ítems.
- WordPress: algunos PDFs antiguos en dominio legacy `sanmiguetp.cluster002.ovh.net`.
- Sin re-parse BOCM; 11 entradas en `boc_canarias` ya en `projects.json`.
