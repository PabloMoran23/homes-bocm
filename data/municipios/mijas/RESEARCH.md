# Mijas — investigación portal ayuntamiento

**Municipio:** Mijas (Málaga, Andalucía)  
**Slug:** `mijas`  
**Boletín:** BOJA (`boja`, 25 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.mijas.es/portal/ | **Operativa** — WordPress |
| Urbanismo | https://www.mijas.es/portal/urbanismo/ | Sección con trámites y enlaces |
| Planes parciales / especiales | https://www.mijas.es/portal/urbanismo/planes-parciales-de-ordenacion-planes-especiales-y-expedientes-de-adaptacion-al-pgou/ | **Operativa** — 45 ZIP con documentación |
| Estudios de detalle | https://www.mijas.es/portal/urbanismo/estudios-de-detalle/ | **Operativa** — 124 ZIP |
| Instrumentos de gestión | https://www.mijas.es/portal/urbanismo/instrumentos-de-gestion/ | **Operativa** — 45 ZIP |
| PGOU | https://www.mijas.es/portal/plan-general-de-ordenacion/ | Documentación PGOU (ZIP/PDF) |
| Sede electrónica (nueva) | https://mijas.sedelectronica.es | **Operativa** — espublico gestiona (desde mayo 2025) |
| Sede antigua | http://sede.mijas.es | Solo impuestos / empadronamiento |
| Tablón sede | https://mijas.sedelectronica.es/board/ | **Operativa** — tabla HTML preview-document |
| Tablón portal | https://www.mijas.es/portal/tablon-de-anuncios-y-edictos/ | Redirige a sede |
| Consulta expedientes | https://mijas.sedelectronica.es/expedientes | Requiere autenticación |
| Licencias obras | https://www.mijas.es/portal/urbanismo/licencias-de-obras-mayores/ | Informativo + enlace sede |

## Cómo se listan expedientes

### Planeamiento (WordPress)

- **CMS:** WordPress en `www.mijas.es/portal`.
- **Formato:** páginas con listas de enlaces a archivos `.zip` en `/wp-content/uploads/`.
- **Nomenclatura:** `EXPTE. {número}. {tipo}, {nombre}.zip` (p. ej. `EXPTE. 361. SUP C-2 A, Residencial Mijas.zip`).
- **Tipos:** SUP (plan parcial), SUNP, UE (estudio de detalle), instrumentos de gestión, adaptaciones PGOU.
- **Fecha:** inferida del path `/uploads/YYYY/MM/` del ZIP.
- **Total:** ~212 ZIP únicos entre las cuatro páginas semilla.

### Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Coín, Algete, Humanes.
- **Listado:** tabla HTML con columnas:
  - `class_name` (documento)
  - `class_folderCode` (expediente, p. ej. `24536/2026`)
  - `class_folderName` (procedimiento: Licencias de Actividad, …)
  - `class_boardCategory` (Urbanismo, Anuncios, …)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).

### Ejemplos urbanísticos en tablón (jul 2026)

| Expediente | Procedimiento | Descripción |
|------------|---------------|-------------|
| 24536/2026 | Licencias de Actividad | Edicto exposición pública calificación ambiental |
| 3231/2025 | Licencias de Actividad | Edicto calificación ambiental |
| — | Urbanismo | Edictos y anuncios de licencias/actividad |

## Licencias de obra

- No hay dataset público de concesiones históricas de obra mayor/menor.
- Las licencias publicadas aparecen en el tablón como edictos de «Licencias de Actividad» o calificación ambiental.
- Trámites informativos en portal y sede `/dossier`; consulta estado vía `licenciasobrasmayores@mijas.es`.
- Consulta de expedientes en sede requiere identificación.

## Proyectos / planeamiento

- **Principal fuente:** ZIP de planeamiento en WordPress (planes parciales, estudios de detalle, instrumentos de gestión).
- **Tablón:** edictos de exposición pública y calificación ambiental vinculados a expedientes.
- **PGOU:** documentación descargable en sección dedicada (revisiones parciales, modificaciones).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Callejero municipal enlaza a visores de catastro por núcleo (Mijas pueblo, Las Lagunas, La Cala, Calahonda) — catastro estatal, no expedientes.
  - No hay visor urbanístico propio (ArcGIS/WFS) enlazado a códigos de expediente.
  - Los ZIP de planeamiento contienen planos PDF/DWG sin API REST pública.
- **Estrategia:** sin query GIS por expediente; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por código de expediente.
  - Documentación en ZIP sin georreferencia embebida en metadatos scrapeables.
  - Consulta de expedientes en sede requiere login.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sede nueva (mayo 2025) con histórico limitado en tablón.
- Sin geometría por expediente.
- ~4 páginas WordPress con muchos ZIP (descarga pesada; el adapter solo indexa metadatos).

## Adapter implementado

- `municipio.adapters.mijas:MijasAyuntamientoAdapter`
- Fuentes: ZIP planeamiento WordPress + tablón sede + páginas informativas trámites.
- IDs: `mijas-lic-*` / `mijas-proy-*` (sha256[:14]).
