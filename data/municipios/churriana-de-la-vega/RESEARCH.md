# Churriana de la Vega — investigación portal ayuntamiento

**Municipio:** Churriana de la Vega (Granada, Andalucía)  
**Slug:** `churriana-de-la-vega`  
**INE:** 18062  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://ayuntamientochurrianadelavega.org | **Operativa** — WordPress municipal |
| Sede electrónica | https://churrianadelavega.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://churrianadelavega.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://churrianadelavega.sedelectronica.es/dossier | Lento/timeout ocasional en CI (~30s) |
| Urbanismo (sede) | Sección «20 - URBANISMO» en dossier | Licencias, segregaciones, declaraciones responsables |
| Consulta expedientes | https://churrianadelavega.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Portal transparencia | http://churrianadelavega.sedelectronica.es/transparency/ | Normativas y ordenanzas |
| PGOU BOJA 2015 | https://www.juntadeandalucia.es/boja/2015/148/74 | Aprobación definitiva PGOU |
| BOP Dip. Granada | https://bop.dipgra.es | Anuncios de planeamiento (SAGA CMS) |
| SITUA / VITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento autonómico |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Coín, Alcaucín.
- **Listado:** tabla HTML `AdvertisementBoardListPanel` con columnas:
  - `class_name` (documento)
  - `class_folderCode` (expediente)
  - `class_folderName` (procedimiento)
  - `class_boardCategory` (categoría)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).

### Ejemplos urbanísticos encontrados (sep 2026)

| Fecha | Procedimiento | Descripción |
|-------|---------------|-------------|
| 04/09/2026 | Declaraciones Responsables o Comunicaciones de Actividad | Información pública licencia apertura reglamentaria 3125/2026 — supermercado C/San Ramón (exp. LAC-2026/0028) |

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor con coordenadas.
- Trámites informativos en sede:
  - Catálogo «20 - URBANISMO» (licencias, segregaciones, declaraciones responsables de obra)
  - Catálogo general de trámites (`/dossier`)
- Las licencias concedidas publicadas aparecen en el tablón como edictos de información pública (p. ej. calificación ambiental + licencia de actividad).

## Proyectos / planeamiento

- **PGOU:** aprobado definitivamente en 2015 (ref. 1051/2012, BOJA 148/2015).
- **Innovaciones PGOU:** publicadas en BOP Dip. Granada (p. ej. ampliación IES Federico García Lorca, 2024–2025).
- **Estudios de detalle:** BOP Dip. Granada (p. ej. embocadura Plazas Parrilla y Altozano, jun 2026).
- **Tablón:** anuncios de información pública de expedientes urbanísticos y licencias de actividad.
- **SITUA:** documentación del PGOU vigente consultable en SituaDIFusión.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - VITUA (Junta de Andalucía): https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ — planeamiento autonómico; sin campo de enlace a expediente del tablón.
  - SITUA SituaDIFusión: documentación PGOU con capas de zonificación municipal; sin API REST por código de expediente del tablón.
  - BOP Dip. Granada: PDFs de anuncios sin geometría embebida enlazable.
- **Estrategia:** los visores autonómicos muestran zonificación PGOU del municipio (INE 18062), **sin campo de enlace a expediente** del tablón. Los anuncios son PDF sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON por código de expediente.
  - Consulta de expedientes requiere login.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- `/dossier` inestable (timeout ~30s) en entorno CI.
- BOP Dip. Granada sin API de búsqueda programática estable.

## Adapter implementado

- `municipio.adapters.churriana_de_la_vega:ChurrianaDeLaVegaAyuntamientoAdapter`
- Fuentes: tablón sede + páginas informativas de trámites + PGOU/SITUA/BOJA/BOP estáticos.
