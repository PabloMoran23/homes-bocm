# Gascones — investigación portal ayuntamiento

**Municipio:** Gascones (Comunidad de Madrid)  
**Fecha:** 2026-08-06  
**BOCM regional (referencia):** 7 avisos

## Resumen

Gascones publica normativa urbanística y trámites en la **web corporativa Joomla** (`gascones.com`, plantilla LT Company + SP Page Builder + icagenda),
anuncios en el **tablón municipal** (RSS icagenda) y la **sede electrónica espublico gestiona** (`gascones.sedelectronica.es`).
Los ámbitos de planeamiento (NNSS: zonas E-* y SAU-1 Los Redondos) están en el **SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`, código municipio 064).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web NNSS | `https://www.gascones.com/tu-ayuntamiento/normativa-municipal/urbanismo-normas-subsidiarias` | Joomla HTML | Enlace SITCM, artículos modificación puntual NNSS |
| Concejalía urbanismo | `https://www.gascones.com/tu-ayuntamiento/concejalias/129-urbanismo/` | Joomla artículos | Aprobación/información pública modificación NNSS (SNU agropecuario) |
| Tablón municipal | `https://www.gascones.com/ciudadanos/tablon-municipal` | icagenda RSS | Anuncios municipales (subvenciones rehabilitación, etc.) |
| Trámites licencias | `https://www.gascones.com/ciudadanos/tramites-personales/instancias-licencias-y-solicitudes` | Joomla HTML + PDF | Modelos licencia obra mayor/menor, DR, primera ocupación, actividad |
| Tablón sede | `https://gascones.sedelectronica.es/board/` | HTML tabla Wicket | Anuncios recientes (modificación NNSS, BOCM, presupuesto) |
| Sede electrónica | `https://gascones.sedelectronica.es/` | espublico gestiona | Registro, consulta expedientes |
| Transparencia | `https://transparencia.gascones.com/transparencia-en-materias-de-urbanismo-obras-publicas-y-medioambiente` | Joomla HTML + PDF | Documentación infraestructura urbanística |
| SIT Comunidad Madrid | `https://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=064` | Visor + WFS | 5 ámbitos únicos con polígonos (E-1..E-4, SAU-1) |

## Tablón de anuncios (`/board/`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document/{uuid}` (PDF). En agosto 2026 incluye modificación puntual NNSS, BOCM presupuesto 2026, censo electoral.

## Licencias

- Modelos PDF en web: licencia obra mayor, declaración responsable obra menor, primera ocupación, licencia actividad, segregación/agrupación, vallado, piscina.
- No hay dataset histórico de concesiones con coordenadas; solo trámites informativos y tablón de anuncios.
- Presentación vía registro general o sede electrónica.

## Proyectos / planeamiento

- **NNSS:** Normas Subsidiarias de Planeamiento Municipal (cartografía en SITCM).
- **Modificación puntual NNSS** (SNU agropecuario): artículos en concejalía urbanismo + anuncio en tablón sede.
- **SIT WFS:** 5 ámbitos únicos (`E-1 EXTENSIÓN DE CASCO`, `E-2/E-3/E-4 RESIDENCIAL UNIFAMILIAR`, `SAU-1 LOS REDONDOS`) con polígonos en WGS84.
- **Transparencia:** PDFs infraestructura en `/images/Urbanismo/Infraestructura/`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='GASCONES'` (`srsName=EPSG:4326`)
  - Visor SITCM Comunidad de Madrid: `visor.htm?municipio=064`
  - No hay visor ArcGIS propio del ayuntamiento ni GeoJSON en datos abiertos locales
- **Estrategia:** Semillas de ámbitos SIT WFS con `geom_geojson`; enriquecer por código E-/SAU- en títulos de expedientes.
- **Limitaciones:** Tablón/PDF sin georreferenciación por expediente; licencias sin GIS enlazable; sede `/dossier` muy lento/inaccesible desde CI.

## Limitaciones

- Municipio pequeño (~230 hab.): pocos anuncios urbanísticos en tablón web (mayoría empleo/subvenciones).
- Portal transparencia separado (`transparencia.gascones.com`) con plantilla Joomla distinta.
- No hay listado público de licencias concedidas con ubicación.

## Estrategia adapter

1. Scrape tablón sede `/board/` (tabla preview-document).
2. RSS tablón municipal icagenda (filtrar urbanismo/rehabilitación).
3. Páginas NNSS y artículos concejalía urbanismo.
4. PDFs trámites licencias (modelos informativos).
5. PDFs transparencia infraestructura.
6. Semillas ámbitos SIT WFS (5 únicos) con `geom_geojson`.
7. IDs: `gascones-{lic|proy}-{sha256[:14]}`.
