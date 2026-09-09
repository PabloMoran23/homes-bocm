# Boadilla — investigación portal ayuntamiento

## Nota alias BOCM

La cola registra el municipio como **«Boadilla»** (`slug: boadilla`, provincia «Boadilla, Madrid») con 1 entrada BOCM.
Corresponde al municipio oficial **Boadilla del Monte** (INE 28022). El portal y la sede son los mismos que
`boadilla-del-monte` (adapter previo PR #8); esta run materializa el slug abreviado del CSV.

## Resumen

Portal **Drupal** en `https://www.ayuntamientoboadilladelmonte.org` con sede electrónica propia en
`https://carpetaciudadano.aytoboadilla.org` (Java/JSP, tablón digital). No hay API REST pública de
expedientes; la ingesta se basa en HTML + PDFs del portal y listado del tablón de anuncios.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Urbanismo (general) | `/informacion-general-de-urbanismo` | Drupal HTML + PDF | Enlaces IP, PGOU, estudios de detalle |
| PGOU 2015 | `/plan-general-de-ordenacion-urbana-2015` | Drupal + PDF | Documentación PGOU, planos, normas |
| Planeamiento desarrollo | `/planeamiento-de-desarrollo-del-pgou` | Drupal + PDF | Planes parciales, PERI, estudios |
| Gestión urbanística | `/gestion-urbanistica` | Drupal | Trámites y documentación en curso |
| IP PERI AD-5 | `/informacion-publica-peri-del-suelo-urbano-consolidado-ad-5-dotacional-monteprincipe` | Drupal + PDF | Memoria, anexos ambientales PERI |
| Licencias obras | `/licencias-obras` | Drupal + PDF | Trámites y formularios licencia |
| Licencias urbanísticas | `/licencias-urbanisticas-documentacion` | Drupal + PDF | Documentación trámites |
| Convenios vigentes | `/convenios-vigentes` | Drupal + PDF | Listado convenios urbanísticos |
| Tablón digital | `carpetaciudadano.aytoboadilla.org/eAdmin/Tablon.do?action=verAnuncios` | JSP tabla HTML | Edictos y anuncios (búsqueda POST) |
| Detalle anuncio | `Tablon.do?action=verAnuncio&id={hex}` | JSP | Ficha con PDF firmado / original |

## Estructura HTML relevante

### Tablón sede

- Listado: `Tablon.do?action=verAnuncios` (GET) o búsqueda POST `referenciaBusqueda`
- Filas `<tr>` con `verAnuncio&id=HEX`, título en `<td width="40%">`, periodo `DD/MM/YYYY - DD/MM/YYYY`
- Documentos vía `javascript:abrir('token')` (base64); detalle en `verAnuncio`

### Portal Drupal urbanismo

- PDFs en `/sites/default/files/*.pdf` (nomenclatura `bocm-*`, `estudio_de_detalle_*`, `vol_*`, `peri*`)
- Páginas IP dedicadas bajo `/informacion-publica-*`
- Menú urbanismo enlaza sede, licencias y planeamiento

## Licencias

El ayuntamiento **no publica un registro tabular de concesiones** con coordenadas.
Las licencias proceden de:

1. Páginas informativas de trámites (`/licencias-obras`, `/licencias-urbanisticas-documentacion`)
2. Tablón filtrado por keywords de licencia/edicto (volumen bajo en tablón vigente)

`lat`/`lon`/`distrito` quedan `null` salvo enriquecimiento por geometría SITCM.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='BOADILLA DEL MONTE'`
  - Visor web: `http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=175`
- **Estrategia:**
  - Catálogo de ámbitos SITCM como proyectos con polígono (`sit_wfs`)
  - Enriquecimiento por título (códigos AD/UE/PERI en PDFs y páginas IP) vía `resolve_ambito_geometry`
- **Limitaciones:**
  - El portal Drupal y el tablón no exponen geometría por expediente
  - `silbo.aytoboadilla.com` (visor municipal mencionado en menú) inaccesible por SSL desde CI
  - Cobertura parcial: solo filas con código de ámbito reconocible o catálogo SITCM

## Limitaciones

- Tablón vigente mayoritariamente administrativo (concursos, plenos); pocos edictos urbanísticos activos.
- Documentos del tablón requieren tokens JS; se usa URL de detalle `verAnuncio` como referencia estable.
- Sin geolocalización en fuentes directas del ayuntamiento.

## Referencia adapters

- Drupal + PDF crawl: `pozuelo.py`, `boadilla_del_monte.py`
- Tablón sede + filtro regex: `mostoles.py`, `getafe.py`
- SITCM WFS partial: `pedrezuela.py`, `villamantilla.py`
