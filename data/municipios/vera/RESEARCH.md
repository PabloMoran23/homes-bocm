# Vera — investigación portal ayuntamiento

**Municipio:** Vera (Almería, Andalucía)  
**Slug:** `vera`  
**Boletín:** BOJA (`boja`, 5 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.vera.es | **Operativa** — CMS propio (Bootstrap, descargar.php) |
| Sede electrónica | https://vera.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://vera.sedelectronica.es/board/ | **Operativa** — ~10 filas vigentes |
| Portal transparencia | https://vera.sedelectronica.es/transparency | **Parcial** — carpeta «5. Urbanismo y Obras Públicas» (24 docs) requiere login |
| Ordenanzas | https://www.vera.es/ayuntamiento/index.php?page=ordenanzas | **Operativa** — PDFs normativa urbanística |
| Geoportal | https://qgis.vera.es | **Operativa** — inventario municipal (saneamiento, parques, mobiliario) |
| E-gobierno | https://www.vera.es/index.php?page=egobierno | Enlaces a sede y tablón |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Cártama, Coín.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** ~10 anuncios vigentes (ago 2026); sin histórico amplio en primera página.

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Expediente | Procedimiento | Descripción |
|-------|------------|---------------|-------------|
| 06/08/2026 | 3848/2026 | Ordenanza fiscal | Modificación ICIO y tasa licencias urbanísticas |
| 31/07/2026 | 10/2026 | Acceso información pública | Notificaciones denuncias / expedientes sancionadores |
| 06/08/2026 | 3179/2026 | Ordenanza fiscal | Modificación tasa expedición documentos administrativos |

## Licencias de obra

- No hay dataset público de concesiones de licencia de obra con coordenadas.
- Ordenanzas fiscales regulan ICIO y tasa por licencias urbanísticas (publicadas en tablón y web).
- Trámites de solicitud vía sede electrónica (`/dossier`); consulta de expedientes requiere Cl@ve (`/expedientes`).
- El adapter incluye páginas informativas del tablón y catálogo de trámites.

## Proyectos / planeamiento

- **Tablón:** ordenanzas fiscales urbanísticas, notificaciones de expedientes sancionadores, acceso a información pública.
- **Ordenanzas web:** Normas Urbanísticas, Ordenanza Municipal de Edificación, protección del espacio urbano, habitabilidad, etc. (PDFs en `descargar.php`).
- **Transparencia sede:** carpeta «5. Urbanismo y Obras Públicas» con 24 documentos; **acceso bloqueado** sin identificación electrónica (redirige a login).
- **BOJA:** modificaciones PGOU (p. ej. MP 33 sector R-19, exp. 2738/2020) publicadas en boletín regional; no re-parseadas por el adapter.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Geoportal municipal https://qgis.vera.es — módulos cartográficos de saneamiento, abastecimiento, parques, mobiliario (datos GNOIDE/IDEAndalucía); **sin capas de planeamiento ni enlace a expediente**.
  - Portal transparencia urbanismo: documentos PDF sin georreferencia.
  - SITUA/Junta de Andalucía: planeamiento regional; sin query por código de expediente del ayuntamiento.
- **Estrategia:** no hay ArcGIS/WFS público enlazable a expedientes del tablón. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Sin `geom_geojson` por proyecto.
  - Carpeta transparencia urbanismo requiere autenticación.
  - Página `page=urbanismo` en web municipal lista instalaciones turísticas (no planeamiento).

## Limitaciones generales

- Tablón con pocos anuncios vigentes (~10).
- Sin listado histórico público de licencias concedidas.
- Transparencia urbanismo detrás de login.
- `/dossier` puede ser lento en CI.

## Adapter implementado

- `municipio.adapters.vera:VeraAyuntamientoAdapter`
- Fuentes: tablón sede + ordenanzas urbanísticas (web) + páginas informativas trámites.
