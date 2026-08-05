# Valdemaqueda — investigación portal ayuntamiento

**Municipio:** Valdemaqueda (Comunidad de Madrid)  
**Fecha:** 2026-08-05  
**BOCM regional (referencia):** 9 avisos

## Resumen

Valdemaqueda publica información urbanística en la **web municipal Joomla** (`aytovaldemaqueda.es`)
y trámites/anuncios en la **sede electrónica espublico gestiona**
(`aytovaldemaqueda.sedelectronica.es`). Los ámbitos de planeamiento están en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Concejalía urbanismo | `https://aytovaldemaqueda.es/tu-ayuntamiento/concejalias/urbanismo` | Joomla HTML + RSS | Noticias de actuaciones urbanísticas |
| NNSS | `.../100-normas-subsidiarias-de-planeamiento-municipal` | Joomla artículo | Texto de modificaciones definitivas (BOCM 1996–2009) |
| Tablón municipal web | `https://aytovaldemaqueda.es/ciudadanos/tablon-municipal` | Joomla RSS | Bandos y edictos (imágenes/PDF) |
| Tablón sede | `https://aytovaldemaqueda.sedelectronica.es/board/` | HTML tabla | Anuncios recientes con `preview-document/{uuid}` |
| Portal transparencia | `https://aytovaldemaqueda.sedelectronica.es/transparency/` | Wicket AJAX | Sección **7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** (19 docs) |
| Visor SIT CM | `https://idem.madrid.org/cartografia/sitcm/html/visor.htm` | Enlace desde web | Planeamiento regional |
| SIT WFS | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 12 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='VALDEMAQUEDA'` |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción,
Fecha de Publicación. Enlaces `preview-document/{uuid}`. En agosto 2026 predominan
anuncios administrativos (plenos, IBI, bandos incendios); sin licencias urbanísticas recientes.

## Licencias

- Trámites en sede electrónica (`/dossier`, `/info`) — catálogo espublico gestiona.
- No hay dataset histórico de concesiones con coordenadas.
- El adapter incluye páginas informativas de referencia (tablón sede, urbanismo, transparencia).

## Proyectos / planeamiento

- **NNSS 1996** con 5 modificaciones definitivas documentadas en la web (BOCM 2002, 2009).
- **Modificación puntual 2025** (redes públicas y VPP) en trámite regional (BOCM referenciado en CCAA).
- **SIT WFS:** 12 ámbitos (UE-1…UE-11, SAU-1) con polígonos WGS84.
- Noticias urbanismo: actuaciones alcantarillado/alumbrado, proyecto sombras plaza España.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='VALDEMAQUEDA'` (`srsName=EPSG:4326`)
  - Visor regional SIT CM: `https://idem.madrid.org/cartografia/sitcm/html/visor.htm`
  - No hay visor ArcGIS propio del ayuntamiento
- **Estrategia:** Semillas de ámbitos desde WFS; enriquecer por código UE/SAU en título cuando
  coincida con `DS_NOMB_AMB`.
- **Limitaciones:** Tablón/PDF sin georreferenciación; transparencia Wicket no automatizable;
  NNSS sin PDFs descargables (solo texto); `/dossier` con timeout en CI.

## Limitaciones

- Portal transparencia: árbol Wicket con sesión JS; no scrapeable de forma estable.
- Tablón sede muestra solo anuncios recientes (~6 filas).
- NNSS publicada como texto HTML sin enlaces PDF directos.
- Sede `/dossier` e `/info` pueden tardar >15s o no responder en CI.

## Estrategia adapter

1. Scrape tablón `/board` (tabla data-label + fallback enlaces).
2. RSS urbanismo y tablón municipal Joomla.
3. Página NNSS + modificaciones parseadas del texto.
4. Semillas de ámbitos SIT WFS con `geom_geojson`.
5. Páginas informativas de referencia (tablón, urbanismo, transparencia).
6. IDs: `valdemaqueda-{lic|proy}-{sha256[:14]}`.
