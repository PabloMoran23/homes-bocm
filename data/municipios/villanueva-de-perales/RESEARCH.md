# Investigación portal — Villanueva de Perales

Municipio: **Villanueva de Perales** (`villanueva-de-perales`) — Comunidad de Madrid, provincia Madrid.  
BOCM (`bocm`): 7 entradas históricas.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.villanuevadeperales.es | WordPress Avada (tema VDP 2.0, iDEA) |
| Área urbanismo | https://www.villanuevadeperales.es/areas/urbanismo/ | Informe técnico OTM, estadísticas expedientes |
| Trámites urbanismo | https://www.villanuevadeperales.es/tramites/urbanismo/ | Formularios PDF (obra mayor/menor, vado, 1ª ocupación) |
| Sede electrónica | https://villanuevadeperales.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón anuncios | https://villanuevadeperales.sedelectronica.es/board | ~3 filas (calendario fiscal, fiestas locales) |
| Transparencia | https://villanuevadeperales.sedelectronica.es/transparency/ | Carpeta «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» vacía (0 docs) |
| Tributos | https://villanuevadeperales.gestiondetributos.es | Sede tributaria (no urbanismo) |

## Cómo se listan expedientes / proyectos

1. **WordPress REST API** — categoría `urbanismo` (id 165, 25 posts): noticias de obras municipales, visitas institucionales.
2. **Página área urbanismo** — informe anual de la Oficina Técnica Municipal (HTML estático, sin PDFs de planeamiento).
3. **WFS SITCM** — 15 ámbitos de planeamiento (`SAU-1`…`SAU-10`, `UE-1`…`UE-5`) vía GeoServer Comunidad de Madrid.
4. **Tablón sede** — HTML tabla con `preview-document/{uuid}`; sin entradas de planeamiento ni información pública en el momento de la investigación.

No hay listado estructurado de expedientes urbanísticos en curso, visor propio del ayuntamiento ni datos abiertos de planeamiento.

## Cómo se publican licencias

- **No hay registro público** de licencias concedidas (fecha, tipo, ubicación).
- Formularios descargables en `/tramites/urbanismo/`: instancia general, obra mayor, obra menor, vado, primera ocupación.
- Sede espublico (`/info.0`, `/expedientes`) requiere certificado/Pin24h para trámites y consulta de expedientes.
- Tablón sede podría publicar licencias pero no hay filas urbanísticas actualmente.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SITCM: https://idem.madrid.org/cartografia/sitcm/html/visor.htm (municipio Villanueva de Perales)
  - WFS GeoServer IDEM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='VILLANUEVA DE PERALES'` (15 features, polígonos EPSG:4326)
  - Campos: `DS_NOMB_AMB` (ej. `SAU-1`, `UE-3`), `DS_CLAS_SUE`, `DS_FIG_DES`
- **Estrategia:** ingestar los 15 ámbitos SITCM como proyectos de planeamiento con `geom_geojson`; enriquecer filas WP/tablón si el título menciona código SAU/UE.
- **Limitaciones:** sin geometría por expediente individual; tablón sin coords; licencias sin georreferencia; transparencia urbanismo vacía; web sin PDFs de PGOU/NNSS.

## Limitaciones generales

- Sede espublico accesible sin `insecure_ssl` en este entorno.
- Tablón con pocas filas, mayormente administrativas (BOCM fiscal, consumo).
- WP categoría urbanismo mezcla noticias de obras con visitas institucionales (filtro RE_PROYECTO).
- Sin API de expedientes; scrape determinista sobre HTML/WFS.

## Referencia adapter

Patrón: `los_santos_de_la_humosa.py` (WP Avada + espublico sede + SITCM WFS).
