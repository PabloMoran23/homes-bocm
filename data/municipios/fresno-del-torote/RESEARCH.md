# Investigación portal — Fresno del Torote

Municipio: **Fresno del Torote** (`fresno-del-torote`) — Comunidad de Madrid, provincia Madrid.  
BOCM (`bocm`): 1 entrada histórica.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://fresnodetorote.org | WordPress + Elementor |
| Ordenanzas | https://fresnodetorote.org/ordenanzas/ | PDFs ordenanzas fiscales y urbanísticas, BOCM 2024-01-22 |
| Ordenanzas municipales | https://fresnodetorote.org/ordenanzas-municipales/ | Índice ordenanzas |
| Sede electrónica | https://sede.fresnodetorote.es | Maggioli ATM (Angular SPA) |
| Transparencia | https://transparencia.fresnodetorote.es | **No disponible** (portalNoDisponible.aspx) |
| Plan General (IDEM) | https://idem.madrid.org/cartografia/planea/planeamiento/planeamiento/Fresno_de_Torote/Vigente/Torote_a.pdf | NNSS 1991 |

## Cómo se listan expedientes / proyectos

1. **WordPress REST API** — categorías `urbanismo` (89) y `obras-y-servicios` (41): noticias de obras, suelo, parcelas.
2. **Página ordenanzas** — PDFs embebidos (BOCM, tasas urbanísticas, licencias).
3. **Visor SITCM / WFS IDEM** — 20 ámbitos únicos de planeamiento (`AA-*`, `S-*`, `AE-*`) con polígonos EPSG:4326.
4. **Sede Maggioli** — tablón de anuncios en SPA Angular; sin HTML/API pública scrapeable.

No hay listado estructurado de expedientes urbanísticos en curso ni visor municipal propio.

## Cómo se publican licencias

- **No hay registro público** de licencias concedidas (listado con fecha, tipo, ubicación).
- Ordenanzas en web: licencia de apertura, tasa licencias urbanísticas, primera ocupación, IICO.
- Trámites telemáticos vía sede Maggioli (requiere identificación).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SITCM: https://idem.madrid.org/cartografia/sitcm/html/visor.htm (municipio Fresno de Torote)
  - WFS GeoServer IDEM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='FRESNO DE TOROTE'` (28 features, ~20 ámbitos únicos)
  - Campos: `DS_NOMB_AMB` (ej. `S-6 EL PONTON`, `AA-01 FRESNO`), `DS_FIG_DES`, `DS_CLAS_SUE`
- **Estrategia:** ingestar ámbitos SITCM como proyectos de planeamiento con `geom_geojson`; enriquecer noticias WP si el título menciona nombre de ámbito o urbanización.
- **Limitaciones:** sin geometría por expediente individual; sede SPA sin tablón scrapeable; transparencia no disponible; licencias sin georreferencia.

## Limitaciones generales

- Sede Maggioli ATM: SPA Angular, tablón no accesible por scrape HTML.
- Portal transparencia devuelve «PORTAL NO DISPONIBLE».
- WP noticias urbanismo mezcladas con obras municipales (alumbrado, asfalto, etc.) — filtro por regex.
- Nombre WFS `FRESNO DE TOROTE` (no «del»).
- Sin API de expedientes; scrape determinista sobre WP REST + WFS.

## Referencia adapter

Patrón: `estremera.py` / `venturada.py` (WP + sede Maggioli + SITCM WFS).
