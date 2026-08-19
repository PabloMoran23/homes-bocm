# Investigación portal — Miraflores de la Sierra

Municipio: **Miraflores de la Sierra** (`miraflores-de-la-sierra`) — Comunidad de Madrid, provincia Madrid.  
BOCM (`bocm`): 6 entradas históricas.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.mirafloresdelasierra.es | WordPress + PixFort/Elementor (Yoast SEO) |
| Urbanismo | https://www.mirafloresdelasierra.es/servicios-municipales/urbanismo/ | Tabs Elementor: normas urbanísticas, guía licencias, PDFs trámites |
| Solicitudes e inscripciones | https://www.mirafloresdelasierra.es/tramites/solicitudes-e-inscripciones/ | Impresos licencia obra mayor/menor, primera ocupación, terrazas |
| Ordenanzas | https://www.mirafloresdelasierra.es/ayuntamiento/ordenanzas-municipales/ | Ordenanzas municipales |
| Sede electrónica | https://mirafloresdelasierra.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón anuncios | https://mirafloresdelasierra.sedelectronica.es/board/ | ~10 filas HTML tabla (empleo, plenos; sin urbanismo activo) |
| Consulta expedientes | https://mirafloresdelasierra.sedelectronica.es/expedientes | Búsqueda por código (requiere identificación para detalle) |
| Trámites sede | https://mirafloresdelasierra.sedelectronica.es/dossier | Catálogo trámites (licencia obra, DR, cédula) |

## Cómo se listan expedientes / proyectos

1. **Página urbanismo (Elementor tabs)** — PDFs estáticos: normas urbanísticas, planos NNSS, guía tramitación licencias/expedientes, solicitudes obra mayor/menor.
2. **Página solicitudes** — Impresos y documentación para licencias (obra mayor/menor, primera ocupación, terrazas, actividad).
3. **Visor SITCM** — 37 polígonos de ámbitos de planeamiento (`PU-*`, `PP-*`) vía WFS GeoServer CM.
4. **Tablón sede** — HTML tabla con `preview-document/{uuid}`; actualmente sin entradas de planeamiento (empleo, plenos).

No hay listado estructurado de expedientes urbanísticos en curso ni API pública de información pública por código.

## Cómo se publican licencias

- **No hay registro público** de licencias concedidas (listado con fecha, tipo, ubicación).
- Trámites informativos en web (PDFs solicitud/documentación) + sede electrónica.
- Tablón sede podría publicar licencias pero no hay filas urbanísticas en el momento de la investigación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SITCM: https://idem.madrid.org/cartografia/sitcm/html/visor.htm (municipio Miraflores de la Sierra)
  - WFS GeoServer IDEM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='MIRAFLORES DE LA SIERRA'` (37 features, polígonos EPSG:4326)
  - Campos: `DS_NOMB_AMB` (ej. `PU-22 LA DEHESILLA NORTE`, `PP-9 LAS ZAHURDAS I`), `DS_CLAS_SUE`, `DS_FIG_DES`
- **Estrategia:** ingestar ámbitos SITCM como proyectos de planeamiento con `geom_geojson`; enriquecer filas WP/tablón si el título menciona código de ámbito (`PU-*`, `PP-*`) o nombre de zona.
- **Limitaciones:** sin geometría por expediente individual; tablón sin coords; licencias sin georreferencia; consulta expedientes requiere login para detalle.

## Limitaciones generales

- Dominio legacy `mirafloresdelasierra.es` (sin www) en algunos PDFs de urbanismo.
- Tablón ~10 filas sin paginación; contenido mayoritariamente empleo/plenos.
- Sin API de expedientes; scrape determinista sobre HTML/WFS.
- Categoría WP `tablon-de-anuncios` (id 18) sin posts publicados.

## Referencia adapter

Patrón: `venturada.py` / `patones.py` (WP + espublico sede + SITCM WFS).
