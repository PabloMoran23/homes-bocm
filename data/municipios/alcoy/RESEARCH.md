# Alcoy — investigación portal ayuntamiento

**Municipio:** Alcoy (`alcoy`)  
**Provincia:** Alicante  
**CCAA:** Comunitat Valenciana (DOGV)  
**INE:** 03009

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Portal web (OpenCMS) | https://www.alcoi.org |
| Urbanismo | https://www.alcoi.org/es/areas/urbanismo/ |
| Transparencia urbanismo | https://www.alcoi.org/es/areas/urbanismo/transparencia/ |
| Licencias urbanísticas (PDF) | https://www.alcoi.org/es/areas/urbanismo/transparencia/licencias_urbanisticas.html |
| Declaraciones de obra (PDF) | https://www.alcoi.org/es/areas/urbanismo/transparencia/declaraciones_obra.html |
| Catálogo protecciones | https://www.alcoi.org/es/areas/urbanismo/transparencia/catalogo_protecciones.html |
| Expedientes restauración | https://www.alcoi.org/es/areas/urbanismo/transparencia/expedientes_restauracion.html |
| Polígonos industriales | https://www.alcoi.org/es/areas/urbanismo/poligonos/index.html |
| Convenios urbanismo | https://www.alcoi.org/es/areas/secretaria/convenios.html?area=urbanismo |
| Sede electrónica STA | https://sedeelectronica.alcoi.org |
| Tablón STA | https://sedeelectronica.alcoi.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all |
| Catálogo trámites STA | https://sedeelectronica.alcoi.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO |
| RSS noticias | https://www.alcoi.org/es/portal/noticias.rss |
| Geoportal municipal | https://geoportal.alcoi.org/alcoi/ |
| Transparencia WP | https://transparencia.alcoi.org/urbanismo-obras-y-medio-ambiente/ |

## Cómo se listan expedientes / proyectos

- **CMS OpenCMS** (`org.alcoi.web.ayto`): páginas de transparencia urbanismo con enlaces a PDFs (certificados JGL, convenios, catálogo, polígonos).
- **Sede STA (T-Systems)**: tablón con dataset JSON embebido `dataset_PTS2_TABLON` (pocos anuncios activos); catálogo `dataset_CATSERV` con ~314 trámites (~43 de urbanismo).
- **RSS municipal**: noticias con menciones a expedientes/obras urbanísticas.
- **ICV WFS**: capa `Planeamiento.Zonificacion` con instrumentos de planeamiento del municipio (plan general, planes parciales, homologaciones).

## Cómo se publican licencias

- **Listados PDF trimestrales/anuales** en transparencia urbanismo (`licencias_urbanisticas.html`, `declaraciones_obra.html`). No hay tabla HTML ni API con coordenadas por expediente.
- **Catálogo sede STA**: trámites informativos (licencia urbanística, declaración responsable, comunicación previa, etc.) sin concesiones individuales publicadas.
- El tablón STA actual tiene muy pocos anuncios (3 filas, ninguno urbanístico en el momento de la investigación).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `Planeamiento.Zonificacion` — `https://terramapas.icv.gva.es/0702_Planeamiento` — filtro client-side `cod_ine_mun=03009`, WFS 2.0 GeoJSON EPSG:4326.
  - Geoportal municipal Sencha ExtJS (`geoportal.alcoi.org`) — visor interactivo sin endpoint REST/ArcGIS público documentado para consultas automatizadas.
- **Estrategia:** ingestar polígonos de instrumentos de planeamiento desde ICV WFS; enriquecer proyectos web/RSS por coincidencia de título (sector, plan parcial, etc.).
- **Limitaciones:**
  - Licencias y declaraciones de obra solo en PDF agregado (sin georef por expediente).
  - Geoportal municipal no expone MapServer/WFS directo.
  - ICV WFS requiere paginación por `startIndex` (lento; ~7 instrumentos únicos en offsets 0–15000).

## Instrumentos ICV detectados (muestra)

- Plan general
- PLAN PARCIAL "EL CLERIGO"
- MODIFICACIÓN PLAN PARCIAL "EL CLERIGO"
- HOMOLOGACIÓN Y PLAN PARCIAL INDUSTRIAL Y RESIDENCIAL DE MEJORA EL CASTELLAR
- HOMOLOGACIÓN Y PLAN PARCIAL SUNP-4 SECTORES 1, 2, 3 "EL SARGENTO"
- HOMOLOGACIÓN MODIFICATIVA DE LOS SECTORES "LA SOLANA"
- PLAN GENERAL (Parque Natural del Carrascal de la Font Roja)

## Limitaciones generales

- Portal bilingüe valenciano/castellano; rutas `/ca/` y `/es/`.
- Sin tablón de anuncios espublico gestiona (usa STA propio).
- SSL válido en sede y portal principal.
