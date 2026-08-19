# La Victoria de Acentejo — investigación portal ayuntamiento

Municipio: **La Victoria de Acentejo** (`la-victoria-de-acentejo`)  
Provincia: Santa Cruz de Tenerife · CCAA: Canarias  
Código INE municipio (Grafcan): `38045`

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (WordPress Divi / echeide) | https://www.lavictoriadeacentejo.es/ | CMS principal |
| Urbanismo | https://www.lavictoriadeacentejo.es/servicios-municipales/urbanismo/ | Índice área urbanismo |
| Participación ciudadana | https://www.lavictoriadeacentejo.es/servicios-municipales/urbanismo/participacion-ciudadana/ | 14 expedientes de planeamiento (WP parent=5500) |
| Normativa | https://www.lavictoriadeacentejo.es/servicios-municipales/urbanismo/normativa/ | PDFs NNSS (dominio legacy `.com`) |
| Licencias | https://www.lavictoriadeacentejo.es/servicios-municipales/urbanismo/licencias/ | Trámites informativos (sin listado concedidas) |
| Comunicación previa | `/servicios-municipales/urbanismo/comunicacion-previa/` | Régimen comunicación previa |
| PMUS | `/servicios-municipales/urbanismo/plan-de-movilidad-urbana-sostenible-pmus/` | Plan movilidad urbana |
| Sede electrónica (ATM-Maggioli) | http://sede.lavictoriadeacentejo.es/ | Angular SPA — procedimientos, contratación |
| WP REST API | `https://www.lavictoriadeacentejo.es/wp-json/wp/v2/pages` | Listado determinista de páginas urbanismo |

## Cómo se listan expedientes / proyectos

- **WordPress REST API:** páginas hijas de `participacion-ciudadana` (parent id 5500) con título, fecha (`date`), enlace y PDFs embebidos en HTML Divi.
- Expedientes recientes: modificación NNSS entorno Los Cercados (2025), modificación menor transversal La Resbala (2022), alteración planeamiento El Arrayanero (2020), ordenanzas municipales (2019).
- **Normativa:** 16 PDFs de Normas Subsidiarias y planos en `lavictoriadeacentejo.com/archivos/pgo/`.
- **No hay** visor de expedientes urbanísticos ni API JSON de proyectos en curso.

## Cómo se publican licencias

- **No hay** listado público de licencias concedidas (tablón con decreto/coords).
- Secciones informativas: licencias, comunicación previa, actuaciones exentas, otros títulos.
- Sede ATM-Maggioli: catálogo de procedimientos (SPA sin API pública scrapeable).
- El adapter devuelve filas informativas de trámites; `min_rows: 0` para licencias reales.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** IDECanarias/Grafcan embed municipal (`http://visor.grafcan.es/ol3/grafcan/embed_mun.php?mun=38045`) — capas WMS callejero/catastro. Participación ciudadana incluye mapas JPG estáticos (`mapa_participacion.jpg`) sin georreferencia.
- **Estrategia:** el visor catastral permite localizar parcelas pero **no** expone consulta por código de expediente ni polígonos de ámbitos de planeamiento enlazables al portal.
- **Limitaciones:** sin ArcGIS REST/WFS público con geometría de expedientes; proyectos publicados como HTML/PDF. El orquestador usará centroide municipal + jitter.

## Limitaciones generales

- Sede ATM-Maggioli: SPA Angular sin tablón `/board/` scrapeable (a diferencia de espublico).
- PDFs NNSS legacy en dominio `lavictoriadeacentejo.com` (distinto del dominio principal `.es`).
- Sin re-parse BOCM; 5 entradas en `boc_canarias` ya en `projects.json`.
