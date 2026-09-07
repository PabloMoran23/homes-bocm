# Arjona — investigación portal ayuntamiento

**Municipio:** Arjona (Jaén, Andalucía)  
**Slug:** `arjona`  
**INE:** 23007  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.arjona.es | **Bloqueada** — WAF anti-bot (challenge JS, detecta headless/CI) |
| Urbanismo (web) | https://www.arjona.es/urbanismo | Misma protección WAF |
| Planeamiento (web) | https://www.arjona.es/planeamiento | Misma protección WAF |
| Sede electrónica | https://arjona.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://arjona.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Transparencia | https://arjona.sedelectronica.es/transparency | **Operativa** — carpetas por área municipal |
| Catálogo trámites | https://arjona.sedelectronica.es/dossier | Redirige a `/dossier.0`; lento/timeout en CI |
| Consulta expedientes | https://arjona.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Baeza, Cártama.
- **Listado:** tabla HTML `AdvertisementBoardListPanel` con columnas estándar espublico:
  - `class_name` (documento)
  - `class_folderCode` (expediente)
  - `class_folderName` (procedimiento)
  - `class_boardCategory` (categoría)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).
- **Contenido actual (sep 2026):** mayoría de anuncios de empleo/subvenciones; sin licencias de obra ni planeamiento en primera página.

## Transparencia (sede)

- Portal de transparencia integrado en sede espublico (`/transparency`).
- **Sección 7:** «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» — **0 documentos** publicados (sep 2026).
- Otras secciones: contratación, subvenciones, personal, etc.

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor con coordenadas.
- Trámites vía catálogo sede (`/dossier`) y consulta de expedientes autenticada.
- Las licencias concedidas publicadas aparecerían en el tablón como edictos (cuando existan).

## Proyectos / planeamiento

- **SITUA (Junta de Andalucía):** https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf — consulta de planeamiento digitalizado por municipio (PGOU Arjona).
- **Transparencia sede:** sección urbanismo vacía.
- **Web municipal:** rutas `/urbanismo` y `/planeamiento` existen pero no accesibles desde CI por WAF.
- No hay visor urbanístico propio del ayuntamiento enlazado a expedientes.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/VITUA (Junta de Andalucía): planeamiento regional digitalizado; visor JSF sin API REST GeoJSON por expediente.
  - Web municipal: sin acceso por WAF.
  - Sede espublico: sin visor GIS ni coordenadas en tablón.
- **Estrategia:** SITUA muestra cartografía de planeamiento aprobado, **sin campo de enlace a expediente** del tablón ni query ArcGIS/WFS pública por código municipal.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por expediente.
  - Anuncios del tablón son PDF sin georreferencia embebida.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Web corporativa con WAF anti-bot (no scrapeable en CI).
- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- Consulta de expedientes requiere login.
- `/dossier` inestable (timeout) en entorno CI.
- Transparencia urbanismo sin documentos publicados.

## Adapter implementado

- `municipio.adapters.arjona:ArjonaAyuntamientoAdapter`
- Fuentes: tablón sede + metadatos SITUA/transparencia + páginas informativas de trámites.
- IDs: `arjona-lic-*` / `arjona-proy-*` (sha256[:14]).
