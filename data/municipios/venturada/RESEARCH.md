# Investigación portal — Venturada

Municipio: **Venturada** (`venturada`) — Comunidad de Madrid, provincia Madrid.  
BOCM (`bocm`): 11 entradas históricas.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://venturada.org | WordPress + Elementor (Yoast SEO) |
| Área urbanismo | https://venturada.org/areas/urbanismo/ | NNSS, trámites, enlace visor SITCM |
| Ordenanzas | https://venturada.org/normativa/ordenanzas/ | PDFs BOCM de ordenanzas + fichas resumen |
| Licencias | https://venturada.org/licencia-reformas/ | Info licencias reformas → sede |
| Trámites | https://venturada.org/tramites/ | Impresos y enlaces sede |
| Sede electrónica | https://venturada.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón anuncios | https://venturada.sedelectronica.es/board/ | ~10 filas HTML tabla (sin paginación) |
| Transparencia | https://venturada.sedelectronica.es/transparency/ | 0 docs en «Urbanismo, obras y medio ambiente» |
| Trámites sede | https://venturada.sedelectronica.es/dossier | Catálogo trámites (licencia, DR obra, cédula) |

## Cómo se listan expedientes / proyectos

1. **WordPress REST API** — categorías `urbanismo` (40), `urbanismo-y-obras` (19), `bandos-municipales` (73): JSON con título, fecha, enlace.
2. **Páginas estáticas Elementor** — PDFs embebidos/enlazados (ordenanzas BOCM, fichas resumen).
3. **Visor SITCM** — 57 polígonos de ámbitos NNSS (`ZONA-N … POLÍGONO M`) vía WFS GeoServer CM.
4. **Tablón sede** — HTML tabla con `preview-document/{uuid}`; actualmente sin entradas de planeamiento (empleo, plenos, deportes).

No hay listado estructurado de expedientes urbanísticos en curso ni información pública por código de expediente.

## Cómo se publican licencias

- **No hay registro público** de licencias concedidas (listado con fecha, tipo, ubicación).
- Trámites informativos en web + sede: licencia obra, declaración responsable obra menor, cédula urbanística.
- Tablón sede podría publicar licencias pero no hay filas urbanísticas en el momento de la investigación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SITCM: https://idem.madrid.org/cartografia/sitcm/html/visor.htm (municipio Venturada)
  - WFS GeoServer IDEM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='VENTURADA'` (57 features, polígonos EPSG:4326)
  - Campos: `DS_NOMB_AMB` (ej. `ZONA-1 CASCO TRADICIONAL. POLÍGONO 24`), `DS_CLAS_SUE`, `DS_FIG_DES`
- **Estrategia:** ingestar ámbitos SITCM como proyectos de planeamiento con `geom_geojson`; enriquecer filas WP/tablón si el título menciona código de ámbito o nombre de zona.
- **Limitaciones:** sin geometría por expediente individual; tablón sin coords; licencias sin georreferencia; transparencia urbanismo vacía.

## Limitaciones generales

- Sede requiere `insecure_ssl` en algunos entornos (certificado/redirect chain).
- Tablón ~10 filas sin paginación.
- WP noticias urbanismo mezcladas con obras municipales (cortes luz, licitaciones).
- Sin API de expedientes; scrape determinista sobre HTML/WFS.

## Referencia adapter

Patrón: `villavieja_del_lozoya.py` / `patones.py` (WP + espublico sede + SITCM WFS).
