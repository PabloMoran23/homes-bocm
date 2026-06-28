# Torrelodones — investigación portal ayuntamiento

**Municipio:** Torrelodones (Comunidad de Madrid)  
**Fecha:** 2026-06-22  
**BOCM regional (referencia):** 34 avisos

## Resumen

Torrelodones publica urbanismo en web corporativa WordPress (Elementor) y sede electrónica eHome (espublico gestiona / Wicket):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://torrelodones.es/urbanismo/` | WordPress | Trámites licencia (informativo) |
| Normas subsidiarias | `https://torrelodones.es/normas-subsidiarias/` | PDFs PGOU/NNSS | Proyectos (planeamiento) |
| Tablón sede | `https://sede.torrelodones.es/board` | HTML tabla eHome | Proyectos y licencias (anuncios vigentes) |
| Avisos web | `https://torrelodones.es/avisos-y-bandos/` | WordPress | Proyectos obras públicas |
| Visor planeamiento SIT | `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=152` | Visor regional | Referencia (código INE 152) |
| Geoportal ArcGIS | `https://torrelodones.maps.arcgis.com/` | ArcGIS Online (SYKGIS) | Geometría sectores NNSS |
| Transparencia sede | `https://sede.torrelodones.es/transparency` | eHome Wicket AJAX | 13 docs sección 6 (no scrapeable sin sesión) |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (WordPress)

- **URL:** `https://torrelodones.es/urbanismo/`
- **Contenido:** Páginas informativas de trámites (licencia obra mayor/menor, declaración responsable, ocupación vía pública, licencia actividad).
- **Licencias:** No hay listado público de concesiones; solo formularios y enlaces a sede (`https://sede.torrelodones.es/registro`).
- **Mecanismo:** HTML estático WordPress.

### 2. Normas subsidiarias / planeamiento

- **URL:** `https://torrelodones.es/normas-subsidiarias/`
- **Contenido:** Texto refundido NNSS 1997, adendas movilidad 2013, publicaciones BOCM (aprobación inicial/definitiva).
- **PDFs:** 6 documentos en `wp-content/uploads/2025/10/`.
- **Visor:** Enlace al SIT Comunidad de Madrid (`municipio=152`) y geoportal ArcGIS municipal.

### 3. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://sede.torrelodones.es/board`
- **Formato:** Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación.
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Limitación:** Solo anuncios vigentes (~10 filas en jun 2026, mayormente empleo público); sin histórico indexable.
- **SSL:** Certificado con problemas en algunos clientes → `insecure_ssl: true`.

### 4. Avisos y bandos (obras urbanísticas)

- Ejemplos: mejora accesibilidad Urbanización Arroyo de Trofas, Montealegre.
- **URL patrón:** `https://torrelodones.es/aviso-*-urbanizacion-*` o `avisos-y-bandos/aviso-proyecto-*`
- **Mecanismo:** WordPress REST API (`search=proyecto mejora urbanizacion`).

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| Transparencia sección 6 (Wicket AJAX) | Requiere sesión JS; redirige a identificación |
| `/dossier`, `/info` sede | Redirect loop sin cookies |
| Consulta expedientes `/expedientes` | Requiere Cl@ve/certificado |
| BOCM re-parse | Ya cubierto en pipeline regional |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS FeatureServer SYKGIS: `https://services1.arcgis.com/SwZwNQ29xwi3dduD/arcgis/rest/services/Normas_Subsidarias_Sectores_Urbanisticos_SYKGIS/FeatureServer/0`
  - 41 polígonos de sectores urbanísticos (campos `TXT_LABEL`, `P_COD`, `P_CL`, `LINK`, `LINK_NORMA`)
  - Visor SIT CM: `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=152`
  - Geoportal municipal: `https://torrelodones.maps.arcgis.com/home/index.html`
- **Estrategia:** Query ArcGIS `returnGeometry=true`, `outSR=4326`, `f=geojson`; cruce por código de sector en título (`S-10`, `APD-13`, `AHS`, etc.).
- **Limitaciones:** No hay capa pública de expedientes/licencias georreferenciados; geometría solo a nivel de sector NNSS, no por expediente individual. Licencias del tablón sin polígono enlazable.

## Estrategia de ingesta

- **proyectos.jsonl:** PDFs normas subsidiarias + tablón sede filtrado + avisos WordPress (obras/urbanización).
- **licencias.jsonl:** tablón sede filtrado (licencia/obra) + páginas trámite urbanismo (informativas).
- **IDs:** `torrelodones-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.
- **Geometría:** `geom_geojson` en proyectos con código de sector reconocible en título.

## Paridad esperada

- `proyectos`: ok (6+ PDFs NNSS + avisos + tablón cuando haya urbanismo).
- `licencias`: partial (trámites informativos; sin listado concesiones con coords).
- `with_geometry`: >0 si hay sectores emparejados en títulos de planeamiento.
