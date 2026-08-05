# Colmenar de Oreja — investigación portal ayuntamiento

## URLs base

| Fuente | URL | Tecnología |
|--------|-----|------------|
| Web municipal | https://www.aytocdo.es | Drupal 10 (tema mipueblo) |
| Área urbanismo | https://www.aytocdo.es/areas/urbanismo | Drupal views (noticias, instalaciones) |
| Trámites presenciales | https://www.aytocdo.es/descargas-generales | PDFs formularios licencia |
| Sede electrónica | https://colmenardeoreja.sedelectronica.es | espublico gestiona (eHome/Wicket) |
| Tablón de anuncios | https://colmenardeoreja.sedelectronica.es/board | Tabla HTML 6 columnas + preview-document |
| Catálogo trámites | https://colmenardeoreja.sedelectronica.es/dossier | Catálogo espublico (timeout intermitente) |
| Transparencia | https://colmenardeoreja.sedelectronica.es/transparency | Sección «E. URBANISMO…» (41 docs, AJAX Wicket) |
| Visor SITCM CM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Referencia ámbitos UA-/S- |

## Proyectos / expedientes

- **Tablón sede:** tabla con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Enlaces `preview-document/{uuid}`. Sin paginación visible (~8 filas actuales); mezcla empleo público y BOCM.
- **Drupal urbanismo:** noticias en `/areas/urbanismo/noticias` (views embebidas, texto social sin nodos enlazados). Sin listado PGOU/planes en web.
- **SITCM WFS:** 13 ámbitos de planeamiento (`UA-1`…`UA-11`, `S-1`, `S-2`) en capa `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='COLMENAR DE OREJA'`.

## Licencias

- No hay dataset público de concesiones. Formularios descargables en `/descargas-generales` (obra menor, apertura, acometida, etc.).
- Tablón puede publicar licencias puntuales (filtro por categoría/procedimiento).
- Catálogo sede incluye trámites de urbanismo (cuando `/dossier` responde).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, campo `DS_NOMB_AMB` (códigos UA-*, S-*).
- **Estrategia:** ingestar los 13 ámbitos SITCM como proyectos con polígono; enriquecer títulos de tablón/noticias que mencionen código de ámbito.
- **Limitaciones:** sin visor urbanístico municipal propio (el botón «visor-urbanismo» en home apunta a incidencias eAgora). Transparencia urbanismo requiere sesión AJAX Wicket. Tablón sin coords. PGOU solo vía SITCM regional.

## Limitaciones generales

- `/dossier` puede tardar >30s o no responder desde CI.
- Noticias Drupal sin URLs de detalle scrapeables.
- Tablón actual mayoritariamente empleo público; paridad proyectos depende de SITCM + filtrado BOCM.
