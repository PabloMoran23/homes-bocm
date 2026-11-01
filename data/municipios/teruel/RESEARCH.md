# Teruel — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `teruel` |
| Provincia | Teruel |
| CCAA | Aragón |
| Boletín | Sin boletín asociado en cola BOCM |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.teruel.es | WordPress (Hub/Liquid) |
| Portal transparencia | https://www.teruel.es/portal-de-transparencia/ | Sección F. Urbanismo |
| Instrumentos planeamiento | https://www.teruel.es/portal-de-transparencia/instrumentos-de-planeamiento/ | Lista PDF (estudios de detalle, anuncios BOP) |
| Modificaciones PGOU | https://www.teruel.es/portal-de-transparencia/modificaciones-del-planeamiento/ | PDFs modificaciones estructurales |
| PGOU | https://www.teruel.es/portal-de-transparencia/plan-general-de-ordenacion-urbana/ | PDF PGOU 1985 |
| Convenios urbanísticos | https://www.teruel.es/portal-de-transparencia/convenios-urbanisticos/ | PDF convenios |
| Autorizaciones/licencias | https://www.teruel.es/portal-de-transparencia/autorizaciones-licencias-y-concesiones/ | Publicaciones puntuales (no dataset) |
| Sede STA | https://sede.teruel.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME | Tablón, catálogo trámites |
| Tablón anuncios | https://sede.teruel.es/sta/CarpetaPublic/doEvent?APP_CODE=PTS2_TABLON&KEY=all | DataTables + AjaxAnywhere (sin `dataset_PTS2_TABLON` en HTML inicial) |
| Catálogo trámites | https://sede.teruel.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | `dataset_CATSERV` (~112 trámites) |
| PGOU participación | https://pgouteruel.es/mapa-web/ | Web informativa PGOU (sin API scrapeable) |

## Cómo se listan expedientes / proyectos

1. **Transparencia (WordPress)**: listas `<ul>` con enlaces a PDF en `/wp-content/uploads/` y `/wp-content/uploads/documentos/`. Título en texto del enlace.
2. **Catálogo STA**: array JSON embebido `var dataset_CATSERV = [...]` con trámites de urbanismo (`TramUrbanismo` en keywords).
3. **Tablón STA**: el listado se carga por evento widget `PTS2_TABLON` / `LISTA` (AjaxAnywhere); no hay dataset estático en el GET inicial — el adapter no depende del tablón para cumplir paridad de proyectos.

## Cómo se publican licencias

- Trámites electrónicos en catálogo STA (licencia urbanística, comunicación previa, declaración responsable, etc.) — páginas informativas, no registro histórico de concesiones.
- Tablón municipal para edictos/anuncios (acceso 24h); contenido dinámico no extraído de forma determinista sin emular Ajax STA.
- Transparencia «Autorizaciones licencias y concesiones» con PDFs puntuales (no listado sistemático).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - [SIUa visor](https://idearagon.aragon.es/SIUa/visor/) — planeamiento regional Aragón (clasificación, instrumentos).
  - [ICEARAGON visor 2D](https://icearagon.aragon.es/visor/) — búsqueda por INE `44001` (Teruel).
  - PGOU municipal: https://pgouteruel.es/mapa-web/ (sin servicio ArcGIS/WFS público enlazado a códigos de expediente del ayto.).
- **Estrategia:** los PDFs del portal no exponen `objectId` ni capa GIS consultable por código de expediente; referencias catastrales aparecen solo en algunos títulos (p. ej. `6157817XK6665N0001WM`) sin API estable en el adapter. El orquestador usa centroide municipal + jitter.
- **Limitaciones:** tablón STA sin JSON embebido; SIUA/IDEAragón no ofrecen WFS simple filtrable por título de anuncio municipal; sin dataset de licencias georreferenciadas.

## Limitaciones

- Tablón STA requiere sesión Ajax para listar filas (no scrapeable con patrón `dataset_PTS2_TABLON` usado en otras sedes STA).
- «Autorizaciones licencias» mezcla materias no urbanísticas.
- Sin boletín autonómico asociado en la cola (`bocm_count: 0`).
