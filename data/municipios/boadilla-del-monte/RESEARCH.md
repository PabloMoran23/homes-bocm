# Boadilla del Monte — investigación portal ayuntamiento

## Resumen

Portal **Drupal** en `https://www.ayuntamientoboadilladelmonte.org` con sede electrónica
propia en `https://carpetaciudadano.aytoboadilla.org` (Java/JSP, tablón digital).
No hay API REST pública de expedientes; la ingesta se basa en HTML + PDFs del portal
y listado del tablón de anuncios.

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

`lat`/`lon`/`distrito` quedan `null`.

## Limitaciones

- Tablón vigente (~44 anuncios) mayoritariamente administrativo (concursos, plenos); pocos edictos urbanísticos activos.
- `silbo.aytoboadilla.com` (mencionado en menú) inaccesible por SSL desde entorno automatizado.
- Documentos del tablón requieren tokens JS; se usa URL de detalle `verAnuncio` como referencia estable.
- Sin geolocalización en fuentes del ayuntamiento.

## Referencia adapters

- Drupal + PDF crawl: `pozuelo.py`, `las_rozas.py`
- Tablón sede + filtro regex: `mostoles.py`, `getafe.py`
