# Cómpeta — investigación portal ayuntamiento

**Municipio:** Cómpeta (Málaga, Andalucía)  
**Slug:** `competa`  
**Boletín:** BOJA (`boja`, 9 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.competa.es | **Parcial** — plataforma Diputación Málaga (`static.malaga.es`); algunas rutas 403 CloudFront en CI sin UA navegador |
| Sede electrónica | https://competa.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://competa.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://competa.sedelectronica.es/dossier | Redirige a `/dossier.0`; lento/timeout en CI |
| Consulta expedientes | https://competa.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Urbanismo (web) | https://www.competa.es/14038/urbanismo | Formularios y modelos de solicitud |
| Transparencia | http://www.malaga.es/gobiernoabierto/portal/entidad/ent-769/competa | Portal gobierno abierto Diputación |
| Datos geográficos | https://www.competa.es/9789/datos-geograficos-y-demograficos | 403 en CI; sin visor propio enlazado |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Coín, Cártama, Mijas.
- **Listado:** tabla HTML `AdvertisementBoardListPanel` con columnas:
  - `class_name` (documento)
  - `class_folderCode` (expediente)
  - `class_folderName` (procedimiento)
  - `class_boardCategory` (categoría)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~7–10 filas).
- **Filtro categoría:** dropdown «Mostrando: Todos».

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Procedimiento | Descripción |
|-------|---------------|-------------|
| 03/08/2026 | Procedimiento Genérico | Expediente de Rectificación Descriptiva de Finca, protocolo 2151/2026 |
| 03/08/2026 | Procedimiento Genérico | Expediente de Rectificación Descriptiva de Finca, protocolo 2157/2026 |

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor con coordenadas.
- Trámites informativos en web municipal:
  - https://www.competa.es/16127/autorizacion-ejecucion-de-obras
  - https://www.competa.es/16152/licencias-de-apertura-y-actividades-economicas
  - https://www.competa.es/16136/cambios-de-uso
- Las licencias concedidas publicadas aparecen en el tablón como edictos (cuando existan).

## Proyectos / planeamiento

- **Tablón:** rectificaciones descriptivas de finca y anuncios de información pública (cuando proceda).
- **Web municipal:** sección urbanismo con formularios (certificación administrativa, reconocimiento situación jurídico-urbanística, segregación/parcelación).
- **Transparencia:** portal gobierno abierto Diputación Málaga (`ent-769/competa`); sin carpetas de planeamiento estructuradas en sede local.
- No hay visor de seguimiento de expedientes público fuera del tablón.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PRP Málaga / Diputación: `https://gis.prpmalaga.es/` — visores cartográficos provinciales (PGOU por municipio); sin ArcGIS REST accesible desde CI.
  - Página «Datos Geográficos y Demográficos» en web municipal: sin visor urbanístico interactivo enlazado a expedientes.
  - SITUA/VITUA (Junta de Andalucía): planeamiento regional; sin enlace por expediente del ayuntamiento.
- **Estrategia:** los visores provinciales muestran zonificación PGOU, **sin campo de enlace a expediente** del tablón. Los anuncios son PDF sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON por código de expediente.
  - Web municipal con WAF CloudFront en rutas concretas desde CI.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- Consulta de expedientes requiere login.
- `/dossier` inestable (timeout) en entorno CI.

## Adapter implementado

- `municipio.adapters.competa:CompetaAyuntamientoAdapter`
- Fuentes: tablón sede + páginas informativas de trámites (sede y web municipal).
- IDs: `competa-lic-*` / `competa-proy-*` (sha256[:14]).
