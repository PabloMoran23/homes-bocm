# Investigación portal — Aldea del Fresno

Municipio: **Aldea del Fresno** (`aldea-del-fresno`) — Comunidad de Madrid, provincia Madrid.  
BOCM (`bocm`): 8 entradas históricas.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.aldeadelfresno.es | WordPress TownPress (Yoast SEO, lsvrdocument) |
| Normativa municipal | https://www.aldeadelfresno.es/normativa-municipal/ | Ordenanzas fiscales y urbanísticas (enlaces BOCM) |
| Ordenanzas | https://www.aldeadelfresno.es/privada/ordenanzas/ | PDFs ordenanzas (zona baño, etc.) |
| Documentos ordenanzas | https://www.aldeadelfresno.es/documentos-categoria/ordenanzas/ | Categoría TownPress documentos |
| Bandos | https://www.aldeadelfresno.es/documentos-categoria/bandos/ | Bandos municipales |
| Sede electrónica | https://aldeadelfresno.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón anuncios | https://aldeadelfresno.sedelectronica.es/board/ | Tabla HTML (~10 filas, sin paginación) |
| Transparencia | https://aldeadelfresno.sedelectronica.es/transparency/ | Sección «7. URBANISMO (NN.SS.), MEDIO AMBIENTE Y OBRAS PÚBLICAS» |
| Trámites sede | https://aldeadelfresno.sedelectronica.es/dossier | Catálogo trámites (licencia, DR obra, cédula) |

## Cómo se listan expedientes / proyectos

1. **Normativa municipal (HTML)** — listado de ordenanzas con enlaces a PDFs del BOCM (tributos, licencias urbanísticas, construcciones auxiliares).
2. **Documentos TownPress** — CPT `lsvrdocument` con categorías (ordenanzas, bandos); mayoría actas de pleno.
3. **Visor SITCM** — 21 polígonos de ámbitos NNSS (`UE-*`, `AR-* SAU`) vía WFS GeoServer CM.
4. **Tablón sede** — HTML tabla con `preview-document/{uuid}`; en agosto 2026 predominan anuncios post-incendios y plenos (sin planeamiento activo).

No hay listado estructurado de expedientes urbanísticos en curso ni visor municipal propio.

## Cómo se publican licencias

- **No hay registro público** de licencias concedidas (listado con fecha, tipo, ubicación).
- Ordenanza fiscal de tasa por otorgamiento de licencias urbanísticas (BOCM 2014) en normativa municipal.
- Trámites informativos en sede electrónica: licencia obra, declaración responsable, cédula urbanística.
- Tablón sede podría publicar licencias pero no hay filas urbanísticas en el momento de la investigación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SITCM: https://www.madrid.org/cartografia/sitcm/html/visor.htm (municipio Aldea del Fresno)
  - WFS GeoServer IDEM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='ALDEA DEL FRESNO'` (21 features, polígonos EPSG:4326)
  - Campos: `DS_NOMB_AMB` (ej. `UE-09`, `AR-1 SAU 1`), `DS_CLAS_SUE`, `DS_FIG_DES`
- **Estrategia:** ingestar ámbitos SITCM como proyectos de planeamiento con `geom_geojson`; enriquecer filas WP/tablón si el título menciona código de ámbito (`UE-*`, `AR-*`).
- **Limitaciones:** sin geometría por expediente individual; tablón sin coords; licencias sin georreferencia; transparencia urbanismo sin documentos indexables en HTML estático.

## Limitaciones generales

- Sede requiere `insecure_ssl` en algunos entornos (certificado/redirect chain).
- Tablón ~10 filas sin paginación.
- WP sin categorías REST de urbanismo; contenido disperso en normativa y documentos.
- Sin API de expedientes; scrape determinista sobre HTML/WFS.

## Referencia adapter

Patrón: `venturada.py` / `chapineria.py` (WP + espublico sede + SITCM WFS).
