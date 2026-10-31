# Seseña — investigación portal ayuntamiento

## URLs base

| Recurso | URL |
|---------|-----|
| Web corporativa | https://ayto-sesena.org |
| Sede electrónica (eAdmin) | https://sede.ayto-sesena.org/eAdmin/Sede.do |
| Tablón de anuncios | https://sede.ayto-sesena.org/eAdmin/Tablon.do?action=verAnuncios&tipoTablon=1 |
| Catálogo trámites | https://sede.ayto-sesena.org/eAdmin/Registrar.do?action=inicioPortalTramites |
| POM en trámite | https://ayto-sesena.org/plan-de-ordenacion-municipal-en-tramite/ |
| Transparencia urbanismo/obras | https://ayto-sesena.org/transparencia/transparencia-uo/ |
| Transparencia POM | https://ayto-sesena.org/transparencia/transparencia-pom/ |
| Formularios licencias (PDF) | https://ayto-sesena.org/descarga-de-documentos/ |

## Cómo se publican proyectos / planeamiento

- **WordPress (Elementor + tablas HTML):** el POM en trámite y la transparencia publican cientos de PDFs bajo `/documentos/pom/` y `/documentos/urbanismo/` (p. ej. SAU34, PEI 8, memoria informativa, anexos).
- **Tablón sede eAdmin:** listado HTML en tabla (`Tablon.do?action=verAnuncio&id=…`); en la muestra actual predominan anuncios de personal/organización, no urbanismo.
- **No hay** visor urbanístico municipal ni listado de expedientes IP enlazado a geometría por expediente.

## Licencias de obra

- No hay registro público de licencias concedidas (solo tablón genérico y formularios PDF de solicitud).
- Tramitación real vía sede con certificado digital (`Login.do`, carpeta ciudadana).
- El adapter ingiere **formularios informativos** (obra mayor/menor, DR, licencia integrada, etc.) desde `descarga-de-documentos/`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ArcGIS CLM `Vector/Planeamiento_Municipal/MapServer/0`, filtro `COD_INE='45161'` (Seseña; no confundir con `45168` que en la capa CLM corresponde al PGOU de Toledo capital).
- **Estrategia:** query GeoJSON al geoportal autonómico; enriquecer filas POM/PGOU y fila sintética CLM con `geom_geojson`. Expedientes/tablon sin enlace GIS → sin polígono por fila.
- **Limitaciones:** certificado SSL caducado en `sede.ayto-sesena.org` (requiere `insecure_ssl`); sin WFS/visor municipal por expediente; documentación mayoritariamente PDF.

## Limitaciones generales

- `www.sesena.es` responde error 500; dominio operativo es `ayto-sesena.org`.
- Tablón con pocos anuncios urbanísticos recientes.
- Muchos PDFs duplicados entre páginas de transparencia (deduplicación por URL en el adapter).
