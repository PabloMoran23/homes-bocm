# Alicante — investigación portal ayuntamiento

**Municipio:** Alicante (capital, Alicante, Comunitat Valenciana)  
**Slug:** `alicante`  
**Boletín:** DOGV (`dogv`, 3 entradas en histórico BOCM)

## URLs base y páginas semilla

| Fuente | URL | Tecnología | Contenido |
|--------|-----|------------|-----------|
| Web corporativa | `https://www.alicante.es` | Drupal 7 | Urbanismo, trámites, noticias |
| Urbanismo y vivienda | `/es/area-tematica/urbanismo-y-vivienda` | Drupal | Enlaces a normativa, modificaciones |
| Modificaciones en tramitación | `/es/contenidos/modificaciones-del-planeamiento-tramitacion` | Drupal | MP 52/53 activas (enlaces a IP) |
| Portal PGMOA 1987 | `https://w3.alicante.es/urbanismo/pgmoa-1987/` | PHP + Bootstrap | **331 expedientes** (PAI, UA, PP, adaptaciones) |
| Listado por tipos | `.../vista_tipos.php` | HTML scrapeable | `consulta.php?codigo=N` + descripción |
| Ficha expediente | `.../consulta.php?codigo=N` | PHP | Tramitación, PDFs plano ámbito/ordenación |
| Sede electrónica | `https://sedeelectronica.alicante.es` | PHP propio | Tablón edictos municipales |
| Edictos | `/edictos.php` + RSS `/rss/rss20/edictos.rss` | HTML/RSS | Exposición pública (planeamiento, licencias puntuales) |
| Guía Urbana | `https://guiaurbana.alicante.es` | Angular + GeoServer WMS | Callejero, ortofotos, capa `pgou87` |
| Trámites urbanismo | `/es/tramites/urbanismo-y-vivienda` | Drupal | Procedimientos informativos (licencias) |
| Sede ALI | `https://ali.alicante.es` | — | **En mantenimiento** (ago 2026) |

## Cómo se listan expedientes

### Portal PGMOA (`w3.alicante.es`)

- `vista_tipos.php`: listado agrupado por tipo (Adaptación PGMOU, Plan Parcial, UA, etc.).
- Cada ítem: enlace `consulta.php?codigo={id}` con título y descripción breve.
- `consulta.php`: ficha con sector, instrumento, fechas de tramitación, PDFs (`documento.php?campo=up.planoambi&valor1=...`).
- `vista_mapa.php`: mapa cuadrantes → modal con PAIs del cuadrante (misma URL `consulta.php`).
- Sin API JSON; scrape HTML determinista.

### Tablón edictos (sede)

- Paginación `edictos.php?pagina=N` (~6 páginas vigentes).
- RSS 2.0 con título, fechas exposición y GUID PDF.
- Urbanismo: edictos de información pública (p. ej. PP 1/2 Benalúa Sur), notificaciones SERVICIO DE URBANISMO.
- Filtro por palabras clave en título/descripción.

### Web Drupal

- Modificaciones activas (MP 52 alojamiento turístico, MP 53 Mercalicante) como páginas de contenido.
- Noticias urbanísticas esporádicas (licencias otorgadas).

## Cómo se publican licencias

- **No hay dataset tabular público** de concesiones con coordenadas.
- Trámites informativos en `alicante.es/es/tramites/` (licencias parcelación, instalaciones publicitarias, etc.).
- Algún edicto puntual en tablón (notificaciones, no listado histórico).
- Consulta expedientes de obra: sede ALI en mantenimiento; sin listado abierto.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Guía Urbana GeoServer WMS: `https://guiaurbana.alicante.es/geoserver/publico/wms`
  - Capa `publico:pgou87`: **raster GeoTIFF/WCS** (calificación PGOU 1987), no vector por expediente.
  - Capas vectoriales queryables: parcelas, manzanas, límites municipales — sin campo código PGMOA.
  - WFS/OWS: **no expuesto** (`/geoserver/publico/wfs` → 404).
  - Ficha PGMOA: PDF `plano_ambito.pdf` por código (`documento.php?campo=up.planoambi`) sin georreferencia embebida.
- **Estrategia:** Metadatos desde PGMOA + edictos; coordenadas vía geocode (centroide municipal + jitter). No hay query GIS enlazable expediente↔polígono.
- **Limitaciones:** Visor municipal sin WFS; pgou87 es orto/raster de zonificación; PDFs de ámbito sin coords; ALI sede inactiva.

## Limitaciones generales

- ALI (`ali.alicante.es`) en mantenimiento — sin consulta expedientes licencias.
- PGMOA histórico extenso (331 fichas); fechas solo en detalle o inferidas por texto.
- Tablón edictos mezcla urbanismo con otros departamentos; filtro heurístico.
- Encoding sede: ISO-8859-1 / latin-1 en HTML.

## Adapter implementado

- `municipio.adapters.alicante:AlicanteAyuntamientoAdapter`
- Proyectos: PGMOA `vista_tipos.php` + edictos sede + semillas Drupal MP activas.
- Licencias: edictos filtrados + trámites informativos urbanismo.
- IDs: `alicante-proy-*` / `alicante-lic-*` (sha256[:14]).
