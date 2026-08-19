# Alcaucín — investigación portal ayuntamiento

**Municipio:** Alcaucín (Málaga, Andalucía)  
**Slug:** `alcaucin`  
**Boletín:** BOJA (`boja`, 4 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.alcaucin.es | **Parcial** — plataforma Diputación Málaga (`static.malaga.es`); homepage 403 CloudFront sin UA navegador |
| Sede electrónica | https://alcaucin.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://alcaucin.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://alcaucin.sedelectronica.es/dossier | Lento/timeout ocasional en CI |
| Urbanismo y Vivienda (sede) | https://alcaucin.sedelectronica.es/catalog/t/a4806ac2-0236-4222-9c47-52bdaaa42c9e | Catálogo trámites urbanismo |
| Consulta expedientes | https://alcaucin.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Urbanismo (web) | https://www.alcaucin.es/es/4526/urbanismo-town-planning | Información de contacto y horarios |
| Impresos urbanismo | https://www.alcaucin.es/es/4508/impresos-urbanismo-town-planning-forms | Formularios PDF |
| Normativa urbanística | https://www.alcaucin.es/es/4500/normativa-urbanistica-town-planning-regulations | Ordenanzas y reglamentos |
| PGOU consolidado | https://www.alcaucin.es/es/4518/texto-refundido-pgou-alcaucin-consolidated-text-pgou-alcaucin | Texto refundido PGOU |
| Planeamiento Diputación | http://www.malaga.es/fomentoinfraestructuras/planeamiento/ficha.asp?mun=29002&cod=736 | Ficha PGOU provincial |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Coín, Cártama.
- **Listado:** tabla HTML `AdvertisementBoardListPanel` con columnas:
  - `class_name` (documento)
  - `class_folderCode` (expediente)
  - `class_folderName` (procedimiento)
  - `class_boardCategory` (categoría)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).
- **Filtro categoría:** dropdown «Mostrando: Todos».

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Procedimiento | Descripción |
|-------|---------------|-------------|
| 16/07/2026 | Declaraciones Responsables o Comunicaciones de Actividad | Anuncio Tramitación información pública expediente 1272/2025 |

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor con coordenadas.
- Trámites informativos en web municipal y sede:
  - Impresos urbanismo (formularios PDF)
  - Catálogo sede «Urbanismo y Vivienda»
  - Catálogo general de trámites (`/dossier`)
- Las licencias concedidas publicadas aparecen en el tablón como edictos (cuando existan).

## Proyectos / planeamiento

- **Tablón:** anuncios de información pública de expedientes (p. ej. 1272/2025).
- **Web municipal:** PGOU consolidado, normativa urbanística, impresos de trámites.
- **Diputación Málaga:** ficha de planeamiento municipal (cod=736, mun=29002).
- No hay visor de seguimiento de expedientes público fuera del tablón.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - VITUA (Junta de Andalucía): https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ — planeamiento autonómico; sin campo de enlace a expediente del tablón.
  - PRP Málaga / Diputación: `https://gis.prpmalaga.es/` — visores cartográficos provinciales (PGOU por municipio); sin ArcGIS REST accesible desde CI enlazable a expedientes.
  - Ficha planeamiento Diputación (`malaga.es/fomentoinfraestructuras/planeamiento/`): documentación alfanumérica, sin geometría por expediente.
- **Estrategia:** los visores provinciales/autonómicos muestran zonificación PGOU, **sin campo de enlace a expediente** del tablón. Los anuncios son PDF sin georreferencia embebida.
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

- `municipio.adapters.alcaucin:AlcaucinAyuntamientoAdapter`
- Fuentes: tablón sede + páginas informativas de trámites (sede y web municipal) + PGOU/normativa estáticos.
