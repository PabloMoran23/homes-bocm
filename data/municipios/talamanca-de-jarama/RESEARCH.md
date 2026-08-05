# Talamanca de Jarama — investigación portal ayuntamiento

**Municipio:** Talamanca de Jarama (Comunidad de Madrid)  
**Fecha:** 2026-08-05  
**BOCM regional (referencia):** 9 avisos

## Resumen

Talamanca de Jarama publica trámites y anuncios en la **sede electrónica espublico gestiona**
(`talamancadejrama.sedelectronica.es`, dominio sin la «a» de Jarama) y documentación de
planeamiento en la **web municipal WordPress** (`talamancadejarama.org`). Los ámbitos de
planeamiento están en el **SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.talamancadejarama.org` | WordPress | Noticias, administración, impresos |
| Normas subsidiarias | `https://www.talamancadejarama.org/administracion/normas-subsidiarias/` | HTML + PDF | NNSS 2006, planos ordenación, RAT 2024 |
| Impresos municipales | `https://www.talamancadejarama.org/impresos/*` | CPT WordPress | Formularios licencia obra, declaración responsable, primera ocupación |
| Tablón de anuncios | `https://talamancadejrama.sedelectronica.es/board` | HTML tabla espublico | Anuncios recientes (pocos en agosto 2026) |
| Portal transparencia | `https://talamancadejrama.sedelectronica.es/transparency` | Wicket | Sin sección urbanismo scrapeable |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | ~24 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='TALAMANCA DE JARAMA'` |
| VisualUrb (tercero) | `https://www.visualurb.es/talamanca-del-jarama-*` | HTML | Referencia histórica de modificaciones NNSS (no API) |

## Tablón de anuncios (`/board`)

Tabla HTML responsive con columnas: Documento, Expediente, Procedimiento, Categoría,
Descripción, Fecha de Publicación. Enlaces `preview-document/{uuid}` (PDF). En agosto 2026
solo consta un anuncio de empleo público; búsqueda por «urbanismo» no filtra (formulario
Wicket no procesa POST externo de forma fiable).

## Licencias

- **Impresos WP** (`/impresos/`): solicitud licencia obra mayor/menor, declaración
  responsable, primera ocupación, consulta técnica, ocupación zonas públicas, terrazas.
- **Sede `/dossier`**: bucle de redirección 302 (`.0`); catálogo `/catalog` devuelve 404.
- No hay dataset histórico de concesiones con coordenadas.
- Anuncios de licencia aparecen en tablón cuando se publican.

## Proyectos / planeamiento

- **NNSS:** PDFs en `wp-content/uploads/2022/10/` (normas urbanísticas, ordenación,
  ámbitos protección) + RAT 2024 (`uploads/2024/07/RAT-2024.pdf`).
- **SIT WFS:** 24 ámbitos únicos UE-*, S-* con polígonos WGS84.
- Modificaciones puntuales (p. ej. rotonda Valdepiélagos) se publican en BOCM y VisualUrb;
  no hay listado estructurado en el portal municipal.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='TALAMANCA DE JARAMA'` (`srsName=EPSG:4326`)
  - Visor regional SIT CM: `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm`
  - Planos PDF en normas subsidiarias (sin georreferenciación vectorial)
- **Estrategia:** Semillas de ámbitos desde WFS; enriquecer por código UE/S en título cuando
  coincida con `DS_NOMB_AMB`.
- **Limitaciones:** Sin visor ArcGIS propio; tablón con pocos anuncios; `/dossier` inaccesible
  por redirección; transparencia Wicket sin scrape estable; licencias sin GIS enlazable.

## Limitaciones

- Dominio sede `talamancadejrama.sedelectronica.es` (typo histórico sin «a»).
- `/dossier` y `/catalog` no operativos para scraping automatizado.
- Tablón muestra solo anuncios vigentes (~1 fila en agosto 2026).
- No hay página dedicada «Urbanismo» en la web; planeamiento disperso en NNSS e impresos.

## Estrategia adapter

1. Scrape tablón `/board` (tabla data-label + fallback enlaces preview-document).
2. Impresos WP desde sitemap `wp-sitemap-posts-impresos-1.xml` (trámites licencia).
3. PDFs NNSS desde normas subsidiarias como proyectos de planeamiento.
4. Semillas de ámbitos SIT WFS con `geom_geojson`.
5. Páginas informativas de referencia (tablón, normas subsidiarias, impresos).
6. IDs: `talamanca-de-jarama-{lic|proy}-{sha256[:14]}`.
