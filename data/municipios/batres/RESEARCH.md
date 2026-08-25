# Batres — investigación portal ayuntamiento

**Municipio:** Batres (Comunidad de Madrid)  
**Fecha:** 2026-08-25  
**BOCM regional (referencia):** 2 avisos

## Resumen

Batres publica normativa y formularios de urbanismo en la **web municipal Joomla** (`www.batres.es`)
y anuncios en la **sede electrónica espublico gestiona** (`batres.sedelectronica.es`). Los ámbitos
de planeamiento están en el **SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.batres.es` | Joomla Gantry | Noticias, áreas municipales, trámites |
| Normas subsidiarias | `https://www.batres.es/ayuntamiento/normativa/normas-subsidiarias` | HTML + PDF | NNSS (memoria, normativa, planos ordenación, catálogo, modificaciones puntuales) |
| Trámites urbanismo | `https://www.batres.es/tramites/urbanismo` | HTML + PDF | Solicitudes licencia obra/actividad, declaraciones responsables, liquidaciones |
| Documentos urbanísticos | `https://www.batres.es/areas-municipales/urbanismo-e-infraestructuras/documentos-urbanisticos` | HTML | Sección informativa (pocos PDFs propios) |
| Tablón de anuncios | `https://batres.sedelectronica.es/board` | HTML tabla espublico | Anuncios recientes (pocos urbanísticos en agosto 2026) |
| Portal transparencia | `https://batres.sedelectronica.es/transparency/` | Wicket | Sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (5 docs) |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 19 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='BATRES'` |

## Tablón de anuncios (`/board`)

Tabla HTML responsive con columnas: Documento, Expediente, Procedimiento, Categoría,
Descripción, Fecha de Publicación. Enlaces `preview-document/{uuid}` (PDF). En agosto 2026
predominan anuncios administrativos; pocos relacionados con urbanismo/licencias.

## Licencias

- **Trámites web** (`/tramites/urbanismo`): ~25 PDFs (solicitud licencia obras, declaraciones
  responsables, primera ocupación, vado, actividades, liquidaciones ICIO/tasas).
- **Sede `/expedientes`**: consulta con autenticación Cl@ve; sin listado público de concesiones.
- No hay dataset histórico de licencias con coordenadas.
- Concesiones publicadas aparecen en tablón cuando procede.

## Proyectos / planeamiento

- **NNSS:** ~25 PDFs en `/images/ayuntamiento/normas-subsidiarias/` (memoria, normativa
  urbanística, planos clasificación/calificación/gestión para Batres-Los Olivos y
  Cotorredondo-Montebatres, catálogo, modificaciones puntuales 1 y 2).
- **SIT WFS:** 19 ámbitos únicos (APD-1..8, SAU-1..3, UE-2..11) con polígonos WGS84.
- Núcleos: Batres, Los Olivos, Cotorredondo, Montebatres.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='BATRES'` (`srsName=EPSG:4326`)
  - Visor regional SIT CM: `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm`
  - Planos PDF en normas subsidiarias (sin georreferenciación vectorial enlazable)
- **Estrategia:** Semillas de ámbitos desde WFS; enriquecer por código APD/SAU/UE en título
  cuando coincida con `DS_NOMB_AMB`.
- **Limitaciones:** Sin visor ArcGIS propio del ayuntamiento; tablón con pocos anuncios
  urbanísticos; licencias sin GIS enlazable; transparencia Wicket sin scrape estable de dossier.

## Limitaciones

- No hay visor urbanístico municipal propio.
- `/dossier` de sede no probado; catálogo de trámites vía menú informativo.
- Tablón muestra solo anuncios vigentes (~5 filas en agosto 2026).
- Documentos urbanísticos web casi vacíos (solo formulario PMR tráfico).

## Estrategia adapter

1. Scrape tablón `/board` (tabla data-label + fallback enlaces preview-document).
2. PDFs NNSS desde normas subsidiarias como proyectos de planeamiento.
3. PDFs trámites urbanismo como páginas informativas de licencias.
4. Semillas de ámbitos SIT WFS con `geom_geojson`.
5. IDs: `batres-{lic|proy}-{sha256[:14]}`.
