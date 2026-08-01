# Patones — investigación portal ayuntamiento

**Municipio:** Patones (Comunidad de Madrid)  
**Fecha:** 2026-07-31

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress) | https://patones.net/site/ayto/ | Portal activo del ayuntamiento (`www.patones.es` inaccesible) |
| Urbanismo / arquitecto municipal | https://patones.net/site/ayto/arquitecto-municipal/ | PAMIF, PAMINUN, Pro_Park, Pro_Citeco (PDFs) |
| Normas subsidiarias (NNSS) | https://patones.net/site/ayto/normas-subsidiarias/ | ~52 PDFs (memoria, planos, modificaciones UE-15, etc.) |
| Bandos | https://patones.net/site/ayto/bandos/ | Bandos municipales (desbroce parcelas, etc.) |
| Boletín municipal | https://patones.net/site/ayto/boletin-municipal/ | Boletines |
| Plan especial aparcamientos | https://patones.net/site/ayto/plan-especial-de-aparcamientos-y-mejora-*/ | Planes especiales UP2403 |
| Modificación NNSS | https://patones.net/site/ayto/modificacion-puntual-de-las-normas-subsi*/ | Modificación puntual NNSS |
| Sede electrónica (espublico gestiona) | https://patones.sedelectronica.es/board | Tablón de anuncios (7 filas actuales) |
| Transparencia | https://patones.sedelectronica.es/transparency | Sección URBANISMO (~34 docs; Wicket, no scrapeable) |
| Catálogo trámites | https://patones.sedelectronica.es/dossier | Redirect loop — no usable |

## Cómo se listan expedientes

- **WordPress:** páginas estáticas con enlaces a PDFs en `/site/nnss/` y `/ayto/archivos/`. REST API en `https://patones.net/site/ayto/wp-json/wp/v2/pages` (26 páginas; pocas noticias en `/posts`).
- **Tablón sede:** HTML tabla con `preview-document` (espublico gestiona). Columnas: documento, expediente, procedimiento, categoría, descripción, fecha.
- **NNSS:** listado extenso de PDFs históricos con códigos UE en nombres de archivo (p. ej. `UE_15_30_10_2009_REUR_75497.pdf`).
- No hay API JSON ni visor de expedientes individual enlazado.

## Cómo se publican licencias

- No hay dataset ni listado histórico de concesiones de licencia de obra.
- El tablón actual no contiene licencias urbanísticas (bandos, ordenanzas, IAE).
- Trámites informativos en sede (`/dossier` inaccesible por redirect loop).
- Estrategia: páginas informativas del tablón + transparencia + formularios si aparecen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='PATONES'`
  - Campo ámbito: `DS_NOMB_AMB` (15 unidades de ejecución: UE-1 … UE-15)
- **Estrategia:** query WFS por código UE en título/PDF; semillas `_collect_sit_ambitos()` para las 15 UE; centroide del polígono en WGS84.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - PDFs de planeamiento sin georreferencia embebida.
  - Transparencia Wicket no scrapeable.
  - `/info` y `/dossier` en sede con redirect loop.
  - Geometría solo para ámbitos SITCM identificables por código UE en título.

## Limitaciones generales

- Portal principal en subdirectorio WordPress (`patones.net/site/ayto`).
- Certificado sede válido; no requiere `insecure_ssl`.
- Paginación WP pages limitada (26 páginas totales).
- Mayoría de proyectos son PDFs históricos NNSS sin fecha explícita en metadatos.
