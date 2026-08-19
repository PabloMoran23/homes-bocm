# Canencia — investigación portal ayuntamiento

**Municipio:** Canencia (Comunidad de Madrid)  
**Fecha:** 2026-08-06  
**BOCM regional (referencia):** 7 avisos

## Resumen

Canencia publica información urbanística en su **web municipal Joomla** (`www.canencia.es`,
plantilla LT Company + icagenda para tablón) y gestiona trámites en la **sede electrónica
espublico gestiona** (`canencia.sedelectronica.es`). Los ámbitos de planeamiento están en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`, código municipio 034).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Planeamiento urbanístico | `/tu-ayuntamiento/normativa-municipal/planeamiento-urbanistico` | Joomla artículo + PDF | Modificación puntual NNSS cementerio (BOCM 2018) |
| Trámites urbanismo | `/ciudadanos/tramites-personales/urbanismo` | Joomla HTML + PDFs | Formularios licencia obra menor/mayor |
| Tablón municipal | `/ciudadanos/tablon-municipal` | Joomla icagenda + RSS | Bandos, anuncios (imágenes JPG, pocos PDFs urbanísticos) |
| Ordenanzas | `/tu-ayuntamiento/normativa-municipal/ordenanzas-municipales` | Joomla categoría + RSS | Ordenanzas municipales |
| Sede electrónica | `https://canencia.sedelectronica.es/info.0` | espublico gestiona | Trámites y registro |
| Tablón sede | `https://canencia.sedelectronica.es/board` | HTML espublico | Tablón vacío (sin filas) |
| Transparencia sede | `https://canencia.sedelectronica.es/transparency` | Wicket AJAX | Sección URBANISMO (0 docs) |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 15 ámbitos (`UE-1`…`UE-14`, `SAU-1`) |
| Visor SIT | `http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=034` | ArcGIS web | Enlace desde planeamiento |

## Cómo se listan expedientes

- **Planeamiento:** página estática Joomla con PDF BOCM embebido y enlace a Google Drive del proyecto.
- **Tablón municipal:** artículos icagenda paginados (`?start=N`) con imágenes JPG; feed RSS
  (`?format=feed&type=rss`).
- **Tablón sede:** tabla espublico vacía; transparencia con Wicket no scrapeable.
- No hay visor urbanístico propio ni API JSON de expedientes.

## Licencias

- Formularios PDF en `/ciudadanos/tramites-personales/urbanismo` (obra menor y mayor).
- No hay dataset histórico de concesiones con coordenadas.
- Tablón actual sin licencias urbanísticas publicadas (bandos administrativos, empleo, etc.).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='CANENCIA'` (`srsName=EPSG:4326`)
  - Visor SIT CM enlazado desde página de planeamiento (`municipio=034`)
  - 15 ámbitos: `UE-1` … `UE-14` (unidades de ejecución) y `SAU-1`
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson`; enriquecer proyectos cuando
  el título contiene código UE/SAU o nombre de ámbito SIT.
- **Limitaciones:**
  - Tablón municipal publica imágenes JPG sin georreferencia.
  - PDFs de planeamiento sin enlace a expediente GIS individual.
  - Tablón sede y transparencia sin documentos urbanísticos activos.
  - Geometría solo para ámbitos SITCM identificables por código en título.

## Limitaciones generales

- Municipio pequeño (Sierra Norte); pocos anuncios urbanísticos activos en tablón.
- Licencias solo como formularios informativos, sin concesiones publicadas.
- CMS Joomla con icagenda; mayoría de tablón son bandos no urbanísticos.

## Estrategia adapter

1. Semillas WFS SITCM (15 ámbitos con polígono).
2. Semilla planeamiento NNSS cementerio (PDF BOCM 2018).
3. RSS tablón + crawl artículos Joomla (filtrar urbanismo/desbroce parcelas/rehabilitación).
4. Formularios licencia desde página urbanismo.
5. Tablón sede (vacío; se intenta parsear por si se publican anuncios).
