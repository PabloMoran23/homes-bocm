# Santorcaz — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (Neosoft) | https://www.ayuntamientosantorcaz.com | CMS corporativo |
| PGOU | https://www.ayuntamientosantorcaz.com/pgou-plan-general-de-ordenacion-urbana | Nota informativa PGOU (imagen; sin PDFs descargables) |
| Normativa municipal | https://www.ayuntamientosantorcaz.com/normativa-municipal | Ordenanzas fiscales BOCM (PDF en `/Ficheros/Documentos/`) |
| PIC | https://www.ayuntamientosantorcaz.com/pic | Punto de Información Catastral (enlace a sede Catastro) |
| Sede espublico gestiona | https://santorcaz.sedelectronica.es | Tablón, trámites, transparencia |
| Tablón de anuncios | https://santorcaz.sedelectronica.es/board | Anuncios publicados (HTML tabla, ~10 visibles; preview-document PDF) |
| Portal transparencia | https://santorcaz.sedelectronica.es/transparency | Sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (74 documentos; expansión vía Wicket AJAX) |
| Consulta expedientes | https://santorcaz.sedelectronica.es/expedientes | Requiere identificación electrónica |

## Listado de expedientes / proyectos

- **Tablón de anuncios:** tabla HTML en `/board` con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Enlaces `preview-document/{uuid}` a PDF. Contenido actual mayoritariamente contratación y presupuesto; urbanismo puntual (exposición ordenanza fiscal).
- **Transparencia:** carpeta urbanismo con 74 documentos; el listado completo requiere interacción Wicket (no expone UUID de subcarpeta en HTML inicial).
- **PGOU web:** página informativa sin listado de documentos PDF.
- **WFS SITCM:** 15 ámbitos del PGOU municipal con polígonos (`UE-1`…`UE-11`, `SAU-1`, `SAU-2`, `AA-1`, `AA-2`).

## Licencias

- No hay dataset público de concesiones con dirección/coords.
- Tablón sede puede publicar edictos de licencia (poco frecuente en muestra actual).
- Trámites de licencia vía sede (`/dossier`); catálogo no responde desde scrape automatizado (timeout/vacío en entorno agente).
- Adapter incluye páginas informativas: tablón, consulta expedientes, transparencia urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid IDEM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='SANTORCAZ'`
  - Campo ámbito: `DS_NOMB_AMB` (15 polígonos: UE-1 CAMINO DE ANCHUELO, UE-7 EL GAVILÁN, SAU-1 LA CRUZ DE PIEDRA, AA-1 URBANIZACIÓN EL COMISARIO, etc.)
- **Estrategia:** descargar ámbitos PGOU desde WFS (`outputFormat=application/json`, `srsName=EPSG:4326`); cruzar título de anuncio con código UE/SAU/AA cuando aparece en texto.
- **Limitaciones:**
  - Sin visor urbanístico municipal ni ArcGIS por expediente.
  - Licencias y estudios de detalle puntuales no tienen polígono en WFS (solo ámbitos del PGOU).
  - Portal transparencia urbanismo no scrapeable sin sesión Wicket.
  - PGOU web sin geometría embebida.

## Limitaciones generales

- Sede `/dossier` e `/info.0` no accesibles desde scrape automatizado (respuesta vacía/timeout).
- Tablón con volumen bajo de anuncios urbanísticos en muestra actual.
- Plenos en web Neosoft sin PDFs embebidos en páginas de actas consultadas.
