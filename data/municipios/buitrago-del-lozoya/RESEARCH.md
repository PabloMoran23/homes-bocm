# Buitrago del Lozoya — investigación portal ayuntamiento

**Municipio:** Buitrago del Lozoya (Comunidad de Madrid)  
**Fecha:** 2026-08-02  
**BOCM regional (referencia):** 11 avisos

## Resumen

Buitrago del Lozoya publica planeamiento y normativa urbanística en su **web municipal Joomla**
(`www.buitrago.org`) y gestiona trámites en la **sede electrónica espublico gestiona**
(`buitragodellozoya.sedelectronica.es`). Los ámbitos de planeamiento municipal están en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Urbanismo (normativa) | `https://www.buitrago.org/normativa/urbanismo` | Joomla categoría + RSS | PGOU, NNSS, plan parcial SAU-1, modificaciones puntuales, PE infraestructuras |
| Tablón municipal | `https://www.buitrago.org/inicio/tablon-municipal` | Joomla categoría + RSS | Bandos, exposiciones públicas, anuncios BOCM |
| Trámites urbanismo | `https://www.buitrago.org/tramites/de-urbanismo` | Joomla HTML + PDFs | Formularios licencia obra menor/mayor, parcelación, actos menores |
| Tablón sede | `https://buitragodellozoya.sedelectronica.es/board/` | HTML espublico | Tablón de anuncios electrónico |
| Transparencia | `https://transparencia.buitrago.org/` | Portal externo | Documentación administrativa |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 18 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='BUITRAGO DEL LOZOYA'` |
| Visor SIT | `https://idem.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS web | Enlace desde menú Normativa |

## Cómo se listan expedientes

- **Planeamiento:** artículos Joomla en categoría `/normativa/urbanismo` con PDFs embebidos
  (`/images/stories/URBANISMO/...`). Feed RSS disponible (`?format=feed&type=rss`).
- **Tablón municipal:** artículos Joomla paginados (`?start=N`) con PDFs en descripción RSS.
- **Tablón sede:** tabla HTML espublico con columnas Documento/Expediente/Procedimiento/Categoría/Fecha.
- **No hay** visor urbanístico propio del ayuntamiento ni API JSON de expedientes.

## Licencias

- Formularios PDF en `/tramites/de-urbanismo` (obra menor/mayor, parcelación, actos menores).
- No hay dataset histórico de concesiones con coordenadas.
- Anuncios de licencia aparecerían en tablón municipal o sede cuando se publiquen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='BUITRAGO DEL LOZOYA'` (`srsName=EPSG:4326`)
  - Visor SIT CM enlazado desde menú Normativa
  - 18 ámbitos: SAU-1/2/3, UG-1..UG-14 (unidades de gestión), etc.
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson`; enriquecer proyectos Joomla
  cuando el título contiene código SAU/UG o nombre de ámbito SIT.
- **Limitaciones:** PDFs sin georreferenciación directa; licencias solo como formularios informativos;
  transparencia en dominio separado no automatizable en CI.

## Limitaciones

- Tablón sede con pocos anuncios urbanísticos activos (mayoría administrativos).
- Licencias solo como páginas de trámite, sin concesiones publicadas con coordenadas.
- PDFs de planeamiento sin enlace a expediente GIS individual.
- Dominio turístico `buitragodelozoya.es` no es web oficial del ayuntamiento.

## Estrategia adapter

1. Parsear feeds RSS Joomla (urbanismo + tablón municipal).
2. Crawl categorías Joomla con paginación y extraer PDFs de artículos.
3. Semillas de ámbitos SIT WFS (18 figuras) con `geom_geojson`.
4. Tablón sede espublico + páginas informativas de licencias.
5. IDs: `buitrago-del-lozoya-{lic|proy}-{sha256[:14]}`.
