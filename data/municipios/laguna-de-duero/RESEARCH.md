# Laguna de Duero — investigación portal ayuntamiento

**Municipio:** Laguna de Duero (Valladolid, Castilla y León)  
**Fecha:** 2026-08-04  
**BOCYL regional (referencia):** 9 avisos

## Resumen

Laguna de Duero publica urbanismo y licencias en la **sede electrónica espublico gestiona**
(`lagunadeduero.sedelectronica.es`), con documentación de planeamiento en **PLAI JCYL** y
cartografía en **SIUCyL / IDECyL WFS**. La web corporativa WordPress (`www.lagunadeduero.org`)
tiene la API REST bloqueada (401 sin login); el contenido urbanístico se redirige al portal de
transparencia de la sede.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de anuncios | `https://lagunadeduero.sedelectronica.es/board` | HTML tabla Wicket | Edictos recientes (~10 filas) |
| Catálogo trámites | `https://lagunadeduero.sedelectronica.es/dossier` | HTML Wicket | ~172 trámites (`/catalog/t/{uuid}`) |
| Portal transparencia | `https://lagunadeduero.sedelectronica.es/transparency` | Wicket/AJAX | Sección E Urbanismo (1738 docs; carga AJAX) |
| Sede ASP.NET legacy | `https://sede.lagunadeduero.org/` | ASP.NET | Notificaciones, transparencia integrada |
| PLAI JCYL | `servicios.jcyl.es/PlanPublica` (municipio 075, prov. 47) | HTML tabla | Instrumentos urbanísticos PDF/BOCYL |
| SIUCyL WFS | `idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | Sectores, planes parciales, ámbitos |
| Web municipal | `https://www.lagunadeduero.org` | WordPress Sydney | WP REST requiere login; búsquedas HTML limitadas |
| PGOU 2024 | `lagunadeduero.sedelectronica.es/citizen-service/8e84726e-...` | Página informativa sede | Enlace desde menú sede |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document/{uuid}` (PDF). En la muestra actual predominan contratación y empleo;
los anuncios de urbanismo aparecen esporádicamente (convocatorias de pleno con acuerdos urbanísticos).

## Trámites urbanismo (catálogo sede)

Trámites scrapeables como páginas informativas (sin listado de concesiones):

- Solicitud de Licencia de Obra Mayor / Licencia o Autorización Urbanística
- Declaración Responsable de Obras y Usos-Obras Menores
- Solicitud de certificados e informaciones Urbanísticas
- Consulta de Proyectos de Urbanismo
- Planeamiento General (Modificación)
- Solicitud de Licencia de Segregación o Agrupación
- Solicitud de Recepción de Obras de Urbanización

## PLAI JCYL

Código municipio PLAI: **075** (provincia 47, INE 47075). Documentos vigentes incluyen:

- NORMAS URBANÍSTICAS MUNICIPALES (NUM)
- Plan Parcial Sector 2C "El Molino 3"
- Modificaciones puntuales NUM (varias)
- Estudio de Detalle calle León
- Modificación 1-2025 NUM (feb 2026)

Enlaces: `doGoBoletin` (BOCYL) y `doOpen` (PDF documento).

## Licencias

No hay visor georreferenciado municipal de concesiones (sin paridad Madrid DROUS).

- Tablón publica edictos de licencia cuando existen.
- Catálogo sede aporta páginas de trámite informativas.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 12 polígonos (sectores "El Canal", "La Guarnicionera", etc.)
  - WFS `urbanismo:plau_cyl_planes_parciales` — 4 polígonos (p. ej. Sector 2C El Molino 3)
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono ámbito PGOU
  - Filtro: `n_mun ILIKE 'Laguna de Duero%'`, `outputFormat=application/json`, `srsName=EPSG:4326`
  - Visor SIUCyL: `https://idecyl.jcyl.es/siur/` (consulta cartográfica, sin enlace directo a expediente)
- **Estrategia:** ingestar capas WFS como proyectos con `geom_geojson`; enriquecer filas PLAI/tablón
  por coincidencia de nombre de sector en título (`EL MOLINO`, etc.)
- **Limitaciones:**
  - No hay geometría por expediente individual de licencia
  - Portal transparencia urbanismo (1738 docs) requiere expandir categorías vía AJAX Wicket
  - WP REST bloqueado; sede dossier tarda ~30–90 s en CI (CookieJar + `insecure_ssl`)
  - PLAI no expone coordenadas; solo PDF/BOCYL

## Limitaciones generales

- Certificado SSL sede espublico: emisor no siempre en CA del sistema → `insecure_ssl: true`
- Tablón ~10 anuncios recientes; histórico urbanismo principalmente en PLAI
- Transparencia ASP.NET en `sede.lagunadeduero.org` duplica contenido con carga PostBack

## Estrategia adapter

1. Scrape tablón `/board` + extracto `/info` (espublico).
2. Catálogo `/dossier` filtrado por keywords urbanismo/licencia.
3. PLAI JCYL municipio 075 (paginación hasta 8 páginas).
4. WFS SIUCyL sectores/PP/ámbitos con polígonos.
5. IDs: `laguna-de-duero-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico: `pelabravo.py`, `el_molar.py`
- PLAI JCYL: `valladolid.py`
- WFS SIUCyL: `segovia.py`, `salamanca.py`
