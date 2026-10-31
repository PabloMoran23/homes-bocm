# Valdepeñas — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.valdepenas.es |
| Obras y urbanismo | https://www.valdepenas.es/servicios/obras-y-urbanismo/ |
| POM (PDFs refundido 2021) | https://www.valdepenas.es/servicios/obras-y-urbanismo/programas-y-planes/plan-de-ordenacion-municipal/ |
| Sede electrónica (espublico gestiona) | https://valdepenas.sedelectronica.es |
| Tablón de anuncios | https://valdepenas.sedelectronica.es/board |
| Catálogo trámites | https://valdepenas.sedelectronica.es/dossier |
| Consulta expedientes (login) | https://valdepenas.sedelectronica.es/expedientes |
| Transparencia | https://valdepenas.sedelectronica.es/transparency |
| Mapa web (Directorist, no urbanismo) | https://www.valdepenas.es/mapa-web/ |

## Expedientes / planeamiento

- **Tablón sede:** tabla HTML Wicket con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Enlaces a `/preview-document/{uuid}`. Procedimientos relevantes: *Actuaciones Urbanísticas*, *Licencias Urbanísticas*; categoría *Urbanismo*.
- Ejemplo activo (mar 2026): exp. **456/2024** — exposición pública «Proyecto de Urbanización del PAU 37.8 POM» (varios PDFs en tablón).
- **Web municipal:** POM aprobado DOCM/BOP 2011, refundido 2021; planos y textos en PDF/RAR en WordPress (`/wp-content/uploads/`). Plan Parcial Sector 40 documentado en la misma página.
- **Expedientes urbanísticos completos:** no hay listado público sin autenticación en `/expedientes`.

## Licencias de obra

- No hay registro histórico abierto de licencias concedidas.
- Edictos puntuales pueden aparecer en tablón bajo *Licencias Urbanísticas*.
- Trámites de licencia vía sede `/dossier` (presentación electrónica).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS CLM `Planeamiento_Municipal/MapServer/0` — polígono del PGOU/POM municipal (`COD_INE='13087'`). Query: `returnGeometry=true`, `f=geojson`, `outSR=4326`.
  - Ayuntamiento implantó «Urbanismo en Red» + LocalGIS 3 (visor con capas urbanísticas y fichas), pero **no hay URL pública** enlazada desde valdepenas.es ni API WFS accesible sin credenciales.
- **Estrategia adapter:** fila PGOU desde CLM con `geom_geojson`; anexar el mismo polígono municipal a PDFs/tablon cuyo título mencione POM/PGOU/planeamiento. Expedientes tablón (p. ej. PAU 37.8) sin enlace GIS → sin polígono de ámbito.
- **Limitaciones:** geometría a nivel municipio/POM, no parcela/expediente; visor municipal no scrapeable; tablón solo metadatos + PDF preview.
