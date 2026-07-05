# Coín — investigación portal ayuntamiento

**Municipio:** Coín (Málaga, Andalucía)  
**Slug:** `coin`  
**Boletín:** BOJA (`boja`, 41 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.coin.es | **Inaccesible** — Drupal con error SQL (`INSERT denied` en watchdog/cache) o HTTP 403 |
| Web alternativa | https://www.ayto-coin.es | **Bloqueada** — challenge Cloudflare/Hostiman |
| Sede electrónica | https://coin.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://coin.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://coin.sedelectronica.es/dossier | Lenta; trámites sin listado histórico |
| Consulta expedientes | https://coin.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Visor urbanístico PGOU | https://gis.prpmalaga.es/web_GIS/geoportal_pub/HTML/visorcoinv22/index.html | Visor CMV/ArcGIS (PRP Málaga); sin REST público accesible desde CI |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Humanes, Griñón, Algete.
- **Listado:** tabla HTML `AdvertisementBoardListPanel` con columnas:
  - `class_name` (documento)
  - `class_folderCode` (expediente, p. ej. `5090/2021`)
  - `class_folderName` (procedimiento: Planeamiento General, Licencias de Actividad, …)
  - `class_boardCategory` (categoría)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX con tokens de sesión; el adapter parsea la primera página (~10 filas).
- **Búsqueda:** formulario POST Wicket por descripción (no determinista sin sesión).
- **Filtro categoría:** dropdown «Mostrando: Todos» (sin categoría «Urbanismo» dedicada; procedimientos en columna `folderName`).

### Ejemplos urbanísticos encontrados (jul 2026)

| Expediente | Procedimiento | Descripción |
|------------|---------------|-------------|
| 5090/2021 | Planeamiento General | Aprobación inicial cambio de uso sector SUNP-2 → SUPI-7 |
| 4458/2026 | Licencias de Actividad | Edicto hostelería Big Burger House S.L. |
| 1166/2026 | Licencias de Actividad | Venta productos alimentación |

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor.
- Las licencias publicadas aparecen en el tablón como edictos («EDICTO AREA IND. AYTO.») o «Licencias de Actividad».
- Trámites informativos en sede `/dossier` (formularios PDF en web caída: `coin.es/sites/default/files/documents/SOLICITUD-LICENCIA-OBRA-MENOR.pdf`).

## Proyectos / planeamiento

- **Tablón:** procedimiento «Planeamiento General» con anuncios BOPMA (Boletín Oficial Provincia Málaga).
- **Web corporativa** (`coin.es/areas/urbanismo`): inaccesible; noticias de visor PGOU en prensa local.
- No hay sección pública de expedientes en información pública fuera del tablón.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Visor PGOU Coín (PRP Málaga / Diputación): https://gis.prpmalaga.es/web_GIS/geoportal_pub/HTML/visorcoinv22/index.html
  - Capas: calificación suelo PGOU 1997/2011, ortofoto, catastro (según nota de prensa ayuntamiento 2020).
  - No expone ArcGIS REST Services público en `gis.prpmalaga.es/arcgis/rest/services` desde entorno CI.
- **Estrategia:** el visor es consulta cartográfica de zonificación PGOU, **sin campo de enlace a expediente** del tablón. Los anuncios del tablón son PDF sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON por código de expediente.
  - Web principal caída impide extraer enlaces al visor desde Drupal.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Web `coin.es` no scrapeable (error BD Drupal / WAF).
- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.coin:CoinAyuntamientoAdapter`
- Fuentes: tablón sede + páginas informativas de trámites.
- IDs: `coin-lic-*` / `coin-proy-*` (sha256[:14]).
