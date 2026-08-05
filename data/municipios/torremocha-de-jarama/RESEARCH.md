# Torremocha de Jarama — investigación portal ayuntamiento

## Resumen

Municipio de la Comunidad de Madrid (provincia Madrid). Portal principal en WordPress (`torremochadejarama.es`) con sede electrónica espublico (`torremochadejarama.sedelectronica.es`). No hay página dedicada `/urbanismo/`; el planeamiento se documenta en la sección **Desarrollo** y en el visor SITCM de la Comunidad de Madrid.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://torremochadejarama.es |
| Desarrollo / planeamiento | https://torremochadejarama.es/desarrollo/ |
| Proyectos fotovoltaicos | https://torremochadejarama.es/proyectos-fotovoltaicos/ |
| Sede electrónica | https://torremochadejarama.sedelectronica.es |
| Tablón de anuncios | https://torremochadejarama.sedelectronica.es/board/ |
| Portal transparencia | https://torremochadejarama.sedelectronica.es/transparency |
| Visor SITCM (enlace desde desarrollo) | https://idem.madrid.org/cartografia/sitcm/html/visor.htm |
| Expedientes Google Drive (fotovoltaicos) | https://drive.google.com/drive/folders/1t0zoE30iCT4L09AwMkNE2H4Y10OehuR7 |

## Proyectos / expedientes urbanísticos

- **WordPress /desarrollo/**: sección "Normas subsidiarias" con enlace al visor SITCM; no publica PDFs NNSS en la web.
- **SITCM WFS** (`sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='TORREMOCHA DE JARAMA'`): 16 ámbitos de planeamiento (UE-1…UE-14, API EL RETIRO DE TORREMOCHA, EL JARAL DEL PAJARITO) con geometría poligonal.
- **/proyectos-fotovoltaicos/**: documentación de proyectos Bisbita y Colimbo (DIA, BOE, carpeta Drive con alegaciones).
- **Tablón sede** (`/board/`): actualmente solo anuncios fiscales (IBI, IAE, calendario fiscal); sin licencias ni planeamiento publicados en el momento de la investigación.

Formato: HTML estático WordPress (Elementor) + tablón espublico con tabla `<tr>` y enlaces `preview-document/{uuid}`.

## Licencias de obra

No hay listado público de licencias concedidas. La sede ofrece trámites telemáticos genéricos (`/dossier`) pero sin catálogo accesible sin sesión. El adapter incluye páginas informativas (desarrollo, tablón, sede) siguiendo el patrón Pozuelo/Chapinería.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='TORREMOCHA DE JARAMA'`
  - Campos: `DS_NOMB_AMB` (nombre ámbito, p. ej. UE-3), `DS_FIG_DES`
- **Estrategia:** descarga masiva de ámbitos vía WFS GetFeature; enriquecimiento por código UE/S en título o coincidencia ILIKE sobre `DS_NOMB_AMB`.
- **Limitaciones:** tablón sin coords; licencias no publicadas; proyectos fotovoltaicos solo PDFs sin georreferencia enlazable al expediente; visor SITCM es consulta manual (no API por expediente municipal).

## Limitaciones generales

- WP REST API bloqueada o vacía para scraping automatizado.
- Tablón con muy pocos anuncios y ninguno urbanístico en la fecha de investigación.
- Sin visor urbanístico propio del ayuntamiento; dependencia del SITCM regional para polígonos de ámbito.
